"""FastAPI application entry point.

Run (from the backend folder, with the venv active):
    uvicorn app.main:app --reload
Swagger docs: http://127.0.0.1:8000/docs
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.concurrency import run_in_threadpool

from app.api.routes import admin, assistant, auth, conversations, dashboard, disease, items, knowledge, meta, weather
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import RequestContextMiddleware, setup_logging
from app.core.rate_limit import limiter
from app.services.container import ServiceContainer

settings = get_settings()
setup_logging(settings.LOG_LEVEL)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    app.state.services = ServiceContainer(settings)
    if settings.PRELOAD_MODELS:
        await run_in_threadpool(app.state.services.preload)
    logger.info("%s started (%s)", settings.APP_NAME, settings.ENVIRONMENT)
    yield
    logger.info("Shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Multilingual voice-based farming assistant with plant disease detection.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
register_exception_handlers(app)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

prefix = settings.API_PREFIX
for module_router in (
    meta.router,
    auth.router,
    assistant.voice_router,
    assistant.router,
    assistant.feedback_router,
    disease.router,
    items.router,
    weather.router,
    knowledge.router,
    conversations.router,
    dashboard.router,
    admin.router,
):
    app.include_router(module_router, prefix=prefix)


@app.get("/", include_in_schema=False)
def root():
    return {"name": settings.APP_NAME, "docs": "/docs", "health": f"{prefix}/health"}
