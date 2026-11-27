"""Mandi prices: intent rule, crop/place extraction, the data.gov.in client and the assistant route.

data.gov.in is mocked at the HTTP level with respx, so the real client code runs.
"""
import asyncio

import httpx
import respx

from app.services.market.mandi import (
    RESOURCE_URL,
    MandiClient,
    PriceQuery,
    commodity_matches,
    extract_query,
    find_crop,
    no_data_answer,
    parse_extract,
    price_summary,
    template_answer,
)
from app.services.nlp.intent_classifier import is_market_question


def rec(market, district, commodity, modal, date="21/11/2026", state="Andhra Pradesh", variety="Local"):
    return {"state": state, "district": district, "market": market, "commodity": commodity, "variety": variety,
            "grade": "FAQ", "arrival_date": date, "min_price": str(modal - 300), "max_price": str(modal + 300),
            "modal_price": str(modal)}


AP_RECORDS = {"records": [
    rec("Vijayawada", "Krishna", "Tomato", 1500),
    rec("Guntur", "Guntur", "Tomato", 1200),
    rec("Guntur", "Guntur", "Tomato", 1100, variety="Hybrid"),       # same market: one row only
    rec("Tenali", "Guntur", "Tomato", 1300, date="20/11/2026"),
    rec("Guntur", "Guntur", "Dry Chillies", 14000),
    rec("Madanapalli", "Chittor", "Tomato", 900),
    rec("Kurnool", "Kurnool", "Onion", 2000),
]}


def test_market_intent_rule():
    assert is_market_question("What is the price of tomato in Kolar market today?")
    assert is_market_question("Today's rate of onion in Lasalgaon mandi")
    assert is_market_question("Cotton prices in Guntur")
    assert not is_market_question("What is the seed rate for maize per acre?")
    assert not is_market_question("How to control fall armyworm in maize?")
    assert not is_market_question("What is the price of gold jewellery today?")  # not a crop
    assert is_market_question("What are mandi prices today?")


def test_classifier_routes_price_questions(services):
    assert services.intent.predict("What is the tomato price in Guntur?").intent == "market_price"


def test_find_crop_and_commodity_names():
    assert find_crop("price of tomatoes in Kolar") == "tomato"
    assert find_crop("paddy rate today") == "paddy"
    assert find_crop("what is the arhar price") == "tur"
    assert find_crop("How is the weather?") is None
    assert commodity_matches("Paddy(Dhan)(Common)", "paddy")
    assert commodity_matches("Arhar (Tur/Red Gram)(Whole)", "tur")
    assert commodity_matches("Green Chilli", "chilli") and commodity_matches("Dry Chillies", "chilli")
    assert not commodity_matches("Potato", "tomato")


def test_parse_extract():
    d = parse_extract('```json\n{"crop": "tomato", "state": "Karnataka", "district": "Kolar", "market": ""}\n```')
    assert d == {"crop": "tomato", "state": "Karnataka", "district": "Kolar", "market": ""}
    assert parse_extract("no json here") is None


class _LLM:
    is_configured = True

    def __init__(self, reply):
        self.reply = reply

    async def generate(self, prompt, system_instruction, **kw):
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def test_extract_query_uses_question_place_then_profile():
    q = asyncio.run(extract_query(_LLM('{"crop": "tomato", "state": "Karnataka", "district": "Kolar", "market": ""}'),
                                  "tomato price in Kolar", None, "Andhra Pradesh", "Guntur"))
    assert (q.crop, q.state, q.district, q.place_from_profile) == ("tomato", "Karnataka", "Kolar", False)
    # nothing named: the profile fills the place; Gemini down: keywords find the crop
    q = asyncio.run(extract_query(_LLM(RuntimeError("503")), "What is the onion price today?", None,
                                  "Andhra Pradesh", "Guntur"))
    assert (q.crop, q.state, q.district, q.place_from_profile) == ("onion", "Andhra Pradesh", "Guntur", True)


@respx.mock
def test_prices_local_market_first_and_one_row_per_market():
    route = respx.get(RESOURCE_URL).mock(return_value=httpx.Response(200, json=AP_RECORDS))
    client = MandiClient("k")
    result = asyncio.run(client.prices(PriceQuery(crop="tomato", state="andhra pradesh", district="Guntur")))
    markets = [r["market"] for r in result["rows"]]
    assert markets[:2] == ["Guntur", "Tenali"]          # the farmer's district first (newest date first)
    assert set(markets) == {"Guntur", "Tenali", "Vijayawada", "Madanapalli"}
    assert result["rows"][0]["modal_price"] == 1200 and result["rows"][0]["local"] is True
    assert result["date"] == "21 Nov 2026"
    params = route.calls[0].request.url.params
    assert params["filters[state.keyword]"] == "Andhra Pradesh" and params["api-key"] == "k"
    # the same state again (any crop) is served from the cache
    asyncio.run(client.prices(PriceQuery(crop="onion", state="Andhra Pradesh")))
    assert route.call_count == 1


