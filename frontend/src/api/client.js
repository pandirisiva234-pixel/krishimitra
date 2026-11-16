import axios from "axios";

const TOKEN_KEY = "krishimitra_token";

// localStorage can be unavailable (private mode, some embedded browsers): never crash on it.
export const tokenStore = {
  get() {
    try {
      return localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token) {
    try {
      localStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* ignore */
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
};

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "",
  timeout: 120000, // the first voice request can be slow while models load
});

api.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || "";
    if (error.response?.status === 401 && !url.includes("/auth/login") && !url.includes("/auth/change-password")) {
      tokenStore.clear();
      onUnauthorized();
    }
    return Promise.reject(error);
  },
);

/** Turn any API/network error into one readable sentence for the user. */
export function errorMessage(error, fallback = "Something went wrong. Please try again.") {
  if (error?.code === "ECONNABORTED") return "The server took too long to answer. Please try again.";
  if (!error?.response) return "Cannot reach the server. Check that the backend is running and you are online.";
  const body = error.response.data;
  if (body?.error?.details?.length) {
    return body.error.details.map((d) => `${d.field ? `${d.field}: ` : ""}${d.message}`).join(" · ");
  }
  if (body?.error?.message) return body.error.message;
  if (typeof body?.detail === "string") return body.detail;
  if (error.response.status === 429) return "Too many requests. Please wait a minute.";
  return fallback;
}

export default api;
