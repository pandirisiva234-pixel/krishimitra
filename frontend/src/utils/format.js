export const INTENT_LABELS = {
  crop_cultivation: "Crop cultivation",
  pest_disease: "Pests & diseases",
  fertilizer_soil: "Fertilizer & soil",
  irrigation_water: "Irrigation",
  weather: "Weather",
  harvest_storage: "Harvest & storage",
  greeting: "Greeting",
  other: "Other",
};

export const intentLabel = (key) => INTENT_LABELS[key] || key || "—";

export function formatDateTime(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function formatDate(value) {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export const pct = (x, digits = 0) => (x == null ? "—" : `${(x * 100).toFixed(digits)}%`);

/** "Tomato___Early_blight" -> "Tomato · Early blight" */
export function prettyLabel(label) {
  if (!label) return "";
  const [crop, disease] = label.split("___");
  const clean = (s) => s.replace(/_/g, " ").replace(/\s+/g, " ").trim();
  return disease ? `${clean(crop)} · ${clean(disease)}` : clean(crop);
}

export const kmh = (ms) => Math.round(ms * 3.6);

/**
 * Split an answer into short pieces for speech, so the first piece can play while the rest is made.
 * The first piece is one sentence (fast start); later pieces group sentences up to ~300 characters.
 */
export function splitForSpeech(text, maxLen = 300) {
  const sentences = String(text || "")
    .split(/\n+/)
    .flatMap((line) => line.split(/(?<=[.!?।])\s+/))
    .map((s) => s.replace(/\s*\[\d+(?:,\s*\d+)*\]/g, "").trim()) // citation marks are not read aloud
    .filter((s) => /[\p{L}\p{N}]/u.test(s));
  if (sentences.length === 0) return [];
  const chunks = [sentences[0]];
  let current = "";
  for (const s of sentences.slice(1)) {
    if (current && current.length + s.length + 1 > maxLen) {
      chunks.push(current);
      current = s;
    } else {
      current = current ? `${current} ${s}` : s;
    }
  }
  if (current) chunks.push(current);
  return chunks;
}
