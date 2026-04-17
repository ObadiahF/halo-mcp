# HaloMCP Cookie Pusher

Chrome/Edge extension that pushes your Halo session cookies to one or more
HaloMCP servers in one click. Replaces the manual copy-paste of the
`Cookie:` header into the `setup_from_cookies` MCP tool.

## Install (unpacked)

1. Open `chrome://extensions` (or `edge://extensions`)
2. Enable **Developer mode**
3. Click **Load unpacked** and select this `extension/` folder
4. Pin the extension icon to your toolbar

## Usage

1. Make sure you're logged into <https://halo.gcu.edu> in the same browser profile
2. Click the extension icon
3. Check the destinations you want to push to
4. Click **Push to selected**

Each destination shows its result inline — `✓ open_id — <tokenExpiration>`
on success, `✗ <error>` on failure.

## Destinations

The extension seeds a single destination on first run:
`http://localhost:8000/mcp` (the default HaloMCP docker port).

To add more (e.g. a VPS-hosted HaloMCP), click **Settings** in the popup
and fill in name + MCP URL. The extension requests host permission for each
new origin — approve the prompt so cross-origin `fetch()` is allowed.

## Security

Session cookies grant full access to your Halo account until they expire
(~30 days). Treat them like a password.

- Only add destinations you trust.
- The HaloMCP server supports **opt-in** bearer-token auth on its `/mcp`
  endpoint. Leave `mcpAccessToken` unset in the server's config.json to
  run unauthenticated (fine for localhost); set it to any value to require
  `Authorization: Bearer <token>` on every request. For a public/VPS
  deployment, setting it is strongly recommended.
- When auth is enabled, paste the configured token into the destination's
  **access token** field (either in the popup or in Settings). Leave blank
  for unauthenticated servers.
- For public exposure, front the server with HTTPS in addition to the
  bearer token.
- The extension never sends cookies to any server you haven't explicitly
  added to the destination list.

## How it works

- Reads Halo's `HttpOnly` cookies via `chrome.cookies.getAll({ domain: "halo.gcu.edu" })`
  (the page-level `document.cookie` API cannot access these, which is why a
  bookmarklet wouldn't work)
- Builds a `Cookie:` header string
- For each enabled destination: opens a streamable-http MCP session
  (`initialize` → `notifications/initialized` → `tools/call`), invoking
  `setup_from_cookies` with the cookie header
- Renders per-destination status in the popup

## Files

| File | Purpose |
|---|---|
| `manifest.json` | MV3 manifest (permissions, popup, options page) |
| `popup.html` / `popup.js` | Toolbar popup UI + push logic |
| `options.html` / `options.js` | Destinations management page |
| `mcp_client.js` | Minimal MCP streamable-http client |
| `storage.js` | Destination CRUD on top of `chrome.storage.sync` |
