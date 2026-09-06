import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend";

export async function GET(req: NextRequest) {
  return proxyToBackend(req, "/health/live");
}
