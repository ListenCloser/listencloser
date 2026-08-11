"use client";

import { useEffect, useState } from "react";

export default function MSWInit() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const isMockEnv = process.env.NEXT_PUBLIC_MOCK_ENABLED === "true";
    if (!isMockEnv) {
      setReady(true);
      return;
    }
    async function init() {
      const { handlers } = await import("@/mocks/handlers");
      const { setupWorker } = await import("msw/browser");
      const worker = setupWorker(...handlers);
      await worker.start({ onUnhandledRequest: "bypass" });
      setReady(true);
    }
    init();
  }, []);

  if (!ready) return null;
  return null;
}
