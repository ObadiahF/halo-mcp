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

## Token Refresh

Halo tokens expire periodically, but the server handles this **automatically**:

### One-time setup

After configuring `config.json` with your tokens, call the `setup_session` tool. This creates a long-lived session (~30 days) that enables automatic token refresh.

```
setup_session → "Session created, expires 2026-03-24T..."
```

### How it works

1. `setup_session` calls Halo's next-auth API to create a session from your tokens
2. The session cookie is stored in `config.json`
3. When tokens expire during any API call, the server automatically:
   - Uses the session cookie to fetch fresh tokens
   - Saves the new tokens to `config.json`
   - Retries the failed request
4. This is completely transparent — no user intervention needed

### When the session expires (~30 days)

1. Get fresh tokens from your browser (DevTools → Network/Cookies)
2. Update `config.json` with the new `authToken` and `contextToken`
3. Call `setup_session` again

### Manual token management

- `check_tokens` — verify current tokens are valid
- `reload_tokens` — hot-reload tokens from config.json
- `refresh` — manually trigger a session-based token refresh
- `setup_session` — create/renew the long-lived session

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
| `setup_session` | Create a ~30-day session for automatic token refresh |
| `refresh` | Manually refresh tokens using the session cookie |
