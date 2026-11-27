"""Today's mandi (market) prices from Agmarknet, through the free data.gov.in API.

Dataset: "Current Daily Price of Various Commodities from Various Markets (Mandi)"
(resource 9ef84268-d588-465a-a308-a864a43d0070). Each record is one market and variety:
state, district, market, commodity, variety, grade, arrival_date (dd/mm/yyyy) and the
minimum, maximum and modal (most common) price in rupees per quintal (100 kg).

How a question is answered:
1. Find the crop and place: Gemini reads the question (in the farmer's words too) and returns
   {crop, state, district, market}; without Gemini, crop keywords are matched. A place not named
   in the question comes from the farmer's profile.
2. Fetch the state's records (one call, cached for an hour, shared by every crop in that state);
   with no state known, fetch that crop across India.
3. Keep the crop, put the farmer's district/market first, and summarise up to 6 markets.
"""
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

import httpx

from app.core.exceptions import ExternalServiceError, ServiceNotConfiguredError

logger = logging.getLogger(__name__)

RESOURCE_URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
SOURCE_TITLE = "Agmarknet daily mandi prices (data.gov.in)"
SOURCE_URL = "https://agmarknet.gov.in"

# English crop words -> word that appears in the Agmarknet commodity name (matched case-insensitively)
CROPS: dict[str, list[str]] = {
    "tomato": ["tomato"], "onion": ["onion"], "potato": ["potato"], "maize": ["maize", "corn"],
    "paddy": ["paddy", "rice"], "wheat": ["wheat"], "cotton": ["cotton", "kapas"],
    "groundnut": ["groundnut", "peanut"], "chilli": ["chilli", "chili", "chillies"],
    "brinjal": ["brinjal", "eggplant", "aubergine"], "banana": ["banana"], "jowar": ["jowar", "sorghum"],
    "bajra": ["bajra", "pearl millet"], "ragi": ["ragi", "finger millet"], "turmeric": ["turmeric"],
    "soyabean": ["soyabean", "soybean", "soya"], "bengal gram": ["bengal gram", "chana", "chickpea"],
    "tur": ["tur", "arhar", "red gram", "pigeon pea"], "green gram": ["green gram", "moong"],
    "black gram": ["black gram", "urad"], "cabbage": ["cabbage"], "cauliflower": ["cauliflower"],
    "bhindi": ["bhindi", "okra", "ladies finger", "lady finger"], "mango": ["mango"],
    "coconut": ["coconut"], "arecanut": ["arecanut", "areca", "supari"], "garlic": ["garlic"],
    "ginger": ["ginger"], "mustard": ["mustard"], "carrot": ["carrot"], "beans": ["beans"],
    "cucumber": ["cucumber"], "pomegranate": ["pomegranate"], "grapes": ["grapes", "grape"],
    "apple": ["apple"], "coriander": ["coriander", "dhania"], "sunflower": ["sunflower"],
    "castor": ["castor"], "sesamum": ["sesame", "sesamum", "til", "gingelly"], "jute": ["jute"],
    "lemon": ["lemon"], "papaya": ["papaya"], "watermelon": ["watermelon", "water melon"],
    "pumpkin": ["pumpkin"], "bitter gourd": ["bitter gourd"], "bottle gourd": ["bottle gourd"],
    "drumstick": ["drumstick"], "capsicum": ["capsicum"], "peas": ["peas", "green peas"],
    "copra": ["copra"], "sugarcane": ["sugarcane"], "tea": ["tea"], "coffee": ["coffee"],
}
# Word in the Agmarknet name that marks the crop (when it differs from the key)
AGMARK_WORD = {"paddy": "paddy", "chilli": "chilli", "bengal gram": "bengal gram", "tur": "arhar",
               "green gram": "green gram", "black gram": "black gram", "bhindi": "bhindi", "sesamum": "sesamum",
               "watermelon": "water melon", "soyabean": "soyabean", "peas": "peas"}
# Agmarknet's state names that differ from common spellings
STATE_ALIASES = {"kerala": ["Kerala", "Keralam"], "odisha": ["Odisha", "Orissa"],
                 "puducherry": ["Puducherry", "Pondicherry"], "telangana": ["Telangana"],
                 "jammu and kashmir": ["Jammu and Kashmir", "Jammu & Kashmir"]}

MARKET_EXTRACT_SYSTEM_PROMPT = (
    "Read a farmer's question about market (mandi) prices in India. Reply with JSON only: "
    '{"crop": "...", "state": "...", "district": "...", "market": "..."}. '
    "crop: the crop in simple English, singular (e.g. tomato, onion, paddy, cotton, maize). "
    "state: the Indian state in English if the question names it or a place in it, else \"\". "
    "district / market: the district and market (mandi) town in English if named, else \"\". "
    "Never guess a place that is not in the question."
)


