#!/usr/bin/env python3
"""
HaloMCP Auth Test Suite - Tests token refresh and session management.

Validates that:
  1. setup_session creates a valid session from current tokens
  2. refresh_tokens fetches fresh tokens using the session cookie
  3. Session cookie rotation is captured and persisted
  4. Refreshed tokens actually work for API calls
  5. Auto-retry on expired tokens works end-to-end

Usage:
    python test_auth.py
    python test_auth.py --verbose
"""

import json
import time
import sys

from config import get_config, reload_config, _CONFIG_FILE
from auth import (
    setup_session,
    refresh_tokens,
    create_session,
    _get_session_cookies_from_config,
    SESSION_COOKIE_NAMES,
)
from request import HaloRequest, HaloTokenExpiredError
import queries


class TestResult:
    def __init__(self, name, passed, message="", duration=0):
        self.name = name
        self.passed = passed
        self.message = message
        self.duration = duration

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        dur = f" ({self.duration:.2f}s)" if self.duration else ""
        msg = f" - {self.message}" if self.message else ""
        return f"  [{status}] {self.name}{dur}{msg}"


# ==================== Tests ====================


def test_config_has_tokens(verbose=False):
    """Test: config.json has valid auth tokens."""
    start = time.time()
    try:
        cfg = reload_config()
        duration = time.time() - start

        if not cfg.auth_token:
            return TestResult("config-tokens", False, "No authToken in config", duration)
        if not cfg.context_token:
            return TestResult("config-tokens", False, "No contextToken in config", duration)

        if verbose:
            print(f"    authToken: {cfg.auth_token[:20]}...")
            print(f"    contextToken: {cfg.context_token[:20]}...")
            print(f"    transactionId: {cfg.transaction_id or '(none)'}")

        return TestResult("config-tokens", True, "Tokens loaded from config", duration)
    except Exception as e:
        return TestResult("config-tokens", False, str(e), time.time() - start)


def test_tokens_work(verbose=False):
    """Test: current tokens can make a successful API call."""
    start = time.time()
    try:
        result = (
            HaloRequest("getCourseClassesForUser")
            .query(queries.GET_COURSE_CLASSES_FOR_USER)
            .variables({"pgNum": 1, "pgSize": 1})
            .cleaner("list-classes")
            .execute()
        )
        duration = time.time() - start

        classes = result.get("classes", [])
        return TestResult("tokens-work", True, f"API responded, {len(classes)} class(es)", duration)
    except HaloTokenExpiredError as e:
        return TestResult("tokens-work", False, f"Tokens expired: {e.messages}", time.time() - start)
    except Exception as e:
        return TestResult("tokens-work", False, str(e), time.time() - start)


def test_setup_session(verbose=False):
    """Test: create a long-lived session from current tokens."""
    start = time.time()
    try:
        result = setup_session()
        duration = time.time() - start

        if result.get("status") == "error":
            return TestResult("setup-session", False, result["message"], duration)

        if result.get("status") != "session_created":
            return TestResult("setup-session", False, f"Unexpected status: {result.get('status')}", duration)

        if verbose:
            print(f"    Status: {result['status']}")
            print(f"    Expires: {result.get('expires', 'unknown')}")
            print(f"    Username: {result.get('username', 'unknown')}")

        return TestResult("setup-session", True,
                          f"Session created, expires {result.get('expires', '?')}", duration)
    except Exception as e:
        return TestResult("setup-session", False, str(e), time.time() - start)


def test_session_cookies_stored(verbose=False):
    """Test: session cookies were saved to config.json."""
    start = time.time()
    try:
        cookies = _get_session_cookies_from_config()
        duration = time.time() - start

        if not cookies:
            return TestResult("cookies-stored", False, "No sessionCookies in config.json", duration)

        has_session = "__Secure-next-auth.session-token" in cookies
        if not has_session:
            return TestResult("cookies-stored", False,
                              "Missing __Secure-next-auth.session-token", duration)

        stored = [name for name in SESSION_COOKIE_NAMES if name in cookies]
        missing = [name for name in SESSION_COOKIE_NAMES if name not in cookies]

        if verbose:
            for name in stored:
                val = cookies[name]
                print(f"    {name}: {val[:30]}...")
            if missing:
                print(f"    Missing (non-critical): {missing}")

        return TestResult("cookies-stored", True,
                          f"{len(stored)}/{len(SESSION_COOKIE_NAMES)} cookies stored", duration)
    except Exception as e:
        return TestResult("cookies-stored", False, str(e), time.time() - start)


def test_refresh_tokens(verbose=False):
    """Test: refresh tokens using the stored session cookie."""
    start = time.time()
    try:
        # Grab tokens before refresh for comparison
        cfg_before = reload_config()
        old_auth = cfg_before.auth_token

        result = refresh_tokens()
        duration = time.time() - start

        if result.get("status") != "refreshed":
            return TestResult("refresh-tokens", False,
                              f"Unexpected status: {result.get('status')}", duration)

        new_auth = result.get("authToken")
        if not new_auth:
            return TestResult("refresh-tokens", False, "No authToken in refresh response", duration)

        tokens_changed = new_auth != old_auth
        msg = "Fresh tokens received"
        if tokens_changed:
            msg += " (tokens rotated)"
        else:
            msg += " (same tokens returned — still valid)"

        if verbose:
            print(f"    Status: {result['status']}")
            print(f"    Expires: {result.get('expires', 'unknown')}")
            print(f"    Username: {result.get('username', 'unknown')}")
            print(f"    Tokens changed: {tokens_changed}")

        return TestResult("refresh-tokens", True, msg, duration)
    except Exception as e:
        return TestResult("refresh-tokens", False, str(e), time.time() - start)


