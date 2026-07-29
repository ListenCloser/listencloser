import { NextRequest } from "next/server";
import { proxyToBackendFormData } from "@/lib/backend";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ project_id: string }> }
) {
  const { project_id } = await params;
  return proxyToBackendFormData(req, `/api/v1/projects/${project_id}/artifacts/upload`);
}