def find_crop(text: str) -> str | None:
    low = f" {text.lower()} "
    for crop, words in CROPS.items():
        for w in words:
            if re.search(rf"\b{re.escape(w)}(s|es)?\b", low):
                return crop
    return None


def commodity_matches(commodity: str, crop: str) -> bool:
    name = commodity.lower()
    words = [AGMARK_WORD.get(crop, crop)] + CROPS.get(crop, [])
    return any(re.search(rf"\b{re.escape(w)}", name) for w in words)


def parse_date(value: str | None) -> datetime | None:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except (TypeError, ValueError):
            continue
    return None


def _num(value) -> float | None:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


@dataclass
class PriceQuery:
    crop: str | None
    state: str | None = None
    district: str | None = None
    market: str | None = None
    place_from_profile: bool = False
    extra: dict = field(default_factory=dict)


def parse_extract(raw: str) -> dict | None:
    try:
        text = raw.strip()
        data = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except (ValueError, TypeError):
        return None
    return {k: (data.get(k) or "").strip() if isinstance(data.get(k), str) else "" for k in
            ("crop", "state", "district", "market")}


async def extract_query(llm, question_english: str, original: str | None, profile_state: str | None,
                        profile_district: str | None, timeout: float = 10.0) -> PriceQuery:
    """Crop and place for a price question. Gemini first, then keywords; the profile fills a missing place."""
    data = None
    if llm is not None and getattr(llm, "is_configured", False):
        prompt = f"Question: {original or question_english}\nEnglish meaning: {question_english}"
        try:
            raw = await asyncio.wait_for(llm.generate(prompt, MARKET_EXTRACT_SYSTEM_PROMPT, retries=1,
                                                      json_output=True, max_output_tokens=200), timeout=timeout)
            data = parse_extract(raw)
        except Exception:  # noqa: BLE001  - keyword fallback below
            logger.warning("Price question extraction failed; using keywords", exc_info=True)
    data = data or {}
    crop = find_crop(data.get("crop") or "") or find_crop(question_english) or (data.get("crop") or None)
    q = PriceQuery(crop=crop, state=data.get("state") or None, district=data.get("district") or None,
                   market=data.get("market") or None)
    if not q.state and profile_state:
        q.state, q.place_from_profile = profile_state, True
        if not q.district and profile_district:
            q.district = profile_district
    return q


class MandiClient:
    def __init__(self, api_key: str | None, timeout: float = 15.0, cache_minutes: int = 60):
        self.api_key = api_key
        self.timeout = timeout
        self.cache_seconds = cache_minutes * 60
        self._cache: dict[tuple, tuple[float, list[dict]]] = {}
        self._filter_style: str | None = None  # which filter spelling the API accepted

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def _fetch(self, client: httpx.AsyncClient, field_name: str, value: str, limit: int = 1000) -> list[dict]:
        """Records where field = value. The API's filter spelling has changed over time, so the known
        spellings are tried until one returns records (the working one is remembered)."""
        styles = [self._filter_style] if self._filter_style else ["{f}.keyword", "{f}", "{F}"]
        for style in styles:
            key = "filters[" + style.format(f=field_name, F=field_name.capitalize()) + "]"
            params = {"api-key": self.api_key, "format": "json", "limit": limit, "offset": 0, key: value}
            try:
                resp = await client.get(RESOURCE_URL, params=params)
            except httpx.HTTPError as exc:
                raise ExternalServiceError("Could not reach data.gov.in for market prices") from exc
            if resp.status_code in (401, 403):
                raise ExternalServiceError("data.gov.in rejected the API key (check DATAGOV_API_KEY)")
            if resp.status_code >= 400:
                raise ExternalServiceError(f"Market price service error ({resp.status_code})")
            records = resp.json().get("records") or []
            if records:
                self._filter_style = style
                return records
        return []

    async def _cached(self, field_name: str, values: list[str]) -> list[dict]:
        key = (field_name, tuple(v.lower() for v in values))
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < self.cache_seconds:
            return hit[1]
        records: list[dict] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for value in values:
                records = await self._fetch(client, field_name, value)
                if records:
                    break
        self._cache[key] = (time.monotonic(), records)
        return records

    async def prices(self, q: PriceQuery, max_markets: int = 6) -> dict:
        if not self.api_key:
            raise ServiceNotConfiguredError("Market prices need DATAGOV_API_KEY in backend/.env")
        if not q.crop:
            return {"query": q, "rows": [], "date": None, "scope": None}
        if q.state:
            names = STATE_ALIASES.get(q.state.strip().lower(), [q.state.strip().title()])
            records = await self._cached("state", names)
            scope = "state"
        else:
            records = await self._cached("commodity", [AGMARK_WORD.get(q.crop, q.crop).title()])
            scope = "india"
        rows = []
        for r in records:
            if not commodity_matches(str(r.get("commodity", "")), q.crop):
                continue
            modal = _num(r.get("modal_price"))
            if modal is None or modal <= 0:
                continue
            rows.append({
                "state": r.get("state"), "district": r.get("district"), "market": r.get("market"),
                "commodity": r.get("commodity"), "variety": r.get("variety"),
                "min_price": _num(r.get("min_price")), "max_price": _num(r.get("max_price")), "modal_price": modal,
                "arrival_date": r.get("arrival_date"), "_date": parse_date(r.get("arrival_date")),
            })

        def local(row) -> int:
            d = (q.district or "").lower()
            m = (q.market or "").lower()
            if m and m in str(row["market"]).lower():
                return 0
            if d and (d in str(row["district"]).lower() or d in str(row["market"]).lower()):
                return 1
            return 2

        rows.sort(key=lambda r: (local(r), -(r["_date"].timestamp() if r["_date"] else 0), -r["modal_price"]))
        # one row per market (its best-matching variety)
        seen, picked = set(), []
        for r in rows:
            if r["market"] in seen:
                continue
            seen.add(r["market"])
            picked.append({k: v for k, v in r.items() if not k.startswith("_")} | {"local": local(r) < 2})
            if len(picked) >= max_markets:
                break
        latest = max((r["_date"] for r in rows if r["_date"]), default=None)
        return {"query": q, "rows": picked, "date": latest.strftime("%d %b %Y") if latest else None, "scope": scope}


