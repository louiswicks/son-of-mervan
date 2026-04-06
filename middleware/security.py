"""
Security headers middleware.

Adds standard security headers to every response. HSTS is only set when
ENVIRONMENT=production to avoid breaking local HTTP development.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, environment: str = "development"):
        super().__init__(app)
        self.environment = environment

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Prevent browsers from MIME-sniffing the content type
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Block the page from being embedded in iframes (clickjacking protection)
        response.headers["X-Frame-Options"] = "DENY"

        # Minimal CSP — tightened per-route on the frontend; backend API only serves JSON
        response.headers["Content-Security-Policy"] = "default-src 'none'"

        # Don't send the full URL as Referer to third parties
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features the API doesn't need
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # HSTS — only in production (HTTP in dev would make this destructive)
        if self.environment == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response
