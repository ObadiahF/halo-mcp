"""
Builder-pattern HTTP client for Halo LMS GraphQL API.
Auto-applies auth + context tokens. Auto-cleans responses on success.
"""

import uuid
import httpx
from typing import Any, Optional

from .config import get_config
from .cleaners import clean_response

GRAPHQL_ENDPOINT = "https://gateway.halo.gcu.edu/"
ORCHESTRATION_ENDPOINT = "https://orchestration.halo.gcu.edu"


class HaloAPIError(Exception):
    """Raised when the Halo GraphQL API returns errors."""

    def __init__(self, operation: str, messages: list[str]):
        self.operation = operation
        self.messages = messages
        super().__init__(f"Halo API error in '{operation}': {'; '.join(messages)}")


class HaloTokenExpiredError(HaloAPIError):
    """Raised when auth tokens are expired or invalid.

    Halo uses Azure AD SSO with JWE tokens that cannot be refreshed
    programmatically. Users must re-authenticate through the browser.
    """

    def __init__(self, operation: str, messages: list[str]):
        super().__init__(operation, messages)
        self.help_text = (
            "Your Halo auth tokens have expired or are invalid.\n\n"
            "To get fresh tokens:\n"
            "  1. Log into https://halo.gcu.edu in your browser\n"
            "  2. Open DevTools → Application → Cookies (or Network tab)\n"
            "  3. Copy the new authToken and contextToken values\n"
            "  4. Update config.json (or set HALO_AUTH_TOKEN / HALO_CONTEXT_TOKEN env vars)\n"
            "  5. Call the reload_config tool (or restart the server)\n"
        )


def _check_for_auth_errors(operation: str, data: dict) -> None:
    """Check GraphQL response for authentication errors and raise appropriately."""
    if "errors" not in data:
        return

    errors = data["errors"]
    messages = [e.get("message", "Unknown error") for e in errors]

    # Check if any error is an auth/token error
    for error in errors:
        ext = error.get("extensions", {})
        error_code = ext.get("errorCode")
        message = error.get("message", "").lower()

        if (
            error_code == 401
            or "unauthorized" in message
            or "invalid" in message and ("token" in message or "jwt" in message or "jwe" in message or "jws" in message)
            or "expired" in message
            or "authentication" in message and "failed" in message
        ):
            raise HaloTokenExpiredError(operation, messages)

    # Not an auth error — raise generic
    raise HaloAPIError(operation, messages)


class HaloRequest:
    """
    Builder for Halo API requests. Auth and context tokens are applied
    automatically from config. Cleaners run automatically on success.

    Usage:
        result = (
            HaloRequest("getCourseClassesForUser")
            .query(GET_COURSE_CLASSES_FOR_USER)
            .variables({"pgNum": 1, "pgSize": 50})
            .cleaner("list-classes")
            .execute()
        )
    """

    def __init__(self, operation_name: str):
        cfg = get_config()
        self._operation_name = operation_name
        self._query_str: Optional[str] = None
        self._variables: dict[str, Any] = {}
        self._cleaner_name: Optional[str] = None
        self._extra_headers: dict[str, str] = {}
        self._form_data: dict[str, str] | None = None
        self._json_body: Any = None
        self._auth_token: str = cfg.auth_token
        self._context_token: str = cfg.context_token
        self._transaction_id: str = cfg.transaction_id

    # --- Builder methods ---

    def query(self, query_str: str) -> "HaloRequest":
        """Set the GraphQL query string."""
        self._query_str = query_str
        return self

    def variables(self, variables: dict[str, Any]) -> "HaloRequest":
        """Set all GraphQL variables at once."""
        self._variables = variables
        return self

    def cleaner(self, name: str) -> "HaloRequest":
        """Set the response cleaner to auto-apply on success."""
        self._cleaner_name = name
        return self

    def class_slug(self, slug_id: str) -> "HaloRequest":
        """Add current-class-slug-id header."""
        self._extra_headers["current-class-slug-id"] = slug_id
        return self

    def course_class(self, course_class_id: str) -> "HaloRequest":
        """Add current-course-class-id header."""
        self._extra_headers["current-course-class-id"] = course_class_id
        return self

    def form_data(self, data: dict[str, str]) -> "HaloRequest":
        """Set form data for REST (multipart/form-data) requests."""
        self._form_data = data
        return self

    def json_body(self, body: Any) -> "HaloRequest":
        """Set JSON body for REST (application/json) requests."""
        self._json_body = body
        return self

    # --- Execution ---

    def _build_headers(self, include_content_type: bool = True) -> dict[str, str]:
        txn = (
            f"{self._transaction_id}-{uuid.uuid4()}"
            if self._transaction_id
            else str(uuid.uuid4())
        )
        headers = {
            "Accept": "application/json",
            "transaction-id": txn,
            "authorization": f"Bearer {self._auth_token}",
            "contexttoken": f"Bearer {self._context_token}",
        }
        if include_content_type:
            headers["Content-Type"] = "application/json"
        headers.update(self._extra_headers)
        return headers

    def execute(self) -> dict[str, Any]:
        """Execute the request. Raises on HTTP or GraphQL errors."""
        if not self._query_str:
            raise ValueError(f"No query set for operation '{self._operation_name}'")

        payload = {
            "operationName": self._operation_name,
            "query": self._query_str,
            "variables": self._variables,
        }

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                GRAPHQL_ENDPOINT, headers=self._build_headers(), json=payload
            )
            if resp.status_code == 401:
                raise HaloTokenExpiredError(
                    self._operation_name, ["HTTP 401 Unauthorized"]
                )
            resp.raise_for_status()
            data = resp.json()

        if "errors" in data:
            _check_for_auth_errors(self._operation_name, data)

        if self._cleaner_name:
            return clean_response(self._cleaner_name, data)

        return data

    def execute_form_post(self, path: str) -> dict[str, Any]:
        """Execute a REST POST with multipart/form-data to the orchestration API."""
        if not self._form_data:
            raise ValueError(f"No form data set for operation '{self._operation_name}'")

        url = f"{ORCHESTRATION_ENDPOINT}{path}"
        # (None, value) tuples tell httpx to send multipart form fields (not files)
        fields = {k: (None, v) for k, v in self._form_data.items()}

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                url,
                headers=self._build_headers(include_content_type=False),
                files=fields,
            )
            if resp.status_code == 401:
                raise HaloTokenExpiredError(
                    self._operation_name, ["HTTP 401 Unauthorized"]
                )
            resp.raise_for_status()
            data = resp.json()

        if self._cleaner_name:
            return clean_response(self._cleaner_name, data)

        return data

    def execute_rest_post(self, path: str) -> Any:
        """Execute a REST POST with application/json to the orchestration API."""
        if self._json_body is None:
            raise ValueError(f"No JSON body set for operation '{self._operation_name}'")

        url = f"{ORCHESTRATION_ENDPOINT}{path}"

        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                url, headers=self._build_headers(), json=self._json_body
            )
            if resp.status_code == 401:
                raise HaloTokenExpiredError(
                    self._operation_name, ["HTTP 401 Unauthorized"]
                )
            resp.raise_for_status()
            data = resp.json()

        if self._cleaner_name:
            return clean_response(self._cleaner_name, data)

        return data


def upload_to_s3(presigned_url: str, file_bytes: bytes, content_type: str) -> None:
    """Upload raw file bytes to an S3 presigned URL (no Halo auth)."""
    with httpx.Client(timeout=120.0) as client:
        resp = client.put(
            presigned_url,
            content=file_bytes,
            headers={"Content-Type": content_type},
        )
        resp.raise_for_status()
