"""
Halo LMS MCP Server -- Exposes Halo LMS APIs as MCP tools.

Run with:
    fastmcp run HaloMCP/server.py:mcp
    python -m HaloMCP.server
    docker compose up  (SSE transport on port 8000)
"""

import os
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from HaloMCP.request import HaloRequest, HaloAPIError, HaloTokenExpiredError
from HaloMCP.cleaners import clean_notifications
from HaloMCP.submission import upload_assignment_file_flow, submit_assignment_flow
from HaloMCP.config import reload_config as _reload_config
from HaloMCP.auth import setup_session as _setup_session, refresh_tokens as _refresh_tokens
from HaloMCP import queries, class_cache

@asynccontextmanager
async def lifespan(server):
    """Set up session on startup for automatic token refresh."""
    try:
        result = _setup_session()
        print(f"[Halo MCP] Session ready — expires {result.get('expires', 'unknown')}")
    except Exception as e:
        print(f"[Halo MCP] Session setup skipped: {e}")
        print("[Halo MCP] Call the 'setup_session' tool manually after providing valid tokens.")
    yield {}


mcp = FastMCP(
    name="Halo LMS",
    lifespan=lifespan,
    instructions=(
        "Halo LMS API server for Grand Canyon University. "
        "Provides access to classes, grades, discussions, announcements, "
        "inbox messages, notifications, and user profiles. "
        "All responses are cleaned for token efficiency."
    ),
)


def _handle_error(e: Exception) -> None:
    """Convert API/HTTP errors into MCP ToolErrors."""
    if isinstance(e, HaloTokenExpiredError):
        raise ToolError(
            f"⚠️ TOKEN EXPIRED — {'; '.join(e.messages)}\n\n{e.help_text}"
        )
    if isinstance(e, HaloAPIError):
        raise ToolError(f"Halo API error: {'; '.join(e.messages)}")
    raise ToolError(f"Request failed: {e}")


# ==================== Course/Class Tools ====================


@mcp.tool(
    description=(
        "List all enrolled course classes for the authenticated user. "
        "Returns class names, codes, stages, dates, current topics, and instructors. "
        "IMPORTANT: Call this first before using other class tools — it populates "
        "the class cache so you can reference classes by course code (e.g. 'CST-323')."
    ),
    tags={"courses"},
)
def list_classes(page: int = 1, page_size: int = 50) -> dict:
    """List all enrolled course classes."""
    try:
        result = (
            HaloRequest("getCourseClassesForUser")
            .query(queries.GET_COURSE_CLASSES_FOR_USER)
            .variables({"pgNum": page, "pgSize": page_size})
            .cleaner("list-classes")
            .execute()
        )
        class_cache.populate(result.get("classes", []))
        return result
    except Exception as e:
        _handle_error(e)


@mcp.tool(
    description=(
        "View all assignments for a course class organized by unit/topic. "
        "Pass a course code (e.g. 'CST-321'), class name, or slug. "
        "Returns units with assignments (titles, types, points, due dates, descriptions), "
        "instructors, holidays, and student count."
    ),
    tags={"courses"},
)
def view_assignments(class_ref: str, is_student: bool = True) -> dict:
    """View assignments by unit. Accepts course code, name, or slug."""
    slug = class_cache.resolve_slug(class_ref)
    try:
        return (
            HaloRequest("CurrentClass")
            .query(queries.CURRENT_CLASS)
            .variables({"slugId": slug, "isStudent": is_student})
            .class_slug(slug)
            .cleaner("class-details")
            .execute()
        )
    except Exception as e:
        _handle_error(e)


# ==================== Grading Tools ====================


@mcp.tool(
    description=(
        "Get grade overview for a course class. "
        "Pass a course code (e.g. 'CST-321'), class name, or slug. "
        "Call list_classes first to populate the class cache. "
        "Returns final grade, individual assessment scores, statuses, and comments."
    ),
    tags={"grades"},
)
def grades(class_ref: str) -> dict:
    """Get grade overview. Accepts course code, name, or slug."""
    slug = class_cache.resolve_slug(class_ref)
    try:
        return (
            HaloRequest("GradeOverview")
            .query(queries.GRADE_OVERVIEW)
            .variables({"courseClassSlugId": slug, "courseClassUserIds": ""})
            .class_slug(slug)
            .cleaner("grades")
            .execute()
        )
    except Exception as e:
        _handle_error(e)


# ==================== Forum/Discussion Tools ====================


@mcp.tool(
    description=(
        "List all discussion forums for a course class. "
        "Pass a course code (e.g. 'CST-321'), class name, or UUID. "
        "Returns forum IDs, titles, types, post counts, and due dates."
    ),
    tags={"discussions"},
)
def discussions(class_ref: str) -> dict:
    """List discussion forums. Accepts course code, name, or UUID."""
    class_id = class_cache.resolve_id(class_ref)
    try:
        return (
            HaloRequest("AllDQForCourseClass")
            .query(queries.ALL_DQ_FOR_COURSE_CLASS)
            .variables({
                "courseClassId": class_id,
                "sortBy": "startDate",
                "pgNum": 1,
                "pgSize": 150,
            })
            .course_class(class_id)
            .cleaner("discussions")
            .execute()
        )
    except Exception as e:
        _handle_error(e)


