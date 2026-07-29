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
    const error = typeof body === "object" && body !== null && "error" in body
      ? (body as { error?: unknown }).error
      : undefined;
    throw new Error(typeof error === "string" ? error : `Request failed: ${res.status}`);
  }
  return res.json();
}
