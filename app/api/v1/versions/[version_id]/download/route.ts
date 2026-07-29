import { NextRequest } from "next/server";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ version_id: string }> }
) {
  const { version_id } = await params;
  const backendUrl = process.env.MUSIC_BACKEND_URL || "http://localhost:8000";
  const key = process.env.BACKEND_API_KEY || "";
  const url = `${backendUrl}/api/v1/versions/${version_id}/download`;
  const headers: Record<string, string> = {};
  if (key) headers["Authorization"] = `Bearer ${key}`;
  const res = await fetch(url, { headers });
  return new Response(res.body, { status: res.status, headers: { "Content-Type": res.headers.get("Content-Type") || "application/octet-stream", "Content-Disposition": res.headers.get("Content-Disposition") || 'attachment' } });
}
