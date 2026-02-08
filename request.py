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


class HaloAPIError(Exception):
    """Raised when the Halo GraphQL API returns errors."""

    def __init__(self, operation: str, messages: list[str]):
        self.operation = operation
        self.messages = messages
        super().__init__(f"Halo API error in '{operation}': {'; '.join(messages)}")


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

    # --- Execution ---

    def _build_headers(self) -> dict[str, str]:
        txn = (
            f"{self._transaction_id}-{uuid.uuid4()}"
            if self._transaction_id
            else str(uuid.uuid4())
        )
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "transaction-id": txn,
            "authorization": f"Bearer {self._auth_token}",
            "contexttoken": f"Bearer {self._context_token}",
        }
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
            resp.raise_for_status()
            data = resp.json()

        if "errors" in data:
            messages = [e.get("message", "Unknown error") for e in data["errors"]]
            raise HaloAPIError(self._operation_name, messages)

        if self._cleaner_name:
            return clean_response(self._cleaner_name, data)

        return data
