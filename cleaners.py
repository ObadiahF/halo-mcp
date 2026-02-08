"""
Response cleaners for Halo API endpoints.

Each cleaner takes raw API response JSON and returns a minimal, token-efficient
object suitable for AI agent tool responses. Strips __typename, nulls, empty
arrays, redundant IDs, and HTML tags.
"""

import re
from typing import Any


def _strip_html(text: str) -> str:
    """Remove HTML tags and decode common entities."""
    if not text:
        return ""
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</?p>', '\n', text)
    text = re.sub(r'</?(?:ol|ul|li|div|span)(?:\s[^>]*)?>',  '', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&#160;', ' ')
    text = text.replace('&rsquo;', "'").replace('&#39;', "'")
    text = text.replace('&ldquo;', '"').replace('&rdquo;', '"')
    text = text.replace('&#34;', '"').replace('&quot;', '"')
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    # Collapse whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _user_name(user: dict) -> str:
    """Extract display name from a user object."""
    if not user:
        return "Unknown"
    name = user.get("preferredFirstName") or user.get("firstName", "")
    return f"{name} {user.get('lastName', '')}".strip() or "Unknown"


def _date_short(date_str: str) -> str:
    """Shorten ISO date to YYYY-MM-DD."""
    if not date_str:
        return None
    return date_str[:10]


# ==================== Individual Cleaners ====================


def clean_list_classes(raw: dict) -> dict:
    """Clean list-classes response to essential fields."""
    classes = (raw.get("data", {})
               .get("getCourseClassesForUser", {})
               .get("courseClasses", []))

    return {"classes": [
        {
            "id": c["id"],
            "slug": c["slugId"],
            "name": c["name"],
            "courseCode": c.get("courseCode"),
            "stage": c["stage"],
            "modality": c["modality"],
            "startDate": _date_short(c["startDate"]),
            "endDate": _date_short(c["endDate"]),
            "currentTopic": next(
                (u["title"] for u in c.get("units", []) if u.get("current")),
                None
            ),
            "instructor": _user_name(
                c["instructors"][0].get("user") if c.get("instructors") else None
            ),
        }
        for c in classes
    ]}


def clean_class_details(raw: dict) -> dict:
    """Clean class-details response."""
    cls = raw.get("data", {}).get("currentClass", {})
    if not cls:
        return {"error": "No class data"}

    return {
        "id": cls["id"],
        "slug": cls["slugId"],
        "name": cls["name"],
        "courseCode": cls.get("courseCode"),
        "classCode": cls.get("classCode"),
        "stage": cls["stage"],
        "modality": cls["modality"],
        "credits": cls.get("credits"),
        "degreeLevel": cls.get("degreeLevel"),
        "startDate": _date_short(cls["startDate"]),
        "endDate": _date_short(cls["endDate"]),
        "description": cls.get("description", "")[:200],
        "units": [
            {
                "sequence": u["sequence"],
                "title": u["title"],
                "current": u.get("current", False),
                "startDate": _date_short(u.get("startDate", "")),
                "endDate": _date_short(u.get("endDate", "")),
                "assessments": [
                    {
                        k: v for k, v in {
                            "title": a["title"],
                            "type": a.get("type"),
                            "points": a.get("points"),
                            "dueDate": _date_short(a.get("dueDate", "")),
                            "description": _strip_html(a.get("description", ""))[:300],
                            "rubric": a["rubric"]["name"] if a.get("rubric") else None,
                            "attachments": [
                                att["title"] for att in a.get("attachments", [])
                            ] or None,
                        }.items() if v is not None and v != []
                    }
                    for a in u.get("assessments", [])
                ],
            }
            for u in cls.get("units", [])
        ],
        "instructors": [
            {
                "name": _user_name(i.get("user")),
                "role": i.get("roleName"),
            }
            for i in cls.get("instructors", [])
        ],
        "studentCount": len(cls.get("students", [])),
        "holidays": [
            {
                "title": h["title"],
                "startDate": _date_short(h["startDate"]),
                "duration": h.get("duration"),
            }
            for h in cls.get("holidays", [])
        ],
    }


def clean_grades(raw: dict) -> dict:
    """Clean grades response to scores and status."""
    overviews = raw.get("data", {}).get("gradeOverview", [])
    if not overviews:
        return {"grades": [], "finalGrade": None}

    overview = overviews[0]
    final = overview.get("finalGrade", {})

    return {
        "finalGrade": {
            "value": final.get("gradeValue"),
            "points": final.get("finalPoints"),
            "maxPoints": final.get("maxPoints"),
            "published": final.get("isPublished", False),
        } if final else None,
        "assessments": [
            {
                "title": g.get("assessment", {}).get("title"),
                "type": g.get("assessment", {}).get("type"),
                "points": g.get("finalPoints"),
                "maxPoints": g.get("assessment", {}).get("points"),
                "dueDate": _date_short(g.get("dueDate")),
                "status": g.get("status"),
                "comment": _strip_html(
                    (g.get("finalComment") or {}).get("comment", "")
                ) or None,
            }
            for g in overview.get("grades", [])
        ],
    }


def clean_discussions(raw: dict) -> dict:
    """Clean discussions response."""
    forums = raw.get("data", {}).get("allDQForCourseClass", [])

    return {"forums": [
        {
            "forumId": f["forumId"],
            "title": f["title"],
            "type": f["forumType"],
            "totalPosts": f.get("totalPosts", 0),
            "active": f.get("active", False),
            "startDate": _date_short(f.get("startDate")),
            "dueDate": _date_short(f.get("dueDate")),
            "description": _strip_html(f.get("description", ""))[:150] or None,
        }
        for f in forums
    ]}


def clean_forum_posts(raw: dict) -> dict:
    """Clean forum-posts response."""
    posts = raw.get("data", {}).get("Posts", [])

    return {"posts": [
        {
            "id": p["id"],
            "author": _user_name(p.get("createdBy", {}).get("user")),
            "role": p.get("createdBy", {}).get("baseRoleName"),
            "date": _date_short(p.get("publishDate")),
            "content": _strip_html(p.get("content", "")),
            "tags": [t["tag"] for t in p.get("postTags", [])],
            "parentPostId": p.get("parentPostId"),
            "hasReplies": p.get("hasChildren", False),
        }
        for p in posts
    ]}


def clean_announcements(raw: dict) -> dict:
    """Clean announcements response."""
    data = raw.get("data", {}).get("announcements", {})

    # Can be a single object or list
    if isinstance(data, list):
        all_posts = []
        for ann in data:
            all_posts.extend(ann.get("posts", []))
    else:
        all_posts = data.get("posts", []) if data else []

    return {"announcements": [
        {
            "id": p["id"],
            "title": p.get("title"),
            "author": _user_name(p.get("createdBy", {}).get("user")),
            "date": _date_short(p.get("publishDate")),
            "content": _strip_html(p.get("content", "")),
            "requiresAck": p.get("isAcknowledge", False),
            "expiryDate": _date_short(p.get("expiryDate")),
        }
        for p in all_posts
    ]}


def clean_inbox(raw: dict) -> dict:
    """Clean inbox response."""
    panels = raw.get("data", {}).get("getInboxLeftPanel", [])

    threads = []
    for panel in panels:
        for forum in panel.get("forums", []):
            last_post = forum.get("lastPost") or {}
            post = last_post.get("post") or {}
            author = post.get("createdBy", {}).get("user") if post else {}

            threads.append({
                "forumId": forum["forumId"],
                "courseClassId": panel["courseClassId"],
                "lastMessage": {
                    "author": _user_name(author),
                    "date": _date_short(post.get("publishDate")),
                    "preview": _strip_html(post.get("content", ""))[:150],
                } if post else None,
            })

    return {"threads": threads}


def clean_inbox_posts(raw: dict) -> dict:
    """Clean inbox-posts response."""
    posts = raw.get("data", {}).get("getPostsForInboxForum", [])

    return {"messages": [
        {
            "id": p["id"],
            "author": _user_name(p.get("createdBy", {}).get("user")),
            "role": p.get("createdBy", {}).get("baseRoleName"),
            "date": _date_short(p.get("publishDate")),
            "content": _strip_html(p.get("content", "")),
            "wordCount": p.get("wordCount"),
        }
        for p in posts
    ]}


def clean_notifications(raw: dict) -> dict:
    """Clean notifications response (combined forum + inbox)."""
    result = {}

    # Forum notifications
    forum_data = raw.get("forum", {}).get("data", {}).get("classes", [])
    for notification in forum_data:
        forum_types = notification.get("forumTypes", {})
        for ftype in ["ANNOUNCEMENTS", "CQ", "DQ", "IDQ", "INBOX", "GROUP"]:
            ft = forum_types.get(ftype)
            if ft:
                classes = ft.get("classes", [])
                count = sum(int(c.get("count", 0) or 0) for c in classes)
                if count > 0:
                    result[ftype] = count

    # Inbox notifications
    inbox_data = raw.get("inbox", {}).get("data", {}).get("classes", [])
    inbox_total = 0
    for notification in inbox_data:
        inbox = notification.get("forumTypes", {}).get("INBOX", {})
        inbox_total += int(inbox.get("count", 0) or 0)
    if inbox_total > 0:
        result["INBOX_TOTAL"] = inbox_total

    return {"unread": result} if result else {"unread": "none"}


def clean_user(raw: dict) -> dict:
    """Clean user response."""
    user = raw.get("data", {}).get("getUserById", {})
    if not user:
        return {"error": "No user data"}

    return {
        "id": user["id"],
        "name": _user_name(user),
        "sourceId": user.get("sourceId"),
    }


# ==================== Registry ====================

CLEANERS = {
    "list-classes": clean_list_classes,
    "class-details": clean_class_details,
    "grades": clean_grades,
    "discussions": clean_discussions,
    "forum-posts": clean_forum_posts,
    "announcements": clean_announcements,
    "inbox": clean_inbox,
    "inbox-posts": clean_inbox_posts,
    "notifications": clean_notifications,
    "user": clean_user,
}


def clean_response(test_name: str, raw: dict) -> dict:
    """Clean a raw API response using the appropriate cleaner."""
    cleaner = CLEANERS.get(test_name)
    if not cleaner:
        return raw
    return cleaner(raw)
