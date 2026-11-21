// One function per backend endpoint. Pages import from here, never build URLs themselves.
import api from "./client";

const data = (p) => p.then((r) => r.data);

export const meta = {
  languages: () => data(api.get("/api/languages")),
  health: () => data(api.get("/api/health")),
};

export const auth = {
  login: (username, password) => {
    const form = new URLSearchParams({ username, password });
    return data(api.post("/api/auth/login", form, { headers: { "Content-Type": "application/x-www-form-urlencoded" } }));
  },
  register: (body) => data(api.post("/api/auth/register", body)),
  profile: () => data(api.get("/api/auth/profile")),
  updateProfile: (body) => data(api.put("/api/auth/profile", body)),
  changePassword: (body) => data(api.post("/api/auth/change-password", body)),
  logout: () => data(api.post("/api/auth/logout")),
};

export const assistant = {
  transcribe: (blob, filename, languageHint) => {
    const form = new FormData();
    form.append("audio", blob, filename);
    if (languageHint) form.append("language_hint", languageHint);
    // speech recognition on a CPU can take a few minutes for the first, larger models
    return data(api.post("/api/voice/transcribe", form, { timeout: 300000 }));
  },
  ask: (body) => data(api.post("/api/assistant/query", body)),
  speak: (body) => data(api.post("/api/assistant/speak", body)),
  translate: (text, languageCode) =>
    data(api.post("/api/assistant/translate", { text, language_code: languageCode }, { timeout: 120000 })),
  videos: (q, languageCode, original) =>
    data(api.get("/api/assistant/videos", {
      params: { q, language_code: languageCode, ...(original ? { original } : {}) },
      timeout: 30000,
    })),
  feedback: (body) => data(api.post("/api/feedback", body)),
  fetchBlob: (url) => api.get(url, { responseType: "blob" }).then((r) => r.data),
};

export const conversations = {
  list: () => data(api.get("/api/conversations")),
  get: (id) => data(api.get(`/api/conversations/${id}`)),
  remove: (id) => data(api.delete(`/api/conversations/${id}`)),
};

export const items = {
  identify: (blob, filename, languageCode) => {
    const form = new FormData();
    form.append("image", blob, filename);
    if (languageCode) form.append("language_code", languageCode);
    return data(api.post("/api/items/identify", form, { timeout: 120000 }));
  },
};

export const disease = {
  predict: (blob, filename) => {
    const form = new FormData();
    form.append("image", blob, filename);
    return data(api.post("/api/disease/predict", form));
  },
  history: (limit = 20) => data(api.get("/api/disease/history", { params: { limit } })),
  secondOpinion: (predictionId, languageCode) => {
    const form = new FormData();
    if (languageCode) form.append("language_code", languageCode);
    return data(api.post(`/api/disease/predictions/${predictionId}/second-opinion`, form, { timeout: 120000 }));
  },
  classes: () => data(api.get("/api/disease/classes")),
};

export const weather = {
  current: (params) => data(api.get("/api/weather/current", { params })),
  forecast: (params) => data(api.get("/api/weather/forecast", { params })),
  geocode: (q) => data(api.get("/api/weather/geocode", { params: { q } })),
};

export const knowledge = {
  documents: () => data(api.get("/api/knowledge/documents")),
  upload: (file, title, sourceUrl) => {
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    if (sourceUrl) form.append("source_url", sourceUrl);
    return data(api.post("/api/knowledge/upload", form));
  },
  remove: (id) => data(api.delete(`/api/knowledge/documents/${id}`)),
  search: (body) => data(api.post("/api/knowledge/search", body)),
};

export const dashboard = {
  summary: () => data(api.get("/api/dashboard/summary")),
};

export const admin = {
  dashboard: () => data(api.get("/api/admin/dashboard")),
  statistics: (days = 30) => data(api.get("/api/admin/statistics", { params: { days } })),
  users: (params) => data(api.get("/api/admin/users", { params })),
  updateUser: (id, body) => data(api.patch(`/api/admin/users/${id}`, body)),
  system: () => data(api.get("/api/admin/system")),
};
