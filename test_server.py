#!/usr/bin/env python3
"""
HaloMCP Server Test Suite - Tests all MCP tools via the HaloRequest builder.

Validates that:
  1. Every tool's request builds and executes correctly
  2. Cleaners auto-apply and produce expected fields
  3. Auth + context tokens are applied automatically

Usage:
    python -m HaloMCP.test_server
    python -m HaloMCP.test_server --verbose
"""

import json
import sys
import time
from pathlib import Path

from .request import HaloRequest, HaloAPIError
from .cleaners import clean_notifications
from . import queries, class_cache


# ==================== Test State ====================

# Populated dynamically as tests run (dependency chain)
STATE = {
    "user_id": "b07ca1b4-e0aa-4a16-a9b4-698c80f8f24b",
    "slug": None,
    "class_id": None,
    "forum_id": None,
    "inbox_forum_id": None,
}


class TestResult:
    def __init__(self, name, passed, message="", duration=0, cleaned=None, raw=None):
        self.name = name
        self.passed = passed
        self.message = message
        self.duration = duration
        self.cleaned = cleaned
        self.raw = raw

    def __str__(self):
        status = "PASS" if self.passed else "FAIL"
        dur = f" ({self.duration:.2f}s)" if self.duration else ""
        msg = f" - {self.message}" if self.message else ""
        return f"  [{status}] {self.name}{dur}{msg}"


# ==================== Individual Tests ====================


def test_list_classes(verbose=False):
    """Test: list_classes tool."""
    start = time.time()
    try:
        raw = (
            HaloRequest("getCourseClassesForUser")
            .query(queries.GET_COURSE_CLASSES_FOR_USER)
            .variables({"pgNum": 1, "pgSize": 50})
            .execute()
        )
        cleaned = (
            HaloRequest("getCourseClassesForUser")
            .query(queries.GET_COURSE_CLASSES_FOR_USER)
            .variables({"pgNum": 1, "pgSize": 50})
            .cleaner("list-classes")
            .execute()
        )
        duration = time.time() - start

        classes = cleaned.get("classes", [])
        if not classes:
            return TestResult("list-classes", False, "No classes returned", duration)

        class_cache.populate(classes)
        STATE["slug"] = classes[0]["slug"]

        if verbose:
            for c in classes:
                print(f"    {c['slug']} - {c['name']}")

        return TestResult("list-classes", True,
                          f"{len(classes)} classes", duration, cleaned, raw)
    except Exception as e:
        return TestResult("list-classes", False, str(e), time.time() - start)


def test_view_assignments(verbose=False):
    """Test: class_details tool."""
    slug = STATE.get("slug")
    if not slug:
        return TestResult("view-assignments", False, "No slug (list-classes failed?)")

    start = time.time()
    try:
        raw = (
            HaloRequest("CurrentClass")
            .query(queries.CURRENT_CLASS)
            .variables({"slugId": slug, "isStudent": True})
            .class_slug(slug)
            .execute()
        )
        cleaned = (
            HaloRequest("CurrentClass")
            .query(queries.CURRENT_CLASS)
            .variables({"slugId": slug, "isStudent": True})
            .class_slug(slug)
            .cleaner("class-details")
            .execute()
        )
        duration = time.time() - start

        STATE["class_id"] = cleaned.get("id")

        expected = ["id", "slug", "name", "stage", "modality", "startDate", "endDate"]
        missing = [f for f in expected if f not in cleaned]
        if missing:
            return TestResult("view-assignments", False,
                              f"Missing fields: {missing}", duration, cleaned, raw)

        if verbose:
            print(f"    {cleaned['name']} ({cleaned['id']})")

        return TestResult("view-assignments", True,
                          cleaned["name"], duration, cleaned, raw)
    except Exception as e:
        return TestResult("view-assignments", False, str(e), time.time() - start)


