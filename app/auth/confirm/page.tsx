"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

export default function AuthConfirm() {
  const router = useRouter();

  useEffect(() => {
    if (!supabase) {
      router.replace("/?error=auth_callback_failed");
      return;
    }

    const params = new URLSearchParams(window.location.search);
    const code = params.get("code");
    const next = params.get("next") ?? "/";

    if (code) {
      supabase.auth.exchangeCodeForSession(code).then(({ error }) => {
        router.replace(error ? "/?error=auth_callback_failed" : next);
      });
    } else {
      const timer = setTimeout(() => {
        if (window.location.search) {
          router.replace("/");
        } else {
          router.replace("/?error=auth_callback_failed");
        }
      }, 2000);

      return () => clearTimeout(timer);
    }
  }, [router]);

  // Session handoff is intentionally visually inert. The app root already owns
  // the page background, so this route does not introduce a spinner or shell.
  return <main aria-busy="true" aria-label="Completing sign in" />;
}
