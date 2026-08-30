/**
 * Generic reverse-proxy to the FastAPI backend.
 *
 * Architecture: The browser never talks to the Oracle VM directly.
 * All backend calls go through Next.js API routes which use this
 * function to proxy requests. This keeps the VM URL/key off the client.
 *
 * Request flow: Browser → Next.js API route → proxyToBackend() → FastAPI
 */

import { NextRequest, NextResponse } from "next/server";

function getBackendUrl(): string {
  const url = process.env.MUSIC_BACKEND_URL;
  if (!url) {
    throw new Error("MUSIC_BACKEND_URL environment variable is not set");
  }
  return url;
}

function jsonWithRequestId(body: unknown, status: number, requestId: string) {
  return NextResponse.json(body, {
    status,
    headers: { "x-request-id": requestId },
  });
}

/**
 * Generic reverse-proxy to the Oracle FastAPI backend.
 * Forwards the request body/method to `BACKEND_URL + path` and returns JSON.
 *
 * The proxy owns one correlation id for the full browser → Vercel → FastAPI
 * request. FastAPI echoes this id in its own structured request log, so an
 * upstream timeout or 5xx can be joined to the backend trace without exposing
 * provider details to the browser.
 */
export async function proxyToBackend(req: NextRequest, path: string, timeoutMs = 20_000) {
  const requestId = req.headers.get("x-request-id") || crypto.randomUUID();
  const startedAt = Date.now();
  try {
    const authHeader = req.headers.get("authorization");
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "x-request-id": requestId,
    };
    if (authHeader) headers.Authorization = authHeader;

    const init: RequestInit = {
      method: req.method,
      headers,
      signal: AbortSignal.timeout(timeoutMs),
    };
    if (req.method !== "GET" && req.method !== "HEAD") {
      const body = await req.text();
      if (body) init.body = body;
    }
    const res = await fetch(`${getBackendUrl()}${path}`, init);
    const data = await res.json().catch(() => ({}));
    const durationMs = Date.now() - startedAt;
    const backendRequestId = res.headers.get("x-request-id") || requestId;

    if (!res.ok) {
      const detail = typeof data === "object" && data !== null && "detail" in data
        ? (data as { detail?: unknown }).detail
        : undefined;
      console.error("backend_proxy_upstream_error", {
        requestId: backendRequestId,
        path,
        status: res.status,
        durationMs,
      });
      return jsonWithRequestId(
        {
          error: typeof detail === "string" ? detail : "backend error",
          request_id: backendRequestId,
        },
        res.status,
        backendRequestId,
      );
    }

    return jsonWithRequestId(data, res.status, backendRequestId);
  } catch (err) {
    const durationMs = Date.now() - startedAt;
    console.error("backend_proxy_failed", { requestId, path, durationMs, error: err });
    return jsonWithRequestId(
      { error: "Processing service unavailable", request_id: requestId },
      502,
      requestId,
    );
  }
}