def test_grades(verbose=False):
    """Test: grades tool."""
    slug = STATE.get("slug")
    if not slug:
        return TestResult("grades", False, "No slug available")

    start = time.time()
    try:
        raw = (
            HaloRequest("GradeOverview")
            .query(queries.GRADE_OVERVIEW)
            .variables({"courseClassSlugId": slug, "courseClassUserIds": ""})
            .class_slug(slug)
            .execute()
        )
        cleaned = (
            HaloRequest("GradeOverview")
            .query(queries.GRADE_OVERVIEW)
            .variables({"courseClassSlugId": slug, "courseClassUserIds": ""})
            .class_slug(slug)
            .cleaner("grades")
            .execute()
        )
        duration = time.time() - start

        assessments = cleaned.get("assessments", [])

        if verbose:
            fg = cleaned.get("finalGrade") or {}
            print(f"    Final: {fg.get('value', 'N/A')}, {len(assessments)} assessments")

        return TestResult("grades", True,
                          f"{len(assessments)} assessments", duration, cleaned, raw)
    except Exception as e:
        return TestResult("grades", False, str(e), time.time() - start)


def test_discussions(verbose=False):
    """Test: discussions tool."""
    class_id = STATE.get("class_id")
    if not class_id:
        return TestResult("discussions", False, "No class_id available")

    start = time.time()
    try:
        raw = (
            HaloRequest("AllDQForCourseClass")
            .query(queries.ALL_DQ_FOR_COURSE_CLASS)
            .variables({"courseClassId": class_id, "sortBy": "startDate",
                        "pgNum": 1, "pgSize": 150})
            .course_class(class_id)
            .execute()
        )
        cleaned = (
            HaloRequest("AllDQForCourseClass")
            .query(queries.ALL_DQ_FOR_COURSE_CLASS)
            .variables({"courseClassId": class_id, "sortBy": "startDate",
                        "pgNum": 1, "pgSize": 150})
            .course_class(class_id)
            .cleaner("discussions")
            .execute()
        )
        duration = time.time() - start

        forums = cleaned.get("forums", [])
        if forums:
            STATE["forum_id"] = forums[0]["forumId"]

        if verbose:
            for f in forums:
                print(f"    {f['title']} ({f['forumId']})")

        return TestResult("discussions", True,
                          f"{len(forums)} forums", duration, cleaned, raw)
    except Exception as e:
        return TestResult("discussions", False, str(e), time.time() - start)


def test_forum_posts(verbose=False):
    """Test: forum_posts tool."""
    forum_id = STATE.get("forum_id")
    if not forum_id:
        return TestResult("forum-posts", False, "No forum_id available")

    start = time.time()
    try:
        raw = (
            HaloRequest("getDiscussionForumPosts")
            .query(queries.GET_DISCUSSION_FORUM_POSTS)
            .variables({"forumId": forum_id, "postId": None,
                        "depthStart": None, "depthEnd": 5})
            .execute()
        )
        cleaned = (
            HaloRequest("getDiscussionForumPosts")
            .query(queries.GET_DISCUSSION_FORUM_POSTS)
            .variables({"forumId": forum_id, "postId": None,
                        "depthStart": None, "depthEnd": 5})
            .cleaner("forum-posts")
            .execute()
        )
        duration = time.time() - start

        posts = cleaned.get("posts", [])

        if verbose:
            print(f"    {len(posts)} posts in forum")

        return TestResult("forum-posts", True,
                          f"{len(posts)} posts", duration, cleaned, raw)
    except Exception as e:
        return TestResult("forum-posts", False, str(e), time.time() - start)


def test_announcements(verbose=False):
    """Test: announcements tool."""
    class_id = STATE.get("class_id")
    if not class_id:
        return TestResult("announcements", False, "No class_id available")

    start = time.time()
    try:
        raw = (
            HaloRequest("GetAnnouncementsStudent")
            .query(queries.GET_ANNOUNCEMENTS_STUDENT)
            .variables({"courseClassId": class_id})
            .course_class(class_id)
            .execute()
        )
        cleaned = (
            HaloRequest("GetAnnouncementsStudent")
            .query(queries.GET_ANNOUNCEMENTS_STUDENT)
            .variables({"courseClassId": class_id})
            .course_class(class_id)
            .cleaner("announcements")
            .execute()
        )
        duration = time.time() - start

        ann = cleaned.get("announcements", [])

        return TestResult("announcements", True,
                          f"{len(ann)} announcements", duration, cleaned, raw)
    except Exception as e:
        return TestResult("announcements", False, str(e), time.time() - start)


