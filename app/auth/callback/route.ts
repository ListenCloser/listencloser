import { NextResponse } from "next/server";

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = searchParams.get("next") ?? "/";

  if (code) {
    return NextResponse.redirect(
      `${origin}/auth/confirm?code=${encodeURIComponent(code)}&next=${encodeURIComponent(next)}`,
    );
  }

  return NextResponse.redirect(`${origin}/?error=auth_callback_failed`);
}
