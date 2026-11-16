// The device's current position from the browser (GPS on phones, Wi-Fi on laptops).
// The browser asks the farmer once for permission. The position is remembered for 10 minutes
// so every weather question does not wait for GPS again.
const KEY = "krishimitra_current_location";
const MAX_AGE_MS = 10 * 60 * 1000;

function remembered() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(KEY) || "null");
    return saved && Date.now() - saved.at < MAX_AGE_MS ? saved : null;
  } catch {
    return null;
  }
}

/** Resolves to { lat, lon } or null (no permission, no GPS, or too slow). Never rejects. */
export function getCurrentLocation({ fresh = false, timeoutMs = 8000 } = {}) {
  const saved = !fresh && remembered();
  if (saved) return Promise.resolve({ lat: saved.lat, lon: saved.lon });
  if (typeof navigator === "undefined" || !navigator.geolocation) return Promise.resolve(null);
  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const loc = { lat: +pos.coords.latitude.toFixed(4), lon: +pos.coords.longitude.toFixed(4) };
        try {
          sessionStorage.setItem(KEY, JSON.stringify({ ...loc, at: Date.now() }));
        } catch {
          /* storage unavailable: still return the position */
        }
        resolve(loc);
      },
      () => resolve(null),
      { enableHighAccuracy: false, timeout: timeoutMs, maximumAge: MAX_AGE_MS },
    );
  });
}
