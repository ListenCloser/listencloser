import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ work_id: string }> },
) {
  const { work_id } = await params;
  return proxyToBackend(
    req,
    `/api/v1/works/${work_id}/relations/similar-moments`,
  );
}
