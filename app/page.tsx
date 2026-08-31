"use client";

import { useEffect } from "react";
import { useAuth } from "@/components/AuthProvider";
import BrandMark from "@/components/BrandMark";
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
  return (
    <main className="app-boot-shell" aria-busy="true" aria-label="Opening your library">
      <header className="app-boot-header"><BrandMark size={21} /></header>
      <div className="app-boot-workspace" aria-hidden="true">
        <aside className="app-boot-library">
          <span className="boot-line boot-line-short" />
          <span className="boot-row" /><span className="boot-row" /><span className="boot-row" />
        </aside>
        <section className="app-boot-canvas">
          <div className="app-boot-tabs"><span /><span /><span /><span /></div>
          <div className="app-boot-visual">{Array.from({ length: 8 }).map((_, index) => <span key={index} />)}</div>
        </section>
        <aside className="app-boot-inspector"><span className="boot-line" /><span className="boot-row" /><span className="boot-row" /></aside>
      </div>
      <footer className="app-boot-transport" />
    </main>
  );
}

function SignedOutLanding() {
  async function signIn() {
    await supabase?.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  }

  return (
    <main className="welcome-page welcome-page-v4">
      <header className="welcome-header welcome-header-v4">
        <span className="welcome-mark" aria-label="Music workspace"><BrandMark size={26} /></span>
      </header>
      <section className="welcome-hero welcome-hero-v4">
        <h1>Listen closer.</h1>
        <p>Bring in a recording. Move between waveform, piano roll, notation, and analysis without losing your place.</p>
        <button className="btn btn-primary" onClick={signIn}>Continue with Google</button>
        <small>Your recordings stay private to your account.</small>
      </section>
    </main>
  );
}
