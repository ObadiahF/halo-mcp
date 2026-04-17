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
- The HaloMCP server enforces bearer-token auth on its `/mcp` endpoint.
  On first startup it auto-generates a token and prints it to the server
  log — paste that into the **Access token** field for the matching
  destination. Pushes without a valid token return HTTP 401.
- For public exposure, still front the server with HTTPS.
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
