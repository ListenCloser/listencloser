"use client";

import { useState } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { supabase } from "@/lib/supabase";

type MockWork = {
  id: string;
  title: string;
  composer: string | null;
};

type MockProject = {
  id: string;
  name: string;
  works: MockWork[];
};

const MOCK_PROJECTS: MockProject[] = [
  {
    id: "proj-1",
    name: "Chopin Preludes",
    works: [
      { id: "w1", title: "Prelude Op. 28 No. 4", composer: "Chopin" },
      { id: "w2", title: "Prelude Op. 28 No. 7", composer: "Chopin" },
    ],
  },
  {
    id: "proj-2",
    name: "My Compositions",
    works: [
      { id: "w3", title: "Untitled Sketch #1", composer: null },
      { id: "w4", title: "Untitled Sketch #2", composer: null },
    ],
  },
  {
    id: "proj-3",
    name: "Bach Studies",
    works: [
      { id: "w5", title: "Fugue in C minor", composer: "J.S. Bach" },
    ],
  },
];

export default function LibraryPanel({ signedIn = false }: { signedIn?: boolean }) {
  const { workspace, toggleLibrary } = useWorkspace();
  const [expandedProjects, setExpandedProjects] = useState<Set<string>>(new Set(["proj-1"]));
  const [selectedWorkId, setSelectedWorkId] = useState<string | null>(null);

  const toggleProject = (id: string) => {
    setExpandedProjects((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

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

        {MOCK_PROJECTS.slice(0, 4).map((p) => (
          <button
            key={p.id}
            className="icon-btn ghost"
            style={{
              padding: "6px",
              fontSize: 12,
              background: selectedWorkId && MOCK_PROJECTS.find((proj) =>
                proj.works.some((w) => w.id === selectedWorkId)
              )?.id === p.id ? "var(--accent-soft)" : undefined,
              color: selectedWorkId && MOCK_PROJECTS.find((proj) =>
                proj.works.some((w) => w.id === selectedWorkId)
              )?.id === p.id ? "var(--accent)" : "var(--muted)",
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
        {MOCK_PROJECTS.map((project) => (
          <div key={project.id} style={{ marginBottom: "var(--s-1)" }}>
            <button
              onClick={() => toggleProject(project.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--s-2)",
                width: "100%",
                padding: "var(--s-2) var(--s-2)",
                border: "none",
                borderRadius: "var(--r-sm)",
                background: "transparent",
                color: "var(--text)",
                fontSize: "var(--fs-sm)",
                fontWeight: "var(--fw-medium)",
                cursor: "pointer",
                fontFamily: "inherit",
                textAlign: "left",
                transition: "background var(--dur) var(--ease)",
              }}
              onMouseEnter={(e) => {
                (e.currentTarget as HTMLElement).style.background = "var(--state-hover)";
              }}
              onMouseLeave={(e) => {
                (e.currentTarget as HTMLElement).style.background = "transparent";
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
                {expandedProjects.has(project.id) ? "▾" : "▸"}
              </span>
              <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {project.name}
              </span>
              <span
                style={{
                  fontSize: "var(--fs-xs)",
                  color: "var(--muted)",
                  flexShrink: 0,
                }}
              >
                {project.works.length}
              </span>
            </button>

            {expandedProjects.has(project.id) && (
              <div style={{ paddingLeft: "var(--s-5)" }}>
                {project.works.map((work) => (
                  <button
                    key={work.id}
                    onClick={() =>
                      setSelectedWorkId(
                        selectedWorkId === work.id ? null : work.id
                      )
                    }
                    style={{
                      display: "flex",
                      flexDirection: "column",
                      gap: 2,
                      width: "100%",
                      padding: "var(--s-2) var(--s-2)",
                      border: "none",
                      borderRadius: "var(--r-sm)",
                      background:
                        selectedWorkId === work.id
                          ? "var(--accent-soft)"
                          : "transparent",
                      color:
                        selectedWorkId === work.id
                          ? "var(--accent)"
                          : "var(--muted)",
                      fontSize: "var(--fs-xs)",
                      cursor: "pointer",
                      fontFamily: "inherit",
                      textAlign: "left",
                      transition: "all var(--dur) var(--ease)",
                    }}
                    onMouseEnter={(e) => {
                      if (selectedWorkId !== work.id) {
                        (e.currentTarget as HTMLElement).style.color = "var(--text)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (selectedWorkId !== work.id) {
                        (e.currentTarget as HTMLElement).style.color = "var(--muted)";
                      }
                    }}
                  >
                    <span>{work.title}</span>
                    {work.composer && (
                      <span style={{ fontSize: 10, opacity: 0.6 }}>
                        {work.composer}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

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
