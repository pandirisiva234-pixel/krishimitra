"""Related YouTube videos: query building, filtering, trusted-channel order, caching and the API route.

YouTube is mocked at the HTTP level with respx, so the real client code runs.
"""
import asyncio

import httpx
import pytest
import respx

from app.services.videos.youtube_client import YouTubeClient, build_search_query, is_trusted, parse_duration

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

SEARCH = {"items": [{"id": {"videoId": v}} for v in ("aaa", "bbb", "ccc", "ddd", "eee")]}


def _video(vid, channel, duration, title=None):
    return {
        "id": vid,
        "snippet": {"title": title or f"Video {vid}", "channelTitle": channel,
                    "thumbnails": {"medium": {"url": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"}}},
        "contentDetails": {"duration": duration},
    }


DETAILS = {"items": [
    _video("aaa", "Random Farm Vlogs", "PT8M10S"),
    _video("bbb", "Kisan Shorts", "PT45S"),             # a Short: skipped
    _video("ccc", "DD Kisan", "PT12M"),                  # trusted
    _video("ddd", "ICAR-IIMR Maize", "PT6M30S"),         # trusted
    _video("eee", "Long Lectures", "PT1H20M"),           # too long: skipped
]}


def test_parse_duration():
    assert parse_duration("PT12M5S") == 725
    assert parse_duration("PT1H2M") == 3720
    assert parse_duration("PT45S") == 45
    assert parse_duration("P1DT1S") == 86401
    assert parse_duration(None) is None and parse_duration("bad") is None


def test_trusted_channels():
    assert is_trusted("DD Kisan") and is_trusted("KVK Ranga Reddy") and is_trusted("ICAR-IIMR")
    assert is_trusted("Tamil Nadu Agricultural University")
    assert not is_trusted("Random Farm Vlogs")


def test_search_query_keeps_keywords_and_language():
    q = build_search_query("How do I control fall armyworm in my maize crop?", "te")
    assert q == "control fall armyworm maize crop Telugu"
    assert build_search_query("What is this?", "en") == "farming"
    assert build_search_query("Tomato blight", "hi").endswith("farming Hindi")


@respx.mock
def test_related_videos_filters_orders_and_caches():
    search = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=SEARCH))
    details = respx.get(VIDEOS_URL).mock(return_value=httpx.Response(200, json=DETAILS))
    yt = YouTubeClient("test-key", max_results=3)

    out = asyncio.run(yt.related_videos("How to control fall armyworm in maize?", "te"))
    ids = [v["video_id"] for v in out["videos"]]
    assert ids == ["ccc", "ddd", "aaa"]  # trusted first, Short and long video removed
    assert out["videos"][0]["trusted"] and not out["videos"][2]["trusted"]
    assert out["videos"][0]["url"] == "https://www.youtube.com/watch?v=ccc"
    assert out["videos"][0]["duration_seconds"] == 720
    params = search.calls[0].request.url.params
    assert params["relevanceLanguage"] == "te" and params["regionCode"] == "IN" and params["safeSearch"] == "strict"
    assert "Telugu" in params["q"] and params["key"] == "test-key"

    again = asyncio.run(yt.related_videos("How to control fall armyworm in maize?", "te"))
    assert again["cached"] is True and again["videos"] == out["videos"]
    assert search.call_count == 1 and details.call_count == 1  # second ask used the cache


@respx.mock
def test_quota_error_is_reported():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(403, json={"error": {"code": 403}}))
    from app.core.exceptions import ExternalServiceError
    with pytest.raises(ExternalServiceError, match="quota"):
        asyncio.run(YouTubeClient("k").related_videos("maize armyworm", "kn"))


@respx.mock
def test_no_results():
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json={"items": []}))
    out = asyncio.run(YouTubeClient("k").related_videos("very rare question", "en"))
    assert out["videos"] == []


def test_route_hidden_without_key(client, farmer, services):
    services.videos.api_key = None
    r = client.get("/api/assistant/videos", params={"q": "maize armyworm", "language_code": "te"},
                   headers=farmer["headers"])
    assert r.status_code == 200 and r.json() == {"enabled": False, "query": None, "videos": []}


@respx.mock
def test_route_returns_videos(client, farmer, services):
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=SEARCH))
    respx.get(VIDEOS_URL).mock(return_value=httpx.Response(200, json=DETAILS))
    services.videos.api_key = "test-key"
    services.videos._cache.clear()
    try:
        r = client.get("/api/assistant/videos", params={"q": "leaf blight in rice", "language_code": "kn"},
                       headers=farmer["headers"])
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["enabled"] is True and len(body["videos"]) == 3
        assert body["videos"][0]["channel"] == "DD Kisan"
    finally:
        services.videos.api_key = None


def test_route_needs_login(client):
    assert client.get("/api/assistant/videos", params={"q": "maize"}).status_code == 401


# ---------------------------------------------------------------- local-language search plan
from app.services.videos.youtube_client import in_local_script, parse_plan, plan_search  # noqa: E402

