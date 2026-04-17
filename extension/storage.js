// Shared destination CRUD backed by chrome.storage.sync.
// First-run seeds a single "Local" destination pointing at the default
// HaloMCP docker port on localhost.

const DEFAULT_DESTINATIONS = [
  { id: "local", name: "Local", url: "http://localhost:8000/mcp", enabled: true },
];

export async function getDestinations() {
  const { destinations } = await chrome.storage.sync.get({ destinations: null });
  if (destinations === null) {
    await chrome.storage.sync.set({ destinations: DEFAULT_DESTINATIONS });
    return DEFAULT_DESTINATIONS;
  }
  return destinations;
}

export async function saveDestinations(destinations) {
  await chrome.storage.sync.set({ destinations });
}

export async function addDestination(name, url) {
  const destinations = await getDestinations();
  const id = `dest-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  destinations.push({ id, name, url, enabled: true });
  await saveDestinations(destinations);

  // Request host permission for the new origin so fetch() isn't blocked by CORS.
  try {
    const origin = new URL(url).origin + "/*";
    await chrome.permissions.request({ origins: [origin] });
  } catch {
    // user denied or URL invalid — push will fail later with a clear error
  }
  return id;
}

export async function removeDestination(id) {
  const destinations = (await getDestinations()).filter(d => d.id !== id);
  await saveDestinations(destinations);
}

export async function setDestinationEnabled(id, enabled) {
  const destinations = await getDestinations();
  const d = destinations.find(x => x.id === id);
  if (d) {
    d.enabled = enabled;
    await saveDestinations(destinations);
  }
}
