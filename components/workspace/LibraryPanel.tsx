"use client";

import { useWorkspace } from "@/lib/stores/workspace";
import { supabase } from "@/lib/supabase";

export default function LibraryPanel({
  signedIn = false,
  projectName,
}: {
  signedIn?: boolean;
  projectName?: string;
}) {
  const { workspace, toggleLibrary } = useWorkspace();

  async function signIn() {
    if (!supabase) return;
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  }

  async function signOut() {
    await supabase?.auth.signOut();
    window.location.reload();
  }

  if (workspace.libraryCollapsed) {
    return (
      <div style={{ width: 44, flexShrink: 0, borderRight: "1px solid var(--border)", background: "var(--panel)", padding: "var(--s-2) 0", textAlign: "center" }}>
        <button className="icon-btn ghost" onClick={toggleLibrary} title="Expand library">▸</button>
      </div>
    );
  }

  return (
    <aside style={{ width: 240, flexShrink: 0, borderRight: "1px solid var(--border)", background: "var(--panel)", padding: "var(--s-3)", display: "flex", flexDirection: "column", gap: "var(--s-3)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span className="section-label" style={{ margin: 0 }}>Workspace</span>
        <button className="icon-btn ghost" onClick={toggleLibrary} title="Collapse library">◂</button>
      </div>
      <div className="stat">
        <span className="s-label">Current project</span>
        <span className="s-value" style={{ fontSize: "var(--fs-sm)" }}>{projectName || "No project loaded"}</span>
      </div>
      <p style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", lineHeight: 1.5 }}>
        This first real pipeline keeps one active session. Persistent project browsing is the next slice.
      </p>
      <div style={{ flex: 1 }} />
      <button className="btn" onClick={signedIn ? signOut : signIn}>
        {signedIn ? "Sign out" : "Sign in with Google"}
      </button>
    </aside>
  );
}