PLAN_JSON = ('{"local_query": "தக்காளி இலைப்புள்ளி நோய் கட்டுப்பாடு", '
             '"english_query": "tomato leaf spot control India", "must_words": ["tomato", "tomatoes", "தக்காளி"]}')

LOCAL_SEARCH = {"items": [{"id": {"videoId": v}} for v in ("t1", "t2", "p1")]}
LOCAL_DETAILS = {"items": [
    _video("t1", "Farm Tamil", "PT9M", title="தக்காளி இலைப்புள்ளி நோய் கட்டுப்பாடு"),
    _video("t2", "TNAU Agritech", "PT7M", title="Tomato early blight management"),
    _video("p1", "GrowVeg", "PT2M26S", title="5 Ways to Control Potato Blight"),  # wrong crop: dropped
]}


def test_parse_plan():
    plan = parse_plan("```json\n" + PLAN_JSON + "\n```")
    assert plan["queries"] == ["தக்காளி இலைப்புள்ளி நோய் கட்டுப்பாடு", "tomato leaf spot control India"]
    assert plan["must_words"] == ["tomato", "tomatoes", "தக்காளி"]
    assert parse_plan("sorry, no idea") is None
    assert parse_plan('{"local_query": "", "english_query": ""}') is None
    same = parse_plan('{"local_query": "maize armyworm India", "english_query": "maize armyworm India"}')
    assert same["queries"] == ["maize armyworm India"]  # English: one search only


def test_local_script_detection():
    assert in_local_script("தக்காளி நோய்", "ta") and in_local_script("ٹماٹر", "ur")
    assert not in_local_script("WHAT IS EATING MY PLANTS? 👺", "ta")
    assert not in_local_script("टमाटर", "en")


class _PlanLLM:
    is_configured = True

    def __init__(self, reply):
        self.reply = reply

    async def generate(self, prompt, system_instruction, **kw):
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def test_plan_search_fallbacks():
    assert asyncio.run(plan_search(None, "q", None, "Tamil")) is None
    assert asyncio.run(plan_search(_PlanLLM(RuntimeError("503")), "q", None, "Tamil")) is None
    plan = asyncio.run(plan_search(_PlanLLM(PLAN_JSON), "tomato spots", "தக்காளி...", "Tamil"))
    assert plan["must_words"][0] == "tomato"


@respx.mock
def test_plan_keeps_only_crop_videos_and_prefers_local_language():
    search = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=LOCAL_SEARCH))
    respx.get(VIDEOS_URL).mock(return_value=httpx.Response(200, json=LOCAL_DETAILS))
    plan = parse_plan(PLAN_JSON)
    out = asyncio.run(YouTubeClient("k").related_videos("brown spots on tomato leaves", "ta", plan))
    ids = [v["video_id"] for v in out["videos"]]
    assert ids == ["t2", "t1"]  # trusted TNAU first, then the Tamil-title video; potato video removed
    assert search.call_count == 1  # 2 relevant videos from the Tamil search: no English backup search
    assert search.calls[0].request.url.params["q"] == "தக்காளி இலைப்புள்ளி நோய் கட்டுப்பாடு"
    assert all(not k.startswith("_") for v in out["videos"] for k in v)


@respx.mock
def test_english_backup_search_when_local_finds_too_little():
    english = {"items": [{"id": {"videoId": "e1"}}]}
    english_details = {"items": [_video("e1", "ICAR-IIHR", "PT10M", title="Tomato leaf spot control")]}
    empty = {"items": []}

    def search_side_effect(request):
        q = request.url.params["q"]
        return httpx.Response(200, json=english if "India" in q else empty)

    search = respx.get(SEARCH_URL).mock(side_effect=search_side_effect)
    respx.get(VIDEOS_URL).mock(return_value=httpx.Response(200, json=english_details))
    out = asyncio.run(YouTubeClient("k").related_videos("tomato spots", "ta", parse_plan(PLAN_JSON)))
    assert search.call_count == 2 and out["queries"][1] == "tomato leaf spot control India"
    assert [v["video_id"] for v in out["videos"]] == ["e1"]


@respx.mock
def test_route_uses_gemini_plan(client, farmer, services):
    search = respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=LOCAL_SEARCH))
    respx.get(VIDEOS_URL).mock(return_value=httpx.Response(200, json=LOCAL_DETAILS))
    services.videos.api_key = "test-key"
    services.videos._cache.clear()
    old_reply = services.llm.reply
    services.llm.reply = PLAN_JSON
    try:
        r = client.get("/api/assistant/videos", headers=farmer["headers"], params={
            "q": "Brown spots are coming on tomato leaves", "language_code": "ta",
            "original": "தக்காளி இலைகளில் பழுப்பு நிற புள்ளிகள் வருகின்றன"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert [v["video_id"] for v in body["videos"]] == ["t2", "t1"]
        assert search.calls[0].request.url.params["q"] == "தக்காளி இலைப்புள்ளி நோய் கட்டுப்பாடு"
        assert "Tamil" in services.llm.prompts[-1] and "தக்காளி இலைகளில்" in services.llm.prompts[-1]
    finally:
        services.llm.reply = old_reply
        services.videos.api_key = None
