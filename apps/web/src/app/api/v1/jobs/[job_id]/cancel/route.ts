import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ job_id: string }> },
) {
  const { job_id } = await params;
  return proxyToBackend(req, `/api/v1/jobs/${job_id}/cancel`);
}
