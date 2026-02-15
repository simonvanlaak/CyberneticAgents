from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderErrorDetails:
    """Sanitized provider error details safe for application logs."""

    status_code: int | None = None
    request_id: str | None = None
    error_type: str | None = None
    error_code: str | None = None
    message: str | None = None
    raw_body_excerpt: str | None = None


def extract_provider_error_details(exc: Exception) -> ProviderErrorDetails | None:
    """Extract sanitized provider error details from an exception.

    Supports httpx.HTTPStatusError (and wrappers) where a response is available.

    Args:
        exc: Raised exception.

    Returns:
        ProviderErrorDetails if extractable, otherwise None.
    """

    httpx_error = _find_httpx_status_error(exc)
    if httpx_error is None:
        return None

    response = getattr(httpx_error, "response", None)
    if response is None:
        return None

    status_code = getattr(response, "status_code", None)
    request_id = None
    try:
        headers = getattr(response, "headers", {})
        if headers:
            request_id = headers.get("x-request-id") or headers.get("x_groq_request_id")
    except Exception:
        request_id = None

    body_json: dict[str, Any] | None = None
    try:
        body_json = response.json()
    except Exception:
        body_json = None

    error_type = None
    error_code = None
    message = None
    if isinstance(body_json, dict):
        err = body_json.get("error")
        if isinstance(err, dict):
            message = _coerce_str(err.get("message"))
            error_type = _coerce_str(err.get("type"))
            error_code = _coerce_str(err.get("code"))
            request_id = request_id or _coerce_str(err.get("request_id"))

    raw_excerpt = None
    if message is None:
        raw_excerpt = _safe_excerpt(_response_text(response))

    return ProviderErrorDetails(
        status_code=int(status_code) if isinstance(status_code, int) else None,
        request_id=request_id,
        error_type=error_type,
        error_code=error_code,
        message=_safe_excerpt(message) if message else None,
        raw_body_excerpt=raw_excerpt,
    )


def _coerce_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=True)
    except Exception:
        try:
            return str(value)
        except Exception:
            return None


def _safe_excerpt(text: str | None, limit: int = 400) -> str | None:
    if not text:
        return None
    normalized = text.replace("\n", " ").replace("\r", " ")
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _response_text(response: Any) -> str | None:
    try:
        return response.text
    except Exception:
        return None


def _find_httpx_status_error(exc: Exception) -> Any | None:
    """Best-effort search for httpx.HTTPStatusError in exception chain."""

    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        name = current.__class__.__name__
        if name == "HTTPStatusError":
            return current
        current = current.__cause__ or current.__context__
    return None
