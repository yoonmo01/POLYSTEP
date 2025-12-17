// src/api.js
import { getToken } from "./auth";

export const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export function authHeaders(extra = {}) {
  const token = getToken();
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...extra,
  };
}

export async function apiFetch(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
    headers: authHeaders(options.headers || {}),
  });

  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const msg = data?.detail || data?.message || `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}
