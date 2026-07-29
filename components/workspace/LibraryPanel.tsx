"use client";

import { useState, useEffect } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { supabase } from "@/lib/supabase";
import { listProjects } from "@/lib/api-client";
import type { Project } from "@/lib/domain.types";

export default function LibraryPanel({ signedIn = false }: { signedIn?: boolean }) {
  const { workspace, toggleLibrary } = useWorkspace();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    listProjects()
      .then(setProjects)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  async function signIn() {
    if (!supabase) return;
    const callbackUrl = `${window.location.origin}/auth/callback`;
    const currentPath = window.location.pathname + window.location.search;
    const redirectTo =
      currentPath && currentPath !== "/"
        ? `${callbackUrl}?next=${encodeURIComponent(currentPath)}`
        : callbackUrl;
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo },
    });
  }

  function signOut() {
    supabase?.auth.signOut();
    window.location.reload();
  }

  if (workspace.libraryCollapsed) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "var(--s-2)",
          padding: "var(--s-2) 0",
          width: 44,
          flexShrink: 0,
          borderRight: "1px solid var(--border)",
          background: "var(--panel)",
          fontSize: "var(--fs-xs)",
        }}
      >
        <button
          className="icon-btn ghost"
          onClick={toggleLibrary}
          style={{ padding: "4px 8px" }}
          title="Expand library"
        >
          ▸
        </button>

        {projects.slice(0, 4).map((p) => (
          <button
            key={p.id}
            className="icon-btn ghost"
            style={{
              padding: "6px",
              fontSize: 12,
              background: selectedProjectId === p.id ? "var(--accent-soft)" : undefined,
              color: selectedProjectId === p.id ? "var(--accent)" : "var(--muted)",
            }}
            title={p.name}
          >
            {p.name.slice(0, 1)}
          </button>
        ))}

        <div style={{ flex: 1 }} />

        {signedIn ? (
          <button className="icon-btn ghost" onClick={signOut} style={{ padding: "4px 6px" }} title="Sign out">
            ⏻
          </button>
        ) : (
          <button className="icon-btn ghost" onClick={signIn} style={{ padding: "4px 6px" }} title="Sign in">
            ↗
          </button>
        )}
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: 260,
        flexShrink: 0,
        borderRight: "1px solid var(--border)",
        background: "var(--panel)",
        overflow: "hidden",
        fontSize: "var(--fs-sm)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "var(--s-2) var(--s-3)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <span
          style={{
            fontSize: "var(--fs-xs)",
            fontWeight: "var(--fw-semibold)",
            color: "var(--muted)",
            textTransform: "uppercase",
            letterSpacing: "0.05em",
          }}
        >
          Library
        </span>

        <button
          className="icon-btn ghost"
          onClick={toggleLibrary}
          style={{ padding: "2px 6px", fontSize: 10 }}
          title="Collapse library"
        >
          ◂
        </button>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "var(--s-2)" }}>
        {loading && (
          <div style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", textAlign: "center", padding: "var(--s-4)" }}>
            Loading projects…
          </div>
        )}
        {error && (
          <div style={{ color: "var(--danger)", fontSize: "var(--fs-xs)", textAlign: "center", padding: "var(--s-4)" }}>
            {error}
          </div>
        )}
        {!loading && !error && projects.length === 0 && (
          <div style={{ color: "var(--muted)", fontSize: "var(--fs-xs)", textAlign: "center", padding: "var(--s-4)" }}>
            No projects yet
          </div>
        )}
        {projects.map((project) => {
          const isSelected = selectedProjectId === project.id;
          return (
            <button
              key={project.id}
              onClick={() => setSelectedProjectId(isSelected ? null : project.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--s-2)",
                width: "100%",
                padding: "var(--s-2) var(--s-2)",
                border: "none",
                borderRadius: "var(--r-sm)",
                background: isSelected ? "var(--accent-soft)" : "transparent",
                color: isSelected ? "var(--accent)" : "var(--text)",
                fontSize: "var(--fs-sm)",
                fontWeight: "var(--fw-medium)",
                cursor: "pointer",
                fontFamily: "inherit",
                textAlign: "left",
                transition: "background var(--dur) var(--ease)",
              }}
              onMouseEnter={(e) => {
                if (!isSelected) (e.currentTarget as HTMLElement).style.background = "var(--state-hover)";
              }}
              onMouseLeave={(e) => {
                if (!isSelected) (e.currentTarget as HTMLElement).style.background = "transparent";
              }}
            >
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 20,
                  height: 20,
                  borderRadius: "var(--r-sm)",
                  background: "var(--accent-soft)",
                  color: "var(--accent)",
                  fontSize: 10,
                  flexShrink: 0,
                }}
              >
                {isSelected ? "●" : "○"}
              </span>
              <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {project.name}
              </span>
            </button>
          );
        })}

        <div style={{ marginTop: "var(--s-4)" }}>
          <div className="section-label">Versions</div>
          <div
            style={{
              color: "var(--muted)",
              fontSize: "var(--fs-xs)",
              padding: "var(--s-2)",
              textAlign: "center",
              border: "1px dashed var(--border)",
              borderRadius: "var(--r-sm)",
            }}
          >
            Select a work to view versions
          </div>
        </div>
      </div>

      <div
        style={{
          padding: "var(--s-2) var(--s-3)",
          borderTop: "1px solid var(--border)",
        }}
      >
        {signedIn ? (
          <button className="btn btn-ghost" onClick={signOut} style={{ width: "100%", justifyContent: "center" }}>
            Sign out
          </button>
        ) : (
          <button className="btn btn-ghost" onClick={signIn} style={{ width: "100%", justifyContent: "center" }}>
            Sign in
          </button>
        )}
      </div>
    </div>
  );
}
