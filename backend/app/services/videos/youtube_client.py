"""Related farming videos from YouTube (YouTube Data API v3, free key).

Gemini first turns the question into a short YouTube search in the farmer's own
language (e.g. "தக்காளி இலைப்புள்ளி நோய் கட்டுப்பாடு") plus an English backup search,
and lists the crop words a relevant video must mention. Only videos whose title or
description names the crop are kept, so a tomato question does not show potato videos.
Without Gemini, a keyword search in English is used.

Each search costs 100 quota units (free limit 10,000 a day); the English backup runs only
when the local-language search finds fewer than 2 relevant videos. Results are cached
in memory, so the same question asked again costs nothing.

Videos from trusted farming channels (DD Kisan, ICAR, KVKs, agricultural
universities, state agriculture departments) are moved to the top and marked
"trusted"; YouTube Shorts and very long videos (over 40 minutes) are skipped.
"""
import asyncio
import json
import logging
import re
import time

import httpx

from app.core.exceptions import ExternalServiceError, ServiceNotConfiguredError

logger = logging.getLogger(__name__)

BASE = "https://www.googleapis.com/youtube/v3"

# Lower-case words that mark a trusted farming channel by its name
TRUSTED_CHANNEL_WORDS = (
    "dd kisan", "icar", "kvk", "krishi vigyan", "krishi vigyan kendra", "agricultural university",
    "agriculture university", "tnau", "pjtsau", "angrau", "uas dharwad", "uas bangalore", "pau ludhiana",
    "iari", "department of agriculture", "agriculture department", "vikaspedia", "nabard", "manage hyderabad",
)
# Language name added to the search so YouTube returns videos in the farmer's language
SEARCH_LANGUAGE = {
    "te": "Telugu", "kn": "Kannada", "hi": "Hindi", "ta": "Tamil", "ml": "Malayalam",
    "mr": "Marathi", "bn": "Bengali", "gu": "Gujarati", "ur": "Urdu", "en": "",
}
MIN_SECONDS, MAX_SECONDS = 60, 40 * 60
_DURATION_RE = re.compile(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def parse_duration(iso: str | None) -> int | None:
    """ISO-8601 duration from YouTube ("PT12M5S") to seconds."""
    if not iso:
        return None
    m = _DURATION_RE.fullmatch(iso)
    if not m:
        return None
    d, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def is_trusted(channel: str) -> bool:
    name = channel.lower()
    return any(word in name for word in TRUSTED_CHANNEL_WORDS)


def build_search_query(question_english: str, language_code: str) -> str:
    """Short keyword query: the English question without filler, plus the language name."""
    words = re.findall(r"[A-Za-z][A-Za-z\-]+", question_english)
    stop = {"what", "how", "why", "when", "which", "should", "can", "could", "would", "do", "does", "did",
            "is", "are", "was", "were", "the", "a", "an", "my", "i", "me", "to", "of", "in", "on", "for",
            "and", "or", "it", "this", "that", "there", "please", "tell", "about", "with", "have", "has",
            "got", "be", "will", "you", "your", "we", "our", "they", "their", "its", "at", "from", "so"}
    keep = [w for w in words if w.lower() not in stop][:8]
    lang = SEARCH_LANGUAGE.get(language_code, "")
    return " ".join(keep + (["farming"] if len(keep) < 3 else []) + ([lang] if lang else []))



VIDEO_PLAN_SYSTEM_PROMPT = (
    "You write YouTube search queries for Indian farmers. Reply with JSON only: "
    '{"local_query": "...", "english_query": "...", "must_words": ["..."]}. '
    "local_query: 3-6 words in the farmer's language and script, the way an Indian farming channel would title "
    "a video (crop + problem + control/treatment). english_query: the same in English, 3-6 words, ending with "
    "'India'. must_words: the crop name in English (singular and plural) and in the farmer's language, written "
    "exactly as used in local_query; add the pest or disease name too only if there is no crop. "
    "For English, local_query equals english_query."
)


def build_plan_prompt(question_english: str, original: str | None, language_name: str) -> str:
    return (f"Farmer's language: {language_name}\n"
            f"Farmer's question: {original or question_english}\n"
            f"English meaning: {question_english}")


def parse_plan(raw: str) -> dict | None:
    """The JSON Gemini returned, checked; None when unusable."""
    try:
        text = raw.strip()
        text = text[text.index("{"): text.rindex("}") + 1]
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    queries = [q.strip() for q in (data.get("local_query"), data.get("english_query"))
               if isinstance(q, str) and 2 <= len(q.strip()) <= 120]
    words = [w.strip().lower() for w in data.get("must_words") or [] if isinstance(w, str) and w.strip()]
    if not queries:
        return None
    return {"queries": list(dict.fromkeys(queries)), "must_words": words[:8]}


async def plan_search(llm, question_english: str, original: str | None, language_name: str,
                      timeout: float = 10.0) -> dict | None:
    """Ask Gemini for the searches; None (keyword fallback) if it is not set up, slow or unclear."""
    if llm is None or not getattr(llm, "is_configured", False):
        return None
    try:
        raw = await asyncio.wait_for(
            llm.generate(build_plan_prompt(question_english, original, language_name), VIDEO_PLAN_SYSTEM_PROMPT,
                         retries=1, json_output=True, max_output_tokens=300),
            timeout=timeout,
        )
    except Exception:  # noqa: BLE001  - videos are optional, never fail because of this
        logger.warning("Video search planning failed; using keywords", exc_info=True)
        return None
    return parse_plan(raw)


def mentions_any(text: str, words: list[str]) -> bool:
    low = text.lower()
    return any(w in low for w in words)


def in_local_script(text: str, language_code: str) -> bool:
    """True when the title is written (partly) in a non-Latin Indian script, i.e. likely local-language."""
    return language_code != "en" and any(0x0900 <= ord(ch) <= 0x0DFF or 0x0600 <= ord(ch) <= 0x06FF for ch in text)

class YouTubeClient:
    def __init__(self, api_key: str | None, timeout: float = 8.0, cache_minutes: int = 360, max_results: int = 3):
        self.api_key = api_key
        self.timeout = timeout
        self.cache_seconds = cache_minutes * 60
        self.max_results = max_results
        self._cache: dict[tuple[str, str], tuple[float, dict]] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def _get(self, client: httpx.AsyncClient, path: str, params: dict) -> dict:
        try:
            resp = await client.get(f"{BASE}{path}", params={**params, "key": self.api_key})
        except httpx.HTTPError as exc:
            raise ExternalServiceError("Could not reach YouTube") from exc
        if resp.status_code == 403:
            raise ExternalServiceError("YouTube refused the request (daily quota used up, or the key is restricted)")
        if resp.status_code == 400:
            raise ExternalServiceError("YouTube rejected the request (check YOUTUBE_API_KEY)")
        if resp.status_code >= 400:
            raise ExternalServiceError(f"YouTube error ({resp.status_code})")
        return resp.json()

    async def _search(self, client: httpx.AsyncClient, query: str, language_code: str) -> list[dict]:
        """One search + details; videos of a sensible length, in YouTube's relevance order."""
        search = await self._get(client, "/search", {
            "part": "snippet", "q": query, "type": "video", "maxResults": 15,
            "regionCode": "IN", "relevanceLanguage": language_code,
            "safeSearch": "strict", "videoEmbeddable": "true",
        })
        ids = [item["id"]["videoId"] for item in search.get("items", []) if item.get("id", {}).get("videoId")]
        if not ids:
            return []
        details = await self._get(client, "/videos", {"part": "snippet,contentDetails", "id": ",".join(ids)})
        order = {vid: i for i, vid in enumerate(ids)}
        videos = []
        for item in details.get("items", []):
            seconds = parse_duration(item.get("contentDetails", {}).get("duration"))
            if seconds is not None and not (MIN_SECONDS <= seconds <= MAX_SECONDS):
                continue  # skip Shorts and very long videos
            sn = item.get("snippet", {})
            thumbs = sn.get("thumbnails", {})
            thumb = (thumbs.get("medium") or thumbs.get("high") or thumbs.get("default") or {}).get("url")
            channel = sn.get("channelTitle", "")
            videos.append({
                "video_id": item["id"],
                "title": sn.get("title", ""),
                "channel": channel,
                "thumbnail_url": thumb,
                "url": f"https://www.youtube.com/watch?v={item['id']}",
                "duration_seconds": seconds,
                "trusted": is_trusted(channel),
                "_text": f"{sn.get('title', '')} {sn.get('description', '')} {' '.join(sn.get('tags') or [])}",
                "_rank": order.get(item["id"], 99),
            })
        videos.sort(key=lambda v: v["_rank"])
        return videos

    async def related_videos(self, question_english: str, language_code: str, plan: dict | None = None) -> dict:
        """plan = {"queries": [local, english], "must_words": [...]} from plan_search(); None = keyword search."""
        if not self.api_key:
            raise ServiceNotConfiguredError("YouTube API key is not set. Add YOUTUBE_API_KEY to backend/.env")
        key = (question_english.strip().lower(), language_code)
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < self.cache_seconds:
            return {**hit[1], "cached": True}

        queries = (plan or {}).get("queries") or [build_search_query(question_english, language_code)]
        must = (plan or {}).get("must_words") or []
        found: dict[str, dict] = {}
        used: list[str] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for step, query in enumerate(queries[:2]):
                used.append(query)
                for v in await self._search(client, query, language_code):
                    if must and not mentions_any(v["_text"], must):
                        continue  # not about this crop
                    v["_step"] = step
                    found.setdefault(v["video_id"], v)
                if len(found) >= 2:
                    break  # enough from the local-language search; save quota

        def score(v):
            # trusted channel, then the farmer's own language, then the earlier (local) search, then relevance
            return (not v["trusted"], not in_local_script(v["title"], language_code), v["_step"], v["_rank"])

        videos = [{k: val for k, val in v.items() if not k.startswith("_")}
                  for v in sorted(found.values(), key=score)[: self.max_results]]
        result = {"query": used[0] if used else None, "queries": used, "videos": videos}
        self._cache[key] = (time.monotonic(), result)
        logger.info("YouTube: %d videos for %s", len(videos), used)
        return {**result, "cached": False}
