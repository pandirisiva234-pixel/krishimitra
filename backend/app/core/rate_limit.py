"""Rate limiting with SlowAPI (per client IP).

Usage on a route:
    @router.post("/login")
    @limiter.limit(settings.RATE_LIMIT_LOGIN)
    def login(request: Request, ...): ...
The route must accept `request: Request`.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

limiter = Limiter(key_func=get_remote_address, enabled=get_settings().RATE_LIMIT_ENABLED)
