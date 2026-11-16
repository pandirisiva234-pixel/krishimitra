"""Application errors and the handlers that turn them into safe JSON.

Every error response has the same shape:
    {"error": {"code": "...", "message": "...", "request_id": "..."}}
Stack traces and secrets are never sent to the client; they go to the log.
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")


class AppError(Exception):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class AuthError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class FileValidationError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "invalid_file"


class ServiceNotConfiguredError(AppError):
    """An optional feature is missing its API key or model file."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_not_configured"


class ExternalServiceError(AppError):
    """Gemini, OpenWeather or Edge-TTS failed."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "external_service_error"


def _body(request: Request, code: str, message: str, details=None) -> dict:
    error = {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None)}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        if exc.status_code >= 500:
            logger.warning("%s: %s", exc.code, exc.message)
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code, content=_body(request, exc.code, exc.message), headers=headers
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(request, "http_error", str(exc.detail)),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in err["loc"] if p != "body"), "message": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422, content=_body(request, "validation_error", "Invalid input", details)
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_body(request, "internal_error", "Something went wrong. Please try again."),
        )
