"""Weather endpoints. Coordinates default to the farmer's saved location."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_services
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models import User
from app.schemas.other import CurrentWeatherOut, ForecastOut, GeocodeResult
from app.services.container import ServiceContainer

router = APIRouter(prefix="/weather", tags=["Weather"])


def _coords(user: User, lat: float | None, lon: float | None) -> tuple[float, float]:
    if lat is not None and lon is not None:
        return lat, lon
    if user.latitude is not None and user.longitude is not None:
        return user.latitude, user.longitude
    raise AppError("No location given. Set your farm location in your profile or pass lat and lon.",
                   code="location_required", status_code=422)


@router.get("/current", response_model=CurrentWeatherOut)
async def current(
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
):
    la, lo = _coords(user, lat, lon)
    return await services.weather.current(db, la, lo, user.id)


@router.get("/forecast", response_model=ForecastOut)
async def forecast(
    lat: float | None = Query(None, ge=-90, le=90),
    lon: float | None = Query(None, ge=-180, le=180),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    services: ServiceContainer = Depends(get_services),
):
    """5-day / 3-hour forecast, daily summaries and farm advisories."""
    la, lo = _coords(user, lat, lon)
    return await services.weather.forecast(db, la, lo, user.id)


@router.get("/geocode", response_model=list[GeocodeResult])
async def geocode(
    q: str = Query(..., min_length=2, max_length=100, description="Village / town / city name"),
    user: User = Depends(get_current_user),
    services: ServiceContainer = Depends(get_services),
):
    return await services.weather.client.geocode(q)
