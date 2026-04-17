"""Bearer-token access control for the HaloMCP streamable-http server.

Opt-in: if `HALO_MCP_ACCESS_TOKEN` env var or `mcpAccessToken` in config.json
is set, any request under /mcp must send `Authorization: Bearer <token>`.
Otherwise the server runs unauthenticated (fine for localhost use).

Stdio transport is local-only and therefore always unauthenticated.
"""
import json
import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import _CONFIG_FILE


def get_configured_access_token() -> str | None:
    """Return the configured MCP access token, or None if auth is disabled."""
    env_token = os.environ.get("HALO_MCP_ACCESS_TOKEN")
    if env_token:
        return env_token
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE) as f:
            data = json.load(f)
        token = data.get("mcpAccessToken")
        if token:
            return token
    return None


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Reject requests to /mcp* that lack the correct bearer token."""

    def __init__(self, app, token: str):
        super().__init__(app)
        self._expected = f"Bearer {token}"

    async def dispatch(self, request, call_next):
        if not request.url.path.startswith("/mcp"):
            return await call_next(request)
        # Constant-time compare to avoid timing side-channels on token guesses.
        provided = request.headers.get("authorization", "")
        if not secrets.compare_digest(provided, self._expected):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)