def test_inbox(verbose=False):
    """Test: inbox tool."""
    start = time.time()
    try:
        raw = (
            HaloRequest("GetInboxLeftPanel")
            .query(queries.GET_INBOX_LEFT_PANEL)
            .variables({})
            .execute()
        )
        cleaned = (
            HaloRequest("GetInboxLeftPanel")
            .query(queries.GET_INBOX_LEFT_PANEL)
            .variables({})
            .cleaner("inbox")
            .execute()
        )
        duration = time.time() - start

        threads = cleaned.get("threads", [])
        if threads and not STATE.get("inbox_forum_id"):
            STATE["inbox_forum_id"] = threads[0]["forumId"]

        if verbose:
            print(f"    {len(threads)} threads")

        return TestResult("inbox", True,
                          f"{len(threads)} threads", duration, cleaned, raw)
    except Exception as e:
        return TestResult("inbox", False, str(e), time.time() - start)


def test_inbox_posts(verbose=False):
    """Test: inbox_posts tool."""
    forum_id = STATE.get("inbox_forum_id")
    if not forum_id:
        return TestResult("inbox-posts", False, "No inbox_forum_id available")

    start = time.time()
    try:
        raw = (
            HaloRequest("getPostsByInboxForumId")
            .query(queries.GET_POSTS_BY_INBOX_FORUM_ID)
            .variables({"forumId": forum_id, "pgNum": 1, "pgSize": 20})
            .execute()
        )
        cleaned = (
            HaloRequest("getPostsByInboxForumId")
            .query(queries.GET_POSTS_BY_INBOX_FORUM_ID)
            .variables({"forumId": forum_id, "pgNum": 1, "pgSize": 20})
            .cleaner("inbox-posts")
            .execute()
        )
        duration = time.time() - start

        messages = cleaned.get("messages", [])

        return TestResult("inbox-posts", True,
                          f"{len(messages)} messages", duration, cleaned, raw)
    except Exception as e:
        return TestResult("inbox-posts", False, str(e), time.time() - start)


def test_notifications(verbose=False):
    """Test: notifications tool (2 requests combined)."""
    class_id = STATE.get("class_id")
    if not class_id:
        return TestResult("notifications", False, "No class_id available")

    start = time.time()
    try:
        forum_raw = (
            HaloRequest("GetForumNotifications")
            .query(queries.GET_FORUM_NOTIFICATIONS)
            .variables({"classId": class_id})
            .execute()
        )
        inbox_raw = (
            HaloRequest("GetInboxNotifications")
            .query(queries.GET_INBOX_NOTIFICATIONS)
            .variables({"fetchCounts": True})
            .execute()
        )
        duration = time.time() - start

        combined_raw = {"forum": forum_raw, "inbox": inbox_raw}
        cleaned = clean_notifications(combined_raw)

        unread = cleaned.get("unread", {})
        summary = unread if unread != "none" else "none"

        return TestResult("notifications", True,
                          f"unread: {summary}", duration, cleaned, combined_raw)
    except Exception as e:
        return TestResult("notifications", False, str(e), time.time() - start)


