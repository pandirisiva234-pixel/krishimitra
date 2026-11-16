"""OpenWeather client (free endpoints only: current weather, 5-day/3-hour forecast, geocoding)."""
from datetime import datetime, timezone

import httpx

from app.core.exceptions import ExternalServiceError, NotFoundError, ServiceNotConfiguredError

BASE = "https://api.openweathermap.org"


def _ts(value: int | None) -> datetime | None:
    return datetime.fromtimestamp(value, tz=timezone.utc) if value else None


class OpenWeatherClient:
    def __init__(self, api_key: str | None, timeout: float = 10.0):
        self.api_key = api_key
        self.timeout = timeout

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def _get(self, path: str, params: dict) -> dict | list:
        if not self.api_key:
            raise ServiceNotConfiguredError("OpenWeather API key is not set. Add OPENWEATHER_API_KEY to backend/.env")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{BASE}{path}", params={**params, "appid": self.api_key})
        except httpx.HTTPError as exc:
            raise ExternalServiceError("Could not reach the weather service") from exc
        if resp.status_code == 401:
            raise ExternalServiceError("OpenWeather rejected the API key (new keys can take up to 2 hours to activate)")
        if resp.status_code == 404:
            raise NotFoundError("Location not found")
        if resp.status_code == 429:
            raise ExternalServiceError("Weather service rate limit reached; try again shortly")
        if resp.status_code >= 400:
            raise ExternalServiceError(f"Weather service error ({resp.status_code})")
        return resp.json()

    async def current(self, lat: float, lon: float) -> dict:
        data = await self._get("/data/2.5/weather", {"lat": lat, "lon": lon, "units": "metric"})
        return parse_current(data)

    async def forecast(self, lat: float, lon: float) -> dict:
        data = await self._get("/data/2.5/forecast", {"lat": lat, "lon": lon, "units": "metric"})
        return parse_forecast(data)

    async def geocode(self, query: str, limit: int = 5) -> list[dict]:
        data = await self._get("/geo/1.0/direct", {"q": query, "limit": limit})
        return [
            {"name": d["name"], "state": d.get("state"), "country": d.get("country", ""),
             "latitude": d["lat"], "longitude": d["lon"]}
            for d in data
        ]


def parse_current(data: dict) -> dict:
    main, wind, weather = data["main"], data.get("wind", {}), (data.get("weather") or [{}])[0]
    return {
        "location_name": data.get("name") or None,
        "latitude": data["coord"]["lat"],
        "longitude": data["coord"]["lon"],
        "temperature_c": main["temp"],
        "feels_like_c": main.get("feels_like", main["temp"]),
        "humidity_pct": int(main["humidity"]),
        "pressure_hpa": main.get("pressure"),
        "wind_speed_ms": float(wind.get("speed", 0.0)),
        "wind_deg": wind.get("deg"),
        "clouds_pct": data.get("clouds", {}).get("all"),
        "rain_1h_mm": data.get("rain", {}).get("1h"),
        "description": weather.get("description", ""),
        "icon": weather.get("icon"),
        "observed_at": _ts(data.get("dt")).isoformat(),
        "sunrise": _iso(_ts(data.get("sys", {}).get("sunrise"))),
        "sunset": _iso(_ts(data.get("sys", {}).get("sunset"))),
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def parse_forecast(data: dict) -> dict:
    city = data.get("city", {})
    points = []
    for item in data.get("list", []):
        weather = (item.get("weather") or [{}])[0]
        points.append({
            "time": _ts(item["dt"]).isoformat(),
            "temperature_c": item["main"]["temp"],
            "humidity_pct": int(item["main"]["humidity"]),
            "wind_speed_ms": float(item.get("wind", {}).get("speed", 0.0)),
            "rain_3h_mm": float(item.get("rain", {}).get("3h", 0.0)),
            "pop": float(item.get("pop", 0.0)),
            "description": weather.get("description", ""),
            "icon": weather.get("icon"),
        })
    return {
        "location_name": city.get("name") or None,
        "latitude": city.get("coord", {}).get("lat"),
        "longitude": city.get("coord", {}).get("lon"),
        "timezone_offset": city.get("timezone", 0),
        "points": points,
    }
