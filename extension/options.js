import {
  getDestinations,
  addDestination,
  removeDestination,
  setDestinationEnabled,
} from "./storage.js";

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function render() {
  const rows = document.getElementById("rows");
  rows.innerHTML = "";
  const destinations = await getDestinations();
  if (destinations.length === 0) {
    rows.innerHTML = `<tr><td colspan="4" class="empty">No destinations yet — add one below.</td></tr>`;
    return;
  }
  for (const d of destinations) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(d.name)}</td>
      <td><code>${escapeHtml(d.url)}</code></td>
      <td><input type="checkbox" data-id="${escapeHtml(d.id)}" ${d.enabled ? "checked" : ""}></td>
      <td><button class="danger" data-id="${escapeHtml(d.id)}">Remove</button></td>`;
    rows.appendChild(tr);
  }
  rows.querySelectorAll("input[type=checkbox]").forEach(el => {
    el.addEventListener("change", () => setDestinationEnabled(el.dataset.id, el.checked));
  });
  rows.querySelectorAll("button.danger").forEach(el => {
    el.addEventListener("click", async () => {
      await removeDestination(el.dataset.id);
      render();
    });
  });
}

document.getElementById("add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("new-name").value.trim();
  const url = document.getElementById("new-url").value.trim();
  if (!name || !url) return;
  try {
    new URL(url);  // validate
  } catch {
    alert("Please enter a valid URL (e.g. https://my-server.example.com/mcp)");
    return;
  }
  await addDestination(name, url);
  document.getElementById("new-name").value = "";
  document.getElementById("new-url").value = "";
  render();
});

document.addEventListener("DOMContentLoaded", render);