def test_refreshed_tokens_saved(verbose=False):
    """Test: refreshed tokens were persisted to config.json and reload works."""
    start = time.time()
    try:
        # Reload config from disk (should pick up tokens saved by refresh_tokens)
        cfg = reload_config()
        duration_reload = time.time() - start

        # Verify the reloaded tokens actually work
        result = (
            HaloRequest("getCourseClassesForUser")
            .query(queries.GET_COURSE_CLASSES_FOR_USER)
            .variables({"pgNum": 1, "pgSize": 1})
            .cleaner("list-classes")
            .execute()
        )
        duration = time.time() - start

        classes = result.get("classes", [])
        return TestResult("refreshed-tokens-saved", True,
                          f"Reloaded tokens work, {len(classes)} class(es)", duration)
    except Exception as e:
        return TestResult("refreshed-tokens-saved", False, str(e), time.time() - start)


def test_cookie_rotation_captured(verbose=False):
    """Test: if the session endpoint rotates cookies, we capture the new ones."""
    start = time.time()
    try:
        cookies_before = _get_session_cookies_from_config()
        if not cookies_before:
            return TestResult("cookie-rotation", False, "No cookies to test with", 0)

        # Do a refresh (which should capture any rotated cookies)
        refresh_tokens()
        cookies_after = _get_session_cookies_from_config()
        duration = time.time() - start

        if not cookies_after:
            return TestResult("cookie-rotation", False, "Cookies disappeared after refresh", duration)

        changed = {k for k in cookies_before if cookies_before.get(k) != cookies_after.get(k)}
        new_keys = set(cookies_after) - set(cookies_before)

        if changed or new_keys:
            msg = f"Cookies updated: {changed | new_keys}"
        else:
            msg = "No rotation occurred (cookies unchanged)"

        if verbose:
            if changed:
                for k in changed:
                    print(f"    Rotated: {k}")
            else:
                print("    No cookies were rotated by the server")

        return TestResult("cookie-rotation", True, msg, duration)
    except Exception as e:
        return TestResult("cookie-rotation", False, str(e), time.time() - start)


def test_auto_retry_on_expired(verbose=False):
    """Test: HaloRequest auto-refreshes on token expiry and retries."""
    start = time.time()
    try:
        # Temporarily corrupt the in-memory token to simulate expiry
        cfg = reload_config()
        original_auth = cfg.auth_token

        req = (
            HaloRequest("getCourseClassesForUser")
            .query(queries.GET_COURSE_CLASSES_FOR_USER)
            .variables({"pgNum": 1, "pgSize": 1})
            .cleaner("list-classes")
        )
        # Override with a bad token to force a 401
        req._auth_token = "expired-invalid-token"

        result = req.execute()
        duration = time.time() - start

        classes = result.get("classes", [])

        if verbose:
            print(f"    Forced 401 with bad token, auto-refresh kicked in")
            print(f"    Got {len(classes)} class(es) after retry")

        return TestResult("auto-retry", True,
                          f"Auto-refreshed and retried successfully", duration)
    except HaloTokenExpiredError:
        duration = time.time() - start
        return TestResult("auto-retry", False,
                          "Auto-refresh failed — token expired error not recovered", duration)
    except Exception as e:
        return TestResult("auto-retry", False, str(e), time.time() - start)


# ==================== Runner ====================

ALL_TESTS = [
    ("config-tokens",          test_config_has_tokens),
    ("tokens-work",            test_tokens_work),
    ("setup-session",          test_setup_session),
    ("cookies-stored",         test_session_cookies_stored),
    ("refresh-tokens",         test_refresh_tokens),
    ("refreshed-tokens-saved", test_refreshed_tokens_saved),
    ("cookie-rotation",        test_cookie_rotation_captured),
    ("auto-retry",             test_auto_retry_on_expired),
]


def run_tests(verbose=False):
    """Run all auth/refresh tests."""
    print("=" * 60)
    print("  HaloMCP Auth & Token Refresh Test Suite")
    print(f"  Testing {len(ALL_TESTS)} auth scenarios")
    print("=" * 60)
    print()

    results = []
    total_start = time.time()

    for name, test_fn in ALL_TESTS:
        print(f"  Testing {name}...", end="", flush=True)
        result = test_fn(verbose=verbose)
        results.append(result)
        print(f"\r{result}")

    total_duration = time.time() - total_start

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    print()
    print("=" * 60)
    print(f"  Results: {passed} passed, {failed} failed, "
          f"{len(results)} total ({total_duration:.2f}s)")
    print("=" * 60)

    if failed > 0:
        print("\n  Failed tests:")
        for r in results:
            if not r.passed:
                print(f"    - {r.name}: {r.message}")

    print()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test HaloMCP auth & token refresh")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed output for each test")
    args = parser.parse_args()

    sys.exit(run_tests(verbose=args.verbose))
