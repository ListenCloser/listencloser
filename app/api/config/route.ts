import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({
    backendUrl: process.env.MUSIC_BACKEND_URL || "",
  });
}
