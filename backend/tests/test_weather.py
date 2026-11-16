"""Weather module: OpenWeather parsing, caching and advisories (Module 5).

OpenWeather is mocked at the HTTP level with respx, so the real client and
parsing code run against responses shaped like the documented API.
"""
import time

import httpx
import respx

from app.services.weather.advisories import build_advisories, daily_summaries

NOW = int(time.time())
CURRENT = {
    "coord": {"lon": 80.45, "lat": 16.3}, "weather": [{"description": "scattered clouds", "icon": "03d"}],
    "main": {"temp": 27.0, "feels_like": 29.5, "humidity": 88, "pressure": 1008},
    "wind": {"speed": 5.5, "deg": 200}, "clouds": {"all": 40}, "dt": NOW,
    "sys": {"sunrise": NOW - 20000, "sunset": NOW + 20000}, "name": "Guntur",
}
FORECAST = {
    "city": {"name": "Guntur", "coord": {"lat": 16.3, "lon": 80.45}, "timezone": 19800},
    "list": [
        {"dt": NOW + i * 10800, "main": {"temp": 26 + (i % 8), "humidity": 80},
         "wind": {"speed": 3.0}, "pop": 0.8 if i < 4 else 0.1,
         "rain": {"3h": 4.0} if i < 4 else {}, "weather": [{"description": "light rain", "icon": "10d"}]}
        for i in range(40)
    ],
}


@respx.mock
def test_current_and_forecast_with_cache(client, farmer):
    cur = respx.get("https://api.openweathermap.org/data/2.5/weather").mock(return_value=httpx.Response(200, json=CURRENT))
    fc = respx.get("https://api.openweathermap.org/data/2.5/forecast").mock(return_value=httpx.Response(200, json=FORECAST))
    h = farmer["headers"]
    r1 = client.get("/api/weather/current?lat=16.3&lon=80.45", headers=h)
    assert r1.status_code == 200, r1.text
    body = r1.json()
    assert body["location_name"] == "Guntur" and body["humidity_pct"] == 88 and body["cached"] is False
    r2 = client.get("/api/weather/current?lat=16.3&lon=80.45", headers=h)
    assert r2.json()["cached"] is True and cur.call_count == 1  # second call served from PostgreSQL

    f = client.get("/api/weather/forecast?lat=16.3&lon=80.45", headers=h).json()
    assert len(f["points"]) == 40 and len(f["daily"]) >= 5
    categories = {a["category"] for a in f["advisories"]}
    assert {"rain", "spraying", "disease_risk"} <= categories  # rain soon, 5.5 m/s wind, 88% humidity at 27 °C
    assert fc.call_count == 1


def test_location_required(client, farmer):
    resp = client.get("/api/weather/current", headers=farmer["headers"])
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "location_required"


@respx.mock
def test_invalid_key_and_geocode(client, farmer):
    respx.get("https://api.openweathermap.org/data/2.5/weather").mock(return_value=httpx.Response(401, json={}))
    resp = client.get("/api/weather/current?lat=10&lon=10", headers=farmer["headers"])
    assert resp.status_code == 502 and "API key" in resp.json()["error"]["message"]
    respx.get("https://api.openweathermap.org/geo/1.0/direct").mock(return_value=httpx.Response(200, json=[
        {"name": "Guntur", "state": "Andhra Pradesh", "country": "IN", "lat": 16.3, "lon": 80.45}]))
    geo = client.get("/api/weather/geocode?q=Guntur", headers=farmer["headers"]).json()
    assert geo[0]["state"] == "Andhra Pradesh"


def _points(temp=30.0, hum=60, wind=2.0, rain=0.0, pop=0.0, n=40):
    return [{"time": f"2026-11-{14 + i // 8:02d}T{(i % 8) * 3:02d}:00:00+00:00", "temperature_c": temp,
             "humidity_pct": hum, "wind_speed_ms": wind, "rain_3h_mm": rain, "pop": pop,
             "description": "", "icon": None} for i in range(n)]


def test_advisory_rules():
    calm_dry_hot = build_advisories(None, _points(temp=37, hum=40, wind=1.0))
    cats = {a["category"] for a in calm_dry_hot}
    assert "heat" in cats and "irrigation" in cats and "spraying" in cats
    assert all(a["level"] in {"info", "warning", "alert"} for a in calm_dry_hot)
    windy = build_advisories({"temperature_c": 25, "humidity_pct": 50, "wind_speed_ms": 6.0}, _points())
    assert any(a["title"] == "Too windy to spray" for a in windy)
    cold = build_advisories(None, _points(temp=8))
    assert any(a["category"] == "cold" for a in cold)


def test_daily_summary_groups_by_local_day():
    days = daily_summaries(_points(rain=1.0), tz_offset_sec=0)
    assert len(days) == 5 and days[0]["rain_mm"] == 8.0


def test_heavy_rain_later_in_the_week_is_flagged():
    pts = _points()
    for p in pts[32:40]:  # 18 Nov (a Wednesday): 8 x 4 mm = 32 mm
        p["rain_3h_mm"], p["pop"] = 4.0, 1.0
    adv = build_advisories(None, pts)
    heavy = [a for a in adv if a["category"] == "planning"]
    assert heavy and heavy[0]["title"] == "Heavy rain expected on Wednesday"
    assert not any(a["category"] == "planning" for a in build_advisories(None, _points()))
