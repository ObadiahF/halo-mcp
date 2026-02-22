# Halo LMS MCP Server

MCP server that exposes Grand Canyon University's Halo LMS APIs as tools for AI agents. Provides access to classes, grades, discussions, announcements, inbox messages, notifications, assignment submissions, and user profiles.

## Setup

### 1. Install dependencies

```bash
cd HaloMCP
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure tokens

Copy the example config and fill in your tokens:

```bash
cp config.example.json config.json
```

Edit `config.json` with your Halo auth and context tokens (without the `Bearer` prefix — it's added automatically):

```json
{
  "authToken": "eyJ...",
  "contextToken": "eyJ...",
  "transactionId": "tenant-uuid-user-uuid"
}
```

Alternatively, set environment variables (these override `config.json`):

```bash
export HALO_AUTH_TOKEN="eyJ..."
export HALO_CONTEXT_TOKEN="eyJ..."
export HALO_TRANSACTION_ID="..."
```

## Running

### Claude Code (stdio)

Add to your Claude Code MCP config (`~/.claude/settings.json` or project `.mcp.json`):

```json
{
  "mcpServers": {
    "halo-lms": {
      "command": "python",
      "args": ["-m", "HaloMCP"],
      "cwd": "/path/to/HaloMCP"
    }
  }
}
```

### Direct (stdio)

```bash
python -m HaloMCP
```

### Docker (SSE on port 8000)

```bash
docker compose up -d
```

Then add it to Claude Code CLI:

```bash
claude mcp add --transport sse halo-lms http://localhost:8000/sse
```

The Docker container bind-mounts `config.json` and your home directory (read-only) from the host, so file uploads via `file_path` work the same as stdio mode. After updating tokens, restart with `docker compose restart`.

## Token Expiry

Halo uses Azure AD SSO with encrypted JWE tokens — they **cannot be refreshed programmatically**. When tokens expire, the server gives a clear error with instructions:

```
⚠️ TOKEN EXPIRED
Your Halo auth tokens have expired or are invalid.

To get fresh tokens:
  1. Log into https://halo.gcu.edu in your browser
  2. Open DevTools → Application → Cookies (or Network tab)
  3. Copy the new authToken and contextToken values
  4. Update config.json (or set HALO_AUTH_TOKEN / HALO_CONTEXT_TOKEN env vars)
  5. Call the reload_tokens tool (or restart the server)
```

Use `check_tokens` to verify your tokens are working, and `reload_tokens` to hot-reload new tokens from `config.json` without restarting.

## Available Tools

| Tool | Description |
|------|-------------|
| `list_classes` | List all enrolled course classes (call first to populate cache) |
| `view_assignments` | View assignments organized by unit for a class |
| `grades` | Get grade overview for a class |
| `discussions` | List discussion forums for a class |
| `forum_posts` | Get posts from a discussion forum |
| `announcements` | Get announcements for a class |
| `inbox` | List all inbox threads |
| `inbox_posts` | Get messages from an inbox thread |
| `message_teacher` | Send a message in an inbox thread |
| `notifications` | Get unread notification counts |
| `user` | Get user profile by ID |
| `upload_assignment_file` | Upload a file to an assignment (absolute file path) |
| `submit_assignment` | Submit an assignment for grading |
| `check_tokens` | Validate current auth tokens are working |
| `reload_tokens` | Hot-reload tokens from config.json without restarting |