@respx.mock
def test_filter_spelling_fallback_and_state_alias():
    def side_effect(request):
        p = request.url.params
        ok = p.get("filters[state]") == "Keralam"  # only the plain spelling + new state name has data
        return httpx.Response(200, json={"records": [rec("Kochi", "Ernakulam", "Banana", 3000, state="Keralam")]
                                         if ok else []})

    route = respx.get(RESOURCE_URL).mock(side_effect=side_effect)
    client = MandiClient("k")
    result = asyncio.run(client.prices(PriceQuery(crop="banana", state="Kerala")))
    assert result["rows"][0]["market"] == "Kochi"
    assert client._filter_style == "{f}"
    assert route.call_count >= 4  # tried both names with the spellings until one worked


@respx.mock
def test_no_state_searches_the_crop_across_india():
    route = respx.get(RESOURCE_URL).mock(return_value=httpx.Response(200, json=AP_RECORDS))
    result = asyncio.run(MandiClient("k").prices(PriceQuery(crop="tomato")))
    assert result["scope"] == "india"
    assert route.calls[0].request.url.params["filters[commodity.keyword]"] == "Tomato"


@respx.mock
def test_bad_key_is_reported():
    respx.get(RESOURCE_URL).mock(return_value=httpx.Response(403, json={}))
    from app.core.exceptions import ExternalServiceError
    try:
        asyncio.run(MandiClient("bad").prices(PriceQuery(crop="tomato", state="Karnataka")))
        raise AssertionError("expected an error")
    except ExternalServiceError as exc:
        assert "DATAGOV_API_KEY" in str(exc)


def test_summary_and_template_answers():
    rows = [{"state": "Andhra Pradesh", "district": "Guntur", "market": "Guntur", "commodity": "Tomato",
             "variety": "Local", "min_price": 900.0, "max_price": 1500.0, "modal_price": 1200.0,
             "arrival_date": "21/11/2026", "local": True}]
    result = {"query": PriceQuery(crop="tomato", state="Andhra Pradesh", district="Guntur", place_from_profile=True),
              "rows": rows, "date": "21 Nov 2026", "scope": "state"}
    summary = price_summary(result)
    assert "modal 1200 (about Rs 12 per kg)" in summary and "[farmer's area]" in summary
    assert "from the farmer's profile" in summary
    text = template_answer(result)
    assert "Guntur (Guntur): Rs 1200" in text and "per kg" in text
    assert "which crop" in no_data_answer(PriceQuery(crop=None))
    assert "Kolar" in no_data_answer(PriceQuery(crop="tomato", district="Kolar"))


# ---------------------------------------------------------------- through the assistant
def _ask(client, headers, text):
    return client.post("/api/assistant/query", headers=headers, json={"text": text, "language_code": "en"})


@respx.mock
def test_assistant_answers_price_question(client, farmer, services):
    respx.get(RESOURCE_URL).mock(return_value=httpx.Response(200, json=AP_RECORDS))
    services.mandi.api_key = "k"
    services.mandi._cache.clear()
    old = services.llm.reply
    services.llm.reply = [
        '{"crop": "tomato", "state": "", "district": "", "market": ""}',  # extraction
        "Tomato is selling at about Rs 12 per kg in Guntur today.",       # answer
    ]
    try:
        r = _ask(client, farmer["headers"], "What is the tomato price today?")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["intent"] == "market_price" and body["grounded"] is True
        assert body["sources"][0]["kind"] == "market" and "Agmarknet" in body["sources"][0]["title"]
        assert "Guntur" in services.llm.prompts[-1]  # the farmer's profile district was used
        assert "Rs 12 per kg" in body["answer_english"]
    finally:
        services.llm.reply = old
        services.mandi.api_key = None


def test_assistant_without_key_explains_setup(client, farmer, services):
    services.mandi.api_key = None
    body = _ask(client, farmer["headers"], "What is the onion price in Kurnool?").json()
    assert body["intent"] == "market_price" and "DATAGOV_API_KEY" in body["answer_english"]


@respx.mock
def test_assistant_price_service_down(client, farmer, services):
    respx.get(RESOURCE_URL).mock(side_effect=httpx.ConnectError("down"))
    services.mandi.api_key = "k"
    services.mandi._cache.clear()
    old = services.llm.reply
    services.llm.reply = '{"crop": "onion", "state": "", "district": "", "market": ""}'
    try:
        body = _ask(client, farmer["headers"], "What is the onion price today?").json()
        assert "could not reach" in body["answer_english"]
    finally:
        services.llm.reply = old
        services.mandi.api_key = None
