"use client";

import { useEffect, useState, type ReactNode } from "react";

export default function MSWInit({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const isMockEnv = process.env.NEXT_PUBLIC_MOCK_ENABLED === "true";
    if (!isMockEnv) {
      setReady(true);
      return;
    }
    async function init() {
      const [{ handlers }, { directUploadHandlers }] = await Promise.all([
        import("@/app/_test-support/msw/handlers"),
        import("@/app/_test-support/msw/direct-upload-handlers"),
      ]);
      const { setupWorker } = await import("msw/browser");
      const worker = setupWorker(...directUploadHandlers, ...handlers);
      await worker.start({ onUnhandledRequest: "bypass" });
      setReady(true);
    }
    init();
  }, []);

  if (!ready) return null;
  return <>{children}</>;
}
