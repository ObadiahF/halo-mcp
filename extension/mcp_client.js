// Minimal MCP streamable-http client: initializes a session and calls one tool.
// Returns the tool's structuredContent (or throws with a useful message).

const MCP_HEADERS = {
  "Content-Type": "application/json",
  "Accept": "application/json, text/event-stream",
};

function parseMcpBody(respText, contentType) {
  if (contentType && contentType.startsWith("text/event-stream")) {
    const line = respText.split("\n").find(l => l.startsWith("data: "));
    if (!line) throw new Error("empty SSE response from server");
    return JSON.parse(line.slice(6));
  }
  return JSON.parse(respText);
}

async function mcpInitialize(url) {
  const resp = await fetch(url, {
    method: "POST",
    headers: MCP_HEADERS,
    body: JSON.stringify({
      jsonrpc: "2.0", id: 1, method: "initialize",
      params: {
        protocolVersion: "2024-11-05",
        capabilities: {},
        clientInfo: { name: "halomcp-cookie-pusher", version: "0.1.0" },
      },
    }),
  });
  if (!resp.ok) throw new Error(`initialize failed: HTTP ${resp.status}`);
  const sessionId = resp.headers.get("mcp-session-id");
  if (!sessionId) throw new Error("server did not return mcp-session-id header");
  return sessionId;
}

async function mcpCallTool(url, sessionId, toolName, args) {
  // Notify initialized (required by MCP spec before tool calls).
  await fetch(url, {
    method: "POST",
    headers: { ...MCP_HEADERS, "mcp-session-id": sessionId },
    body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }),
  });

  const resp = await fetch(url, {
    method: "POST",
    headers: { ...MCP_HEADERS, "mcp-session-id": sessionId },
    body: JSON.stringify({
      jsonrpc: "2.0", id: 2, method: "tools/call",
      params: { name: toolName, arguments: args },
    }),
  });
  if (!resp.ok) throw new Error(`tools/call failed: HTTP ${resp.status}`);

  const body = parseMcpBody(await resp.text(), resp.headers.get("content-type"));
  if (body?.error) throw new Error(body.error.message || "tool call error");

  const structured = body?.result?.structuredContent;
  if (structured?.status === "error") {
    throw new Error(structured.message || "server rejected request");
  }
  return structured || body?.result;
}

export async function pushCookieHeader(destinationUrl, cookieHeader) {
  const sessionId = await mcpInitialize(destinationUrl);
  return mcpCallTool(destinationUrl, sessionId, "setup_from_cookies", {
    cookie_header: cookieHeader,
  });
}