def test_user(verbose=False):
    """Test: user tool."""
    user_id = STATE.get("user_id")
    if not user_id:
        return TestResult("user", False, "No user_id configured")

    start = time.time()
    try:
        raw = (
            HaloRequest("getUserById")
            .query(queries.GET_USER_BY_ID)
            .variables({"userId": user_id})
            .execute()
        )
        cleaned = (
            HaloRequest("getUserById")
            .query(queries.GET_USER_BY_ID)
            .variables({"userId": user_id})
            .cleaner("user")
            .execute()
        )
        duration = time.time() - start

        if "error" in cleaned:
            return TestResult("user", False, cleaned["error"], duration, cleaned, raw)

        if verbose:
            print(f"    {cleaned['name']} ({cleaned['id']})")

        return TestResult("user", True,
                          cleaned["name"], duration, cleaned, raw)
    except Exception as e:
        return TestResult("user", False, str(e), time.time() - start)


# ==================== Runner ====================

ALL_TESTS = [
    ("list-classes",  test_list_classes),
    ("view-assignments", test_view_assignments),
    ("grades",        test_grades),
    ("discussions",   test_discussions),
    ("forum-posts",   test_forum_posts),
    ("announcements", test_announcements),
    ("inbox",         test_inbox),
    ("inbox-posts",   test_inbox_posts),
    ("notifications", test_notifications),
    ("user",          test_user),
]


def run_tests(verbose=False, output_dir=None):
    """Run all MCP tool tests."""
    if not output_dir:
        output_dir = Path(__file__).parent / "test_output"
    else:
        output_dir = Path(output_dir)
    cleaned_dir = output_dir / "cleaned"
    raw_dir = output_dir / "raw"
    cleaned_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  HaloMCP Server Test Suite")
    print(f"  Testing {len(ALL_TESTS)} MCP tools via HaloRequest builder")
    print("=" * 60)
    print()

    results = []
    size_comparisons = []
    total_start = time.time()

    for name, test_fn in ALL_TESTS:
        print(f"  Testing {name}...", end="", flush=True)
        result = test_fn(verbose=verbose)
        results.append(result)

        # Dump JSON responses
        if result.raw is not None:
            raw_json = json.dumps(result.raw, indent=2)
            with open(raw_dir / f"{name}.json", "w") as f:
                f.write(raw_json)
            raw_size = len(raw_json)
        else:
            raw_size = 0

        if result.cleaned is not None:
            cleaned_json = json.dumps(result.cleaned, indent=2)
            with open(cleaned_dir / f"{name}.json", "w") as f:
                f.write(cleaned_json)
            cleaned_size = len(cleaned_json)
        else:
            cleaned_size = 0

        if raw_size > 0:
            reduction = ((raw_size - cleaned_size) / raw_size * 100)
            size_comparisons.append((name, raw_size, cleaned_size, reduction))

        print(f"\r{result}")

    total_duration = time.time() - total_start

    # Summary
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

    # Size comparison table
    if size_comparisons:
        print()
        print("  Size Comparison (raw vs cleaned):")
        print(f"  {'Tool':<20} {'Raw':>8} {'Cleaned':>8} {'Saved':>8} {'Reduction':>10}")
        print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")

        total_raw = 0
        total_cleaned = 0
        for name, raw_size, cleaned_size, reduction in size_comparisons:
            saved = raw_size - cleaned_size
            total_raw += raw_size
            total_cleaned += cleaned_size
            print(f"  {name:<20} {raw_size:>7}B {cleaned_size:>7}B "
                  f"{saved:>7}B {reduction:>8.1f}%")

        total_saved = total_raw - total_cleaned
        total_reduction = ((total_raw - total_cleaned) / total_raw * 100) if total_raw else 0
        print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")
        print(f"  {'TOTAL':<20} {total_raw:>7}B {total_cleaned:>7}B "
              f"{total_saved:>7}B {total_reduction:>8.1f}%")

    print()
    print(f"  Raw responses:     {raw_dir}/")
    print(f"  Cleaned responses: {cleaned_dir}/")
    print()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test HaloMCP server tools")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed output for each test")
    parser.add_argument("--output-dir", "-o", default=None,
                        help="Directory for JSON response dumps")
    args = parser.parse_args()

    sys.exit(run_tests(verbose=args.verbose, output_dir=args.output_dir))
