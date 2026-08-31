/**
 * Authenticated frontend fetch wrapper.
 *
 * Supabase is the single owner of session persistence and token refresh. Read
 * the current client session for each request instead of maintaining a second
 * TTL cache that can outlive sign-out or auth-state transitions.
 */

import { supabase } from "./supabase";

export class ApiError extends Error {
  readonly status: number;
  readonly requestId: string | null;

  constructor(message: string, status: number, requestId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.requestId = requestId;
  }
}

async function getToken(): Promise<string | null> {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

function responseRequestId(res: Response, body: unknown): string | null {
  const fromHeader = res.headers?.get?.("x-request-id")?.trim();
  if (fromHeader) return fromHeader;
  if (typeof body === "object" && body !== null && "request_id" in body) {
    const fromBody = (body as { request_id?: unknown }).request_id;
    if (typeof fromBody === "string" && fromBody.trim()) return fromBody.trim();
  }
  return null;
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
    throw new ApiError(
      typeof error === "string" ? error : `Request failed: ${res.status}`,
      res.status,
      responseRequestId(res, body),
    );
  }
  return res.json();
}
