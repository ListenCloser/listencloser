import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend";

export async function GET(req: NextRequest) {
  return proxyToBackend(req, "/api/v1/projects");
}

export async function POST(req: NextRequest) {
  return proxyToBackend(req, "/api/v1/projects");
}
