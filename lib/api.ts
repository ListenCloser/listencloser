/**
 * Authenticated frontend API transport.
 *
 * Supabase is the single owner of session persistence and token refresh. Read
 * the current client session for each request instead of maintaining a second
 * TTL cache that can outlive sign-out or auth-state transitions.
 *
 * New ordinary JSON endpoints should use the generated `apiClient` contract.
 * `apiFetch` remains temporarily for endpoints that have not migrated yet.
 */

import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./api-types";
import { supabase } from "./supabase";

async function getToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

export function apiResponseError(body: unknown, status: number): Error {
  const error = typeof body === "object" && body !== null && "error" in body
    ? (body as { error?: unknown }).error
    : undefined;
  return new Error(typeof error === "string" ? error : `Request failed: ${status}`);
}

const authMiddleware: Middleware = {
  async onRequest({ request }) {
    const token = await getToken();
    if (token) request.headers.set("Authorization", `Bearer ${token}`);
    return request;
  },
};

// All current callers are browser-side and use same-origin API routes. The
// localhost fallback makes the client deterministic in jsdom/build-time module
// evaluation without introducing a deployment-specific API origin.
const baseUrl = typeof location === "undefined" ? "http://localhost" : location.origin;

export const apiClient = createClient<paths>({ baseUrl });
apiClient.use(authMiddleware);

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
    throw apiResponseError(body, res.status);
  }
  return res.json();
}