@mcp.tool(
    description=(
        "Get posts from a discussion forum. "
        "Returns post content, authors, roles, dates, tags, and reply structure."
    ),
    tags={"discussions"},
)
def forum_posts(forum_id: str, depth_end: int = 5) -> dict:
    """Get posts from a discussion forum by forum UUID."""
    try:
        return (
            HaloRequest("getDiscussionForumPosts")
            .query(queries.GET_DISCUSSION_FORUM_POSTS)
            .variables({
                "forumId": forum_id,
                "postId": None,
                "depthStart": None,
                "depthEnd": depth_end,
            })
            .cleaner("forum-posts")
            .execute()
        )
    except Exception as e:
        _handle_error(e)


# ==================== Announcements ====================


@mcp.tool(
    description=(
        "Get announcements for a course class. "
        "Pass a course code (e.g. 'CST-321'), class name, or UUID. "
        "Returns announcement titles, authors, dates, content, and acknowledgement status."
    ),
    tags={"announcements"},
)
def announcements(class_ref: str) -> dict:
    """Get announcements. Accepts course code, name, or UUID."""
    class_id = class_cache.resolve_id(class_ref)
    try:
        return (
            HaloRequest("GetAnnouncementsStudent")
            .query(queries.GET_ANNOUNCEMENTS_STUDENT)
            .variables({"courseClassId": class_id})
            .course_class(class_id)
            .cleaner("announcements")
            .execute()
        )
    except Exception as e:
        _handle_error(e)


# ==================== Inbox Tools ====================


@mcp.tool(
    description=(
        "Get inbox threads across all enrolled classes. "
        "Returns forum IDs, last message previews, and authors."
    ),
    tags={"inbox"},
)
def inbox() -> dict:
    """List all inbox threads."""
    try:
        return (
            HaloRequest("GetInboxLeftPanel")
            .query(queries.GET_INBOX_LEFT_PANEL)
            .variables({})
            .cleaner("inbox")
            .execute()
        )
    except Exception as e:
        _handle_error(e)


@mcp.tool(
    description=(
        "Get messages from an inbox thread. "
        "Returns message content, authors, roles, dates, and word counts."
    ),
    tags={"inbox"},
)
def inbox_posts(forum_id: str, page: int = 1, page_size: int = 20) -> dict:
    """Get messages from an inbox thread by forum UUID."""
    try:
        return (
            HaloRequest("getPostsByInboxForumId")
            .query(queries.GET_POSTS_BY_INBOX_FORUM_ID)
            .variables({"forumId": forum_id, "pgNum": page, "pgSize": page_size})
            .cleaner("inbox-posts")
            .execute()
        )
    except Exception as e:
        _handle_error(e)


@mcp.tool(
    description=(
        "Send a message to a teacher in an inbox thread. "
        "Requires a class reference (course code, name, or slug) and the forum ID "
        "of the inbox thread — get the forum ID from inbox() first. "
        "Content should be plain text; it will be wrapped in HTML automatically."
    ),
    tags={"inbox"},
)
def message_teacher(
    class_ref: str,
    forum_id: str,
    content: str,
    is_draft: bool = False,
) -> dict:
    """Send a message in an inbox thread. Get forum_id from inbox() first."""
    slug = class_cache.resolve_slug(class_ref)
    class_id = class_cache.resolve_id(class_ref)

    html_content = content if content.strip().startswith("<") else f"<p>{content}</p>"

    try:
        return (
            HaloRequest("message_teacher")
            .class_slug(slug)
            .course_class(class_id)
            .form_data({
                "content": html_content,
                "forumId": forum_id,
                "isDraft": str(is_draft).lower(),
                "extractLink": "true",
            })
            .execute_form_post("/api/v1/orchestrate/forum/post/send")
        )
    except Exception as e:
        _handle_error(e)


# ==================== Notification Tools ====================


@mcp.tool(
    description=(
        "Get unread notification counts by forum type "
        "(announcements, DQ, inbox, etc). "
        "Pass a course code (e.g. 'CST-321'), class name, or UUID. "
        "Combines forum and inbox notification data."
    ),
    tags={"notifications"},
)
def notifications(class_ref: str) -> dict:
    """Get notification counts. Accepts course code, name, or UUID."""
    class_id = class_cache.resolve_id(class_ref)
    try:
        forum_resp = (
            HaloRequest("GetForumNotifications")
            .query(queries.GET_FORUM_NOTIFICATIONS)
            .variables({"classId": class_id})
            .execute()
        )
        inbox_resp = (
            HaloRequest("GetInboxNotifications")
            .query(queries.GET_INBOX_NOTIFICATIONS)
            .variables({"fetchCounts": True})
            .execute()
        )
        return clean_notifications({"forum": forum_resp, "inbox": inbox_resp})
    except Exception as e:
        _handle_error(e)


# ==================== User Tools ====================


