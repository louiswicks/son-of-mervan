"""
X-Request-ID tracing middleware.

Reads X-Request-ID from incoming requests (if present and a valid UUID4),
otherwise generates a new UUID4. Echoes the ID back in the response header
and binds it into the structlog context so every log line during the request
carries the same request_id field.
"""
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger(__name__)

_HEADER = "X-Request-ID"


def _valid_uuid4(value: str) -> bool:
    """Return True if *value* is a valid UUID4 string."""
    try:
        parsed = uuid.UUID(value, version=4)
        # UUID() accepts any version but coerces bits — check the variant too.
        return str(parsed) == value.lower()
    except (ValueError, AttributeError):
        return False


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        incoming = request.headers.get(_HEADER, "")
        request_id = incoming if _valid_uuid4(incoming) else str(uuid.uuid4())

        # Bind for the duration of this request; cleared automatically by
        # structlog.contextvars between requests (ASGI lifecycle).
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        response: Response = await call_next(request)
        response.headers[_HEADER] = request_id
        return response
