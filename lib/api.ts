/**
 * Authenticated fetch wrapper with token caching.
 *
 * Architecture: All frontend API calls go through this function. It
 * attaches the Supabase JWT token and handles 401 by invalidating the
 * cache. The token is cached for 60 seconds to avoid redundant
 * getSession() calls on every request.
 *
 * Token lifecycle:
 * 1. First call: fetches from supabase.auth.getSession()
 * 2. Subsequent calls (< 60s): returns cached token
 * 3. On 401: clears cache, next call re-fetches
 * 4. On sign-out: call clearTokenCache() explicitly
 */

import { supabase } from "./supabase";

let cachedToken: string | null = null;
let tokenExpiry = 0;

export function clearTokenCache(): void {
  cachedToken = null;
  tokenExpiry = 0;
}

export function apiErrorMessage(body: unknown, status: number): string {
  const fallback = `Request failed: ${status}`;
  if (typeof body !== "object" || body === null) return fallback;

  const payload = body as Record<string, unknown>;
  if (typeof payload.error === "string" && payload.error.trim()) return payload.error;
  if (typeof payload.detail === "string" && payload.detail.trim()) return payload.detail;

  if (Array.isArray(payload.detail)) {
    const messages = payload.detail.flatMap((item) => {
      if (typeof item === "string" && item.trim()) return [item];
      if (typeof item !== "object" || item === null) return [];
      const message = (item as Record<string, unknown>).msg;
      return typeof message === "string" && message.trim() ? [message] : [];
    });
    if (messages.length > 0) return messages.join("; ");
  }

  return fallback;
}

async function getToken(): Promise<string | null> {
  if (!supabase) return null;
  const now = Date.now();
  if (cachedToken && now < tokenExpiry) return cachedToken;
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token ?? null;
  cachedToken = token;
  tokenExpiry = now + 60_000;
  return token;
}

export async function apiFetch<T = unknown>(url: string, options?: RequestInit): Promise<T> {
  const token = await getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    if (res.status === 401) cachedToken = null;
    const body = await res.json().catch(() => ({}));
    throw new Error(apiErrorMessage(body, res.status));
  }
  return res.json();
}
