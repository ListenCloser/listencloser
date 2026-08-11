"use client";

import { useWorkspace } from "@/lib/stores/workspace";
import { supabase } from "@/lib/supabase";

export default function LibraryPanel({ signedIn = false }: { signedIn?: boolean }) {
  const {
    workspace,
    requestImport,
    setActiveWorkId,
    toggleLibrary,
  } = useWorkspace();

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
      <aside style={{ width: 44, flexShrink: 0, borderRight: "1px solid var(--border)", background: "var(--panel)", padding: "var(--s-2) 0", textAlign: "center" }}>
        <button className="icon-btn ghost" onClick={toggleLibrary} title="Expand library">▸</button>
      </aside>
    );
  }

  return (
    <aside style={{ width: 260, flexShrink: 0, borderRight: "1px solid var(--border)", background: "var(--panel)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "var(--s-3)", borderBottom: "1px solid var(--border)" }}>
        <div>
          <div className="section-label" style={{ margin: 0 }}>Project</div>
          <div style={{ fontSize: "var(--fs-sm)", marginTop: 4 }}>{workspace.project?.name ?? "No project"}</div>
        </div>
        <button className="icon-btn ghost" onClick={toggleLibrary} title="Collapse library">◂</button>
      </div>

      {signedIn && (
        <div style={{ padding: "var(--s-3)", borderBottom: "1px solid var(--border)" }}>
          <button className="btn btn-primary" style={{ width: "100%" }} onClick={requestImport}>
            Import audio
          </button>
        </div>
      )}

      <div style={{ flex: 1, overflow: "auto", padding: "var(--s-2)" }}>
        {workspace.works.length === 0 ? (
          <p style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", lineHeight: 1.5, padding: "var(--s-2)" }}>
            Imported works will appear here and can be reopened in later sessions.
          </p>
        ) : workspace.works.map((work) => {
          const selected = workspace.activeWorkId === work.id;
          return (
            <button
              key={work.id}
              onClick={() => setActiveWorkId(work.id)}
              disabled={workspace.isLoadingWork && selected}
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 3,
                width: "100%",
                padding: "var(--s-3)",
                marginBottom: "var(--s-1)",
                border: `1px solid ${selected ? "var(--accent)" : "transparent"}`,
                borderRadius: "var(--r-md)",
                background: selected ? "var(--accent-soft)" : "transparent",
                color: selected ? "var(--accent)" : "var(--text)",
                cursor: "pointer",
                textAlign: "left",
                fontFamily: "inherit",
              }}
            >
              <span style={{ fontSize: "var(--fs-sm)", fontWeight: "var(--fw-medium)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", width: "100%" }}>
                {work.title}
              </span>
              <span style={{ color: "var(--muted)", fontSize: "var(--fs-xs)" }}>
                {workspace.isLoadingWork && selected ? "Loading…" : new Date(work.created_at).toLocaleDateString()}
              </span>
            </button>
          );
        })}
      </div>

      <div style={{ padding: "var(--s-3)", borderTop: "1px solid var(--border)" }}>
        <button className="btn" style={{ width: "100%" }} onClick={signedIn ? signOut : signIn}>
          {signedIn ? "Sign out" : "Sign in with Google"}
        </button>
      </div>
    </aside>
  );
}
