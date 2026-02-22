"""
Halo LMS token refresh via next-auth session.

Flow:
  1. Initial setup: User provides authToken/contextToken (from browser DevTools)
  2. We create a next-auth session by calling /api/auth/callback/tokens
  3. The session cookie (__Secure-next-auth.session-token) is stored in config
  4. When tokens expire, we call /api/auth/session with the cookie to get fresh tokens
  5. Session lasts ~30 days before requiring re-authentication

The session cookie acts as a long-lived refresh token. As long as it's valid,
we can obtain fresh authToken/contextToken without user interaction.
"""

import json
import re
from pathlib import Path

import httpx

from .config import get_config, _CONFIG_FILE, HaloConfig

HALO_BASE = "https://halo.gcu.edu"

# All cookies needed for a valid Halo session
SESSION_COOKIE_NAMES = [
    "__Host-next-auth.csrf-token",
    "__Secure-next-auth.callback-url",
    "__Secure-next-auth.session-token",
    "TE1TX0FVVEg",      # LMS_AUTH (base64)
    "TE1TX0NPTlRFWFQ",  # LMS_CONTEXT (base64)
]


def _get_session_cookies_from_config() -> dict | None:
    """Read stored session cookies from config.json."""
    if not _CONFIG_FILE.exists():
        return None
    with open(_CONFIG_FILE) as f:
        data = json.load(f)
    cookies = data.get("sessionCookies")
    if not cookies or not isinstance(cookies, dict):
        return None
    return cookies


def _save_session_cookies(cookies: dict) -> None:
    """Save session cookies to config.json."""
    data = {}
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE) as f:
            data = json.load(f)
    data["sessionCookies"] = cookies
    # Remove old singular key if present
    data.pop("sessionCookie", None)
    with open(_CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def _save_tokens(auth_token: str, context_token: str) -> None:
    """Save refreshed tokens to config.json."""
    data = {}
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE) as f:
            data = json.load(f)
    data["authToken"] = auth_token
    data["contextToken"] = context_token
    with open(_CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)


def create_session(auth_token: str, context_token: str) -> dict:
    """
    Create a next-auth session from existing tokens.

    Returns dict with:
      - sessionCookie: the long-lived session cookie for future refreshes
      - expires: session expiration date
      - authToken: current auth token
      - contextToken: current context token
    """
    with httpx.Client(timeout=30.0) as client:
        # Get CSRF token
        csrf_resp = client.get(f"{HALO_BASE}/api/auth/csrf")
        csrf_resp.raise_for_status()
        csrf_token = csrf_resp.json()["csrfToken"]

        # Sign in with tokens
        callback_resp = client.post(
            f"{HALO_BASE}/api/auth/callback/tokens",
            data={
                "csrfToken": csrf_token,
                "authToken": auth_token,
                "contextToken": context_token,
                "json": "true",
            },
        )
        callback_resp.raise_for_status()

        # Extract all session cookies
        session_cookies = {}
        for cookie in client.cookies.jar:
            if cookie.name in SESSION_COOKIE_NAMES:
                session_cookies[cookie.name] = cookie.value

        if "__Secure-next-auth.session-token" not in session_cookies:
            raise RuntimeError(
                "Failed to obtain session cookies. "
                "The provided tokens may be invalid."
            )

        # Get session data (includes fresh tokens)
        session_resp = client.get(f"{HALO_BASE}/api/auth/session")
        session_resp.raise_for_status()
        session = session_resp.json()

    if not session.get("userId"):
        raise RuntimeError("Session created but no user data returned. Tokens may be invalid.")

    return {
        "sessionCookies": session_cookies,
        "expires": session.get("expires"),
        "authToken": session.get("authToken", auth_token),
        "contextToken": session.get("contextToken", context_token),
        "userId": session.get("userId"),
        "username": session.get("username"),
    }


def refresh_tokens() -> dict:
    """
    Refresh authToken/contextToken using the stored session cookie.

    Returns dict with fresh tokens or raises on failure.
    The refreshed tokens are automatically saved to config.json.
    """
    session_cookies = _get_session_cookies_from_config()
    if not session_cookies:
        raise RuntimeError(
            "No session cookies stored. Run initial setup first:\n"
            "  1. Provide authToken/contextToken in config.json\n"
            "  2. Call the 'setup_session' tool to create a long-lived session"
        )

    with httpx.Client(timeout=30.0) as client:
        # Set all session cookies via header
        cookie_str = "; ".join(f"{k}={v}" for k, v in session_cookies.items())
        session_resp = client.get(
            f"{HALO_BASE}/api/auth/session",
            headers={"Cookie": cookie_str},
        )
        session_resp.raise_for_status()
        session = session_resp.json()

    if not session.get("userId"):
        raise RuntimeError(
            "Session cookie has expired. You need to re-authenticate:\n"
            "  1. Log into https://halo.gcu.edu in your browser\n"
            "  2. Update authToken/contextToken in config.json\n"
            "  3. Call the 'setup_session' tool to create a new session"
        )

    auth_token = session.get("authToken")
    context_token = session.get("contextToken")

    if not auth_token or not context_token:
        raise RuntimeError("Session valid but no tokens returned.")

    # Save refreshed tokens to config.json
    _save_tokens(auth_token, context_token)

    return {
        "status": "refreshed",
        "expires": session.get("expires"),
        "authToken": auth_token,
        "contextToken": context_token,
        "username": session.get("username"),
    }


def setup_session() -> dict:
    """
    Create a long-lived session from current config tokens.
    Stores the session cookie for future token refreshes.

    This only needs to be done once (or when the session expires after ~30 days).
    """
    from .config import reload_config
    cfg = reload_config()

    result = create_session(cfg.auth_token, cfg.context_token)

    # Save session cookies for future refreshes
    _save_session_cookies(result["sessionCookies"])

    return {
        "status": "session_created",
        "expires": result["expires"],
        "username": result.get("username"),
        "message": (
            f"Session created, expires {result['expires']}. "
            "Token refresh will now work automatically."
        ),
    }
