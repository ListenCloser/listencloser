"use client";

import { useEffect } from "react";
import { useAuth } from "@/components/AuthProvider";
import LiveSignalField from "@/components/design/LiveSignalField";
import WorkspaceSession from "@/components/workspace/WorkspaceSession";
import WorkspaceShell, { type ServiceStatus } from "@/components/workspace/WorkspaceShell";
import { supabase } from "@/lib/supabase";
import { useProcessingHealth } from "@/lib/server-state";

export default function Home() {
  const { user, loading } = useAuth();
  const {
    data: processingHealth,
    isPending: processingHealthPending,
    isSuccess: processingHealthSuccess,
    refetch: refreshService,
  } = useProcessingHealth();
  const serviceStatus: ServiceStatus = processingHealthPending
    ? "checking"
    : processingHealthSuccess && processingHealth?.status === "ready"
      ? "ready"
      : "unavailable";

  useEffect(() => {
    const onControllerChange = () => { void refreshService(); };
    navigator.serviceWorker?.addEventListener("controllerchange", onControllerChange);
    return () => {
      navigator.serviceWorker?.removeEventListener("controllerchange", onControllerChange);
    };
  }, [refreshService]);

  if (loading) return <AppBootShell />;
  if (!user) return <SignedOutLanding />;

  return (
    <WorkspaceShell signedIn serviceStatus={serviceStatus}>
      <WorkspaceSession serviceStatus={serviceStatus} />
    </WorkspaceShell>
  );
}

function AppBootShell() {
  // Auth lookup should be visually inert. The app root already owns the page
  // background, so there is no intermediate spinner, mark, or loading shell.
  return <main aria-busy="true" aria-label="Opening your library" />;
}

function SignedOutLanding() {
  async function signIn() {
    await supabase?.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  }

  return (
    <main className="aesthetic-landing">
      <header className="aesthetic-landing-header">
        <span className="aesthetic-wordmark">Music, in context.</span>
      </header>

      <section className="aesthetic-hero">
        <div className="aesthetic-hero-copy">
          <h1>Listen<br /><em>closer.</em></h1>
          <button type="button" className="aesthetic-enter" onClick={signIn}>
            <span>Continue with Google</span>
            <span aria-hidden="true">↗</span>
          </button>
        </div>

        <div className="aesthetic-signal-object aesthetic-signal-object-solo" aria-hidden="true">
          <div className="aesthetic-signal-solo-field">
            <LiveSignalField
              className="aesthetic-live-signal"
              height={330}
              barWidth={2}
              barGap={5}
            />
          </div>
        </div>
      </section>
    </main>
  );
}