@mcp.tool(
    description=(
        "Get user profile information by user UUID. "
        "Returns name, source ID, and access groups."
    ),
    tags={"user"},
)
def user(user_id: str) -> dict:
    """Get user details by user UUID."""
    try:
        return (
            HaloRequest("getUserById")
            .query(queries.GET_USER_BY_ID)
            .variables({"userId": user_id})
            .cleaner("user")
            .execute()
        )
    except Exception as e:
        _handle_error(e)


# ==================== Assignment Submission Tools ====================


@mcp.tool(
    description=(
        "Upload a file and attach it to an assignment submission. "
        "Can be called multiple times to attach multiple files before submitting. "
        "Pass a course code (e.g. 'CST-321'), class name, or slug for the class. "
        "The assessment_id is the UUID of the assignment — get it from view_assignments. "
        "file_path must be an absolute path to a local file. "
        "After uploading all files, call submit_assignment to finalize."
    ),
    tags={"assignments"},
)
def upload_assignment_file(
    class_ref: str,
    assessment_id: str,
    file_path: str,
) -> dict:
    """Upload a file to an assignment. Call submit_assignment when all files are attached."""
    cls = class_cache.resolve(class_ref)
    if not cls:
        raise ToolError(f"Class not found: '{class_ref}'. Call list_classes first.")
    try:
        return upload_assignment_file_flow(
            class_id=cls["id"],
            slug=cls["slug"],
            assessment_id=assessment_id,
            file_path=file_path,
        )
    except Exception as e:
        _handle_error(e)


@mcp.tool(
    description=(
        "Finalize and submit an assignment for grading. "
        "Submits ALL files currently attached to the assignment. "
        "Upload files first with upload_assignment_file. "
        "Pass a course code (e.g. 'CST-321'), class name, or slug for the class. "
        "The assessment_id is the UUID of the assignment — get it from view_assignments. "
        "WARNING: This action is irreversible — it submits the assignment for grading."
    ),
    tags={"assignments"},
)
def submit_assignment(class_ref: str, assessment_id: str) -> dict:
    """Submit an assignment for grading. Upload files first with upload_assignment_file."""
    cls = class_cache.resolve(class_ref)
    if not cls:
        raise ToolError(f"Class not found: '{class_ref}'. Call list_classes first.")
    try:
        return submit_assignment_flow(
            class_id=cls["id"],
            class_name=cls["name"],
            slug=cls["slug"],
            assessment_id=assessment_id,
        )
    except Exception as e:
        _handle_error(e)


# ==================== Token Management Tools ====================


@mcp.tool(
    description=(
        "Check if the current Halo auth tokens are valid by making a lightweight API call. "
        "Returns token status. Use this to verify tokens after updating config.json."
    ),
    tags={"auth"},
)
def check_tokens() -> dict:
    """Validate current auth tokens against the Halo API."""
    try:
        result = (
            HaloRequest("getCourseClassesForUser")
            .query(queries.GET_COURSE_CLASSES_FOR_USER)
            .variables({"pgNum": 1, "pgSize": 1})
            .cleaner("list-classes")
            .execute()
        )
        classes = result.get("classes", [])
        return {
            "status": "valid",
            "message": f"Tokens are working. Found {len(classes)} class(es).",
        }
    except HaloTokenExpiredError as e:
        return {
            "status": "expired",
            "message": e.help_text,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error: {e}",
        }


@mcp.tool(
    description=(
        "Reload auth tokens from config.json or environment variables without restarting the server. "
        "Use this after updating config.json with fresh tokens. "
        "Automatically validates the new tokens after loading."
    ),
    tags={"auth"},
)
def reload_tokens() -> dict:
    """Reload tokens from config.json/env vars and validate them."""
    try:
        _reload_config()
    except ValueError as e:
        return {"status": "error", "message": f"Config error: {e}"}

    # Validate the newly loaded tokens
    return check_tokens()


@mcp.tool(
    description=(
        "Create a long-lived session for automatic token refresh. "
        "Call this ONCE after setting up config.json with valid tokens. "
        "Creates a session that lasts ~30 days. While the session is active, "
        "expired tokens are automatically refreshed — no manual intervention needed. "
        "When the session itself expires (~30 days), update tokens and call this again."
    ),
    tags={"auth"},
)
def setup_session() -> dict:
    """Create a session from current tokens for automatic refresh."""
    try:
        return _setup_session()
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool(
    description=(
        "Manually refresh auth tokens using the stored session cookie. "
        "This happens automatically when tokens expire during API calls, "
        "but you can call this proactively. Requires setup_session to have been called first."
    ),
    tags={"auth"},
)
def refresh() -> dict:
    """Manually refresh tokens using the session cookie."""
    try:
        result = _refresh_tokens()
        # Reload config to pick up new tokens
        _reload_config()
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ==================== Entry Point ====================


def main():
    """Run the MCP server. Set MCP_TRANSPORT=streamable-http for HTTP mode (Docker)."""
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    if transport == "stdio":
        mcp.run(transport=transport)
    else:
        mcp.run(transport=transport, host=host)


if __name__ == "__main__":
    main()