def price_summary(result: dict) -> str:
    """Plain-text table of the prices, for Gemini and as the source snippet."""
    q: PriceQuery = result["query"]
    lines = [f"Crop: {q.crop}. Place asked: {', '.join(p for p in (q.market, q.district, q.state) if p) or 'not given'}"
             + (" (from the farmer's profile)" if q.place_from_profile else "") + "."]
    if result.get("date"):
        lines.append(f"Latest Agmarknet date: {result['date']}. Prices in rupees per quintal (100 kg).")
    for r in result["rows"]:
        per_kg = r["modal_price"] / 100
        lines.append(
            f"- {r['market']} ({r['district']}, {r['state']}), {r['commodity']} {r['variety'] or ''}".rstrip()
            + f": min {r['min_price']:.0f}, max {r['max_price']:.0f}, modal {r['modal_price']:.0f} "
              f"(about Rs {per_kg:.0f} per kg), date {r['arrival_date']}"
            + (" [farmer's area]" if r.get("local") else "")
        )
    return "\n".join(lines)


def template_answer(result: dict) -> str:
    """Answer without Gemini (or if it fails): the prices themselves, short and clear."""
    q: PriceQuery = result["query"]
    rows = result["rows"]
    if not rows:
        return no_data_answer(q)
    lines = [f"{q.crop.title()} prices (Agmarknet, {result.get('date') or 'latest'}), per quintal:"]
    for r in rows[:4]:
        lines.append(f"{r['market']} ({r['district']}): Rs {r['modal_price']:.0f} "
                     f"(range {r['min_price']:.0f} to {r['max_price']:.0f}), about Rs {r['modal_price'] / 100:.0f} per kg.")
    lines.append("Prices change every day; confirm with the market before you travel.")
    return "\n".join(lines)


def no_data_answer(q: PriceQuery) -> str:
    if not q.crop:
        return ("Please tell me which crop you want the market price for, and your district. "
                "For example: what is the tomato price in Kolar market today?")
    where = q.district or q.state or "your area"
    return (f"I could not find today's {q.crop} price for {where} in the government Agmarknet data. "
            "The market may not have reported yet, or may not trade this crop. Try a nearby big market, "
            "or ask again later in the day.")


MARKET_SYSTEM_PROMPT = (
    "You help Indian farmers understand today's mandi prices. Use ONLY the price lines given. "
    "Write 4-7 short sentences in plain English for a farmer: the price in the farmer's area first (or say it "
    "was not reported and give the nearest listed markets), with the modal price per quintal and per kg, "
    "the range, and the date. Then name the market with the best price among those listed, and remind them "
    "to count transport cost and to check the price with the market before travelling. "
    "No markdown, no tables, no greeting, no invented numbers."
)


def build_market_prompt(question_english: str, summary: str) -> str:
    return f"Farmer's question: {question_english}\n\nAgmarknet prices:\n{summary}"
