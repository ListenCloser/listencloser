import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ project_id: string }> },
) {
  const { project_id } = await params;
  return proxyToBackend(req, `/api/v1/projects/${project_id}/artifacts/upload-intent`);
}
