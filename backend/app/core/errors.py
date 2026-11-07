"""One error shape for every response: {"error": {"code": ..., "message": ...}}.

500s are logged server-side and never return a stack trace or exception text.
"""

import logging
from collections.abc import Mapping
from typing import Any, cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers


def error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    headers: Mapping[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message}
    if extra:
        body.update(extra)
    return JSONResponse({"error": body}, status_code=status_code, headers=headers)


_HTTP_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    429: "rate_limited",
}


# Starlette types handlers as (Request, Exception); each is registered only for its
# own exception class, so the casts below are safe.


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    err = cast(AppError, exc)
    return error_response(err.status_code, err.code, err.message, headers=err.headers)


async def _validation_handler(_: Request, exc: Exception) -> JSONResponse:
    errors = cast(RequestValidationError, exc).errors()
    # Report where and what kind of error, never the submitted value ("input"),
    # which may contain PII.
    fields = [
        {"loc": [str(p) for p in e.get("loc", ())], "type": e.get("type", "invalid")}
        for e in errors
    ]
    return error_response(422, "validation_error", "Invalid request.", extra={"fields": fields})


async def _http_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    http_exc = cast(StarletteHTTPException, exc)
    code = _HTTP_CODES.get(http_exc.status_code, "http_error")
    message = http_exc.detail if isinstance(http_exc.detail, str) else "Request failed."
    return error_response(http_exc.status_code, code, message, headers=http_exc.headers)


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log only the exception type and route; the traceback stays in server logs.
    logger.exception("unhandled_error type=%s path=%s", type(exc).__name__, request.url.path)
    return error_response(500, "internal_error", "Internal server error.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
