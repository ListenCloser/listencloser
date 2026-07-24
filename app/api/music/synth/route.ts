import { NextRequest } from "next/server";
import { proxyToBackend } from "@/lib/backend";

export async function POST(req: NextRequest) {
  return proxyToBackend(req, "/music/synth");
}
