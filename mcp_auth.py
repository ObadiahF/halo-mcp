"""Bearer-token access control for the HaloMCP streamable-http server.

Gate: any request under /mcp must send `Authorization: Bearer <token>`.
Source of truth, in precedence order:
  1. HALO_MCP_ACCESS_TOKEN env var
  2. mcpAccessToken in config.json
  3. Auto-generated (32 bytes URL-safe) and persisted to config.json

Stdio transport is local-only and therefore unauthenticated.
"""
import json
import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import _CONFIG_FILE


def get_or_create_access_token() -> str:
    """Return the MCP access token, generating one on first call if needed."""
    env_token = os.environ.get("HALO_MCP_ACCESS_TOKEN")
    if env_token:
        return env_token

    data = {}
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE) as f:
            data = json.load(f)

    token = data.get("mcpAccessToken")
    if token:
        return token

    token = secrets.token_urlsafe(32)
    data["mcpAccessToken"] = token
    with open(_CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return token


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
