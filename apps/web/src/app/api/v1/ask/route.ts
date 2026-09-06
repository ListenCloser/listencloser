import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend";

export async function POST(req: NextRequest) {
  // The Ask endpoint invokes an LLM, so allow a longer proxy timeout than the
  // 20s default used for the rest of the domain API.
  return proxyToBackend(req, "/api/v1/ask", 60_000);
}
