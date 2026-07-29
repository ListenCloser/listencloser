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

/**
 * Generic reverse-proxy to the Oracle FastAPI backend.
 * Forwards the request body/method to `BACKEND_URL + path` and returns JSON.
 */
export async function proxyToBackendFormData(req: NextRequest, path: string) {
  try {
    const authHeader = req.headers.get("authorization");
    const headers: Record<string, string> = {};
    if (authHeader) headers["Authorization"] = authHeader;

    const formData = await req.formData();
    const res = await fetch(`${getBackendUrl()}${path}`, {
      method: "POST",
      headers,
      body: formData,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof data === "object" && data !== null && "detail" in data
        ? (data as { detail?: unknown }).detail
        : undefined;
      return NextResponse.json(
        { error: typeof detail === "string" ? detail : "backend error" },
        { status: res.status }
      );
    }
    return NextResponse.json(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "unknown error";
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}

export async function proxyToBackend(req: NextRequest, path: string) {
  try {
    const authHeader = req.headers.get("authorization");
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (authHeader) headers["Authorization"] = authHeader;

    const init: RequestInit = {
      method: req.method,
      headers,
    };
    if (req.method !== "GET" && req.method !== "HEAD") {
      const body = await req.text();
      if (body) init.body = body;
    }
    const res = await fetch(`${getBackendUrl()}${path}`, init);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof data === "object" && data !== null && "detail" in data
        ? (data as { detail?: unknown }).detail
        : undefined;
      return NextResponse.json(
        { error: typeof detail === "string" ? detail : "backend error" },
        { status: res.status }
      );
    }
    return NextResponse.json(data);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "unknown error";
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
