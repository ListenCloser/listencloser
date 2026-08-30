/**
 * Authenticated frontend fetch wrapper.
 *
 * Supabase is the single owner of session persistence and token refresh. Read
 * the current client session for each request instead of maintaining a second
 * TTL cache that can outlive sign-out or auth-state transitions.
 */

import { supabase } from "./supabase";

async function getToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export async function apiFetch<T = unknown>(url: string, options?: RequestInit): Promise<T> {
  const token = await getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string>),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(url, { ...options, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const error = typeof body === "object" && body !== null && "error" in body
      ? (body as { error?: unknown }).error
      : undefined;
    throw new Error(typeof error === "string" ? error : `Request failed: ${res.status}`);
  }
  return res.json();
}
