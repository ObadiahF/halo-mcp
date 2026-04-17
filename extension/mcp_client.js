// Minimal MCP streamable-http client: initializes a session and calls one tool.
// Returns the tool's structuredContent (or throws with a useful message).

const BASE_HEADERS = {
  "Content-Type": "application/json",
  "Accept": "application/json, text/event-stream",
};

function buildHeaders(accessToken, extra = {}) {
  const h = { ...BASE_HEADERS, ...extra };
  if (accessToken) h["Authorization"] = `Bearer ${accessToken}`;
  return h;
}

function parseMcpBody(respText, contentType) {
  if (contentType && contentType.startsWith("text/event-stream")) {
    const line = respText.split("\n").find(l => l.startsWith("data: "));
    if (!line) throw new Error("empty SSE response from server");
    return JSON.parse(line.slice(6));
  }
  return JSON.parse(respText);
}

function describeHttpError(resp) {
  if (resp.status === 401) return "unauthorized — check the destination's access token";
  return `HTTP ${resp.status}`;
}

async function mcpInitialize(url, accessToken) {
  const resp = await fetch(url, {
    method: "POST",
    headers: buildHeaders(accessToken),
    body: JSON.stringify({
      jsonrpc: "2.0", id: 1, method: "initialize",
      params: {
        protocolVersion: "2024-11-05",
        capabilities: {},
        clientInfo: { name: "halomcp-cookie-pusher", version: "0.1.0" },
      },
    }),
  });
  if (!resp.ok) throw new Error(`initialize failed: ${describeHttpError(resp)}`);
  const sessionId = resp.headers.get("mcp-session-id");
  if (!sessionId) throw new Error("server did not return mcp-session-id header");
  return sessionId;
}

async function mcpCallTool(url, accessToken, sessionId, toolName, args) {
  // Notify initialized (required by MCP spec before tool calls).
  await fetch(url, {
    method: "POST",
    headers: buildHeaders(accessToken, { "mcp-session-id": sessionId }),
    body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }),
  });

  const resp = await fetch(url, {
    method: "POST",
    headers: buildHeaders(accessToken, { "mcp-session-id": sessionId }),
    body: JSON.stringify({
      jsonrpc: "2.0", id: 2, method: "tools/call",
      params: { name: toolName, arguments: args },
    }),
  });
  if (!resp.ok) throw new Error(`tools/call failed: ${describeHttpError(resp)}`);

  const body = parseMcpBody(await resp.text(), resp.headers.get("content-type"));
  if (body?.error) throw new Error(body.error.message || "tool call error");

  const structured = body?.result?.structuredContent;
  if (structured?.status === "error") {
    throw new Error(structured.message || "server rejected request");
  }
  return structured || body?.result;
}

export async function pushCookieHeader(destination, cookieHeader) {
  const { url, accessToken } = destination;
  const sessionId = await mcpInitialize(url, accessToken);
  return mcpCallTool(url, accessToken, sessionId, "setup_from_cookies", {
    cookie_header: cookieHeader,
  });
}
