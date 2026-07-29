import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ version_id: string }> }
) {
  const { version_id } = await params;
  return proxyToBackend(req, `/api/v1/versions/${version_id}/analyze`);
}
