"""Weather service: OpenWeather + PostgreSQL cache (weather_data table) + advisories."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WeatherData
from app.services.weather.advisories import build_advisories, daily_summaries


def _round(v: float) -> float:
    return round(float(v), 2)


class WeatherService:
    def __init__(self, client, cache_minutes: int):
        self.client = client
        self.cache_minutes = cache_minutes

    def _cached(self, db: Session, kind: str, lat: float, lon: float) -> dict | None:
        since = datetime.now(timezone.utc) - timedelta(minutes=self.cache_minutes)
        row = db.scalars(
            select(WeatherData)
            .where(WeatherData.kind == kind, WeatherData.latitude == lat, WeatherData.longitude == lon,
                   WeatherData.fetched_at >= since)
            .order_by(WeatherData.fetched_at.desc())
            .limit(1)
        ).first()
        return row.payload if row else None

    def _store(self, db: Session, kind: str, lat: float, lon: float, payload: dict, user_id: int | None) -> None:
        db.add(WeatherData(kind=kind, latitude=lat, longitude=lon, payload=payload, user_id=user_id,
                           location_name=payload.get("location_name")))
        db.commit()

    async def current(self, db: Session, lat: float, lon: float, user_id: int | None = None) -> dict:
        lat, lon = _round(lat), _round(lon)
        cached = self._cached(db, "current", lat, lon)
        if cached:
            return {**cached, "cached": True}
        data = await self.client.current(lat, lon)
        self._store(db, "current", lat, lon, data, user_id)
        return {**data, "cached": False}

    async def forecast(self, db: Session, lat: float, lon: float, user_id: int | None = None) -> dict:
        lat, lon = _round(lat), _round(lon)
        cached = self._cached(db, "forecast", lat, lon)
        was_cached = cached is not None
        data = cached or await self.client.forecast(lat, lon)
        if not was_cached:
            self._store(db, "forecast", lat, lon, data, user_id)
        try:
            current = await self.current(db, lat, lon, user_id)
        except Exception:  # noqa: BLE001 - advisories can still use the forecast alone
            current = None
        points = data["points"]
        return {
            "location_name": data.get("location_name"),
            "latitude": data.get("latitude") or lat,
            "longitude": data.get("longitude") or lon,
            "points": points,
            "daily": daily_summaries(points, data.get("timezone_offset", 0)),
            "advisories": build_advisories(current, points),
            "cached": was_cached,
        }
