# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HaloMCP is a Python MCP (Model Context Protocol) server that exposes GCU's Halo LMS APIs as tools for AI agents. It wraps Halo's GraphQL and REST APIs, providing 30+ tools for courses, grades, discussions, assignments, inbox, and user profiles.

## Commands

| Task | Command |
|------|---------|
| Install deps | `pip install -r requirements.txt` |
| Run server (stdio) | `python server.py` |
| Run API tests | `python test_server.py` |
| Run auth tests | `python test_auth.py` |
| Run tests verbose | `python test_server.py --verbose` |
| Docker build+run | `docker compose up -d --build` |

## Architecture

### Request Pipeline

All API calls flow through the **builder pattern** in `request.py`:

```
Tool (server.py) → HaloRequest().query(GQL).variables({}).cleaner("name").execute()
                         ↓
                  Auto-applies auth tokens from config
                         ↓
                  Hits GraphQL (gateway.halo.gcu.edu) or REST (orchestration.halo.gcu.edu)
                         ↓
                  On 401 → auto-refreshes tokens via session cookie (auth.py)
                         ↓
                  Applies named cleaner (cleaners.py) to strip noise for token efficiency
```

### Key Modules

- **`server.py`** — MCP tool definitions (FastMCP 2.0). Each tool resolves a class identifier via `class_cache.py`, builds a `HaloRequest`, and returns cleaned data.
- **`request.py`** — `HaloRequest` builder. Handles GraphQL queries, REST POSTs (JSON + multipart), auth header injection, and automatic token refresh on failure.
- **`auth.py`** — Token lifecycle: `setup_session()` creates a long-lived next-auth session cookie; `refresh_tokens()` uses that cookie to get fresh JWTs.
- **`cleaners.py`** — Named response processors that strip `__typename`, nulls, HTML tags, and redundant nesting to minimize token usage.
- **`submission.py`** — Two-phase assignment submission: upload file to S3 via presigned URL → submit assessment for grading.
- **`class_cache.py`** — In-memory fuzzy resolver so tools accept course codes ("CST-321"), names, slugs, or UUIDs.
- **`queries/`** — GraphQL query strings organized by domain (course, grading, forums, inbox, user, assignment).
- **`config.py`** — Loads config from `config.json` or environment variables (`HALO_AUTH_TOKEN`, `HALO_CONTEXT_TOKEN`, `HALO_TRANSACTION_ID`).

### Authentication Flow

1. User provides initial `authToken` + `contextToken` (from browser DevTools) in `config.json`
2. `setup_session()` (runs on server startup via lifespan) creates next-auth session cookies (~30 day validity)
3. When tokens expire, `refresh_tokens()` transparently fetches new JWTs using stored session cookies
4. Session cookies and tokens are persisted back to `config.json`

### Testing

Tests in `test_server.py` are end-to-end against the live Halo API (no mocks). They follow a dependency chain: `list_classes` → `view_assignments` → `grades` → `discussions` → etc. A valid `config.json` with active tokens is required to run tests.
