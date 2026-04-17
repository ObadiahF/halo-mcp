import { pushCookieHeader } from "./mcp_client.js";
import { getDestinations, setDestinationAccessToken } from "./storage.js";

const HALO_DOMAIN = "halo.gcu.edu";
const REQUIRED_COOKIES = [
  "__Host-next-auth.csrf-token",
  "__Secure-next-auth.callback-url",
  "__Secure-next-auth.session-token",
  "TE1TX0FVVEg",
  "TE1TX0NPTlRFWFQ",
];

async function getHaloCookieHeader() {
  const cookies = await chrome.cookies.getAll({ domain: HALO_DOMAIN });
  const wanted = cookies.filter(c => REQUIRED_COOKIES.includes(c.name));
  const sessionPresent = wanted.some(c => c.name === "__Secure-next-auth.session-token");
  if (!sessionPresent) {
    throw new Error("Not logged into halo.gcu.edu in this browser — open it and log in first.");
  }
  return wanted.map(c => `${c.name}=${c.value}`).join("; ");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function setStatus(el, text, cls) {
  el.textContent = text;
  el.className = `dest-status ${cls}`;
}

async function render() {
  const list = document.getElementById("destinations");
  list.innerHTML = "";
  const destinations = await getDestinations();
  if (destinations.length === 0) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "No destinations configured — click Settings to add one.";
    list.appendChild(li);
    return;
  }
  for (const d of destinations) {
    const li = document.createElement("li");
    li.innerHTML = `
      <div class="dest-row">
        <input type="checkbox" class="dest-check" data-id="${escapeHtml(d.id)}" ${d.enabled ? "checked" : ""}>
        <div style="flex:1">
          <div class="dest-name">${escapeHtml(d.name)}</div>
          <div class="dest-url">${escapeHtml(d.url)}</div>
          <input type="text" class="dest-token" data-id="${escapeHtml(d.id)}"
                 value="${escapeHtml(d.accessToken || "")}"
                 placeholder="access token (leave blank if server has no auth)"
                 autocomplete="off">
          <div class="dest-status" id="status-${escapeHtml(d.id)}"></div>
        </div>
      </div>`;
    list.appendChild(li);
  }
  list.querySelectorAll(".dest-token").forEach(el => {
    el.addEventListener("change", () => setDestinationAccessToken(el.dataset.id, el.value.trim()));
  });
}

async function push() {
  const pushBtn = document.getElementById("push");
  pushBtn.disabled = true;
  try {
    const cookieHeader = await getHaloCookieHeader();
    const destinations = await getDestinations();
    const checkedIds = new Set(
      [...document.querySelectorAll(".dest-check:checked")].map(el => el.dataset.id)
    );
    // Pick up unsaved token edits from the visible inputs.
    const liveTokens = Object.fromEntries(
      [...document.querySelectorAll(".dest-token")].map(el => [el.dataset.id, el.value.trim()])
    );
    const targets = destinations
      .filter(d => checkedIds.has(d.id))
      .map(d => ({ ...d, accessToken: liveTokens[d.id] ?? d.accessToken }));
    if (targets.length === 0) {
      alert("Select at least one destination to push to.");
      return;
    }
    await Promise.all(targets.map(async d => {
      const statusEl = document.getElementById(`status-${d.id}`);
      setStatus(statusEl, "pushing…", "status-pending");
      try {
        const result = await pushCookieHeader(d, cookieHeader);
        const method = result?.authMethod || "saved";
        const exp = result?.tokenExpiration || result?.expires || "";
        setStatus(statusEl, `✓ ${method}${exp ? " — " + exp : ""}`, "status-ok");
        if (result?.warning) {
          const warn = document.createElement("div");
          warn.className = "dest-status status-err";
          warn.textContent = `⚠ ${result.warning}`;
          statusEl.parentElement.appendChild(warn);
        }
      } catch (e) {
        setStatus(statusEl, `✗ ${e.message}`, "status-err");
      }
    }));
  } catch (e) {
    const warn = document.getElementById("halo-warn");
    warn.textContent = e.message;
    warn.style.display = "block";
  } finally {
    pushBtn.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  render();
  document.getElementById("push").addEventListener("click", push);
  document.getElementById("open-options").addEventListener("click",
    () => chrome.runtime.openOptionsPage());
});
