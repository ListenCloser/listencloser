"use client";

import { useState, useEffect } from "react";

type Project = { id: string; name: string; created_at: string };

export default function LibraryPanel({ signedIn }: { signedIn: boolean }) {
  const [collapsed, setCollapsed] = useState(false);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let c = false;
    fetch("/api/v1/projects")
      .then((r) => r.json())
      .then((data) => { if (!c) { if (Array.isArray(data)) setProjects(data); else setError("Could not load projects"); } })
      .catch(() => { if (!c) setError("Backend unavailable"); })
      .finally(() => { if (!c) setLoading(false); });
    return () => { c = true; };
  }, []);

  if (collapsed) {
    return (
      <div style={{ width: 44, flexShrink: 0, background: "var(--panel)", borderRight: "1px solid var(--border)", display: "flex", flexDirection: "column", alignItems: "center", paddingTop: "var(--s-3)", gap: "var(--s-3)" }}>
        <button onClick={() => setCollapsed(false)} style={{ background: "none", border: "none", color: "var(--muted)", cursor: "pointer", fontSize: 14, padding: 4 }} title="Expand library">▸</button>
        {projects.slice(0, 5).map((p) => (
          <div key={p.id} style={{ width: 28, height: 28, borderRadius: "var(--r-sm)", background: "var(--accent-soft)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: "var(--accent)", fontWeight: "var(--fw-semibold)" }} title={p.name}>
            {p.name.charAt(0).toUpperCase()}
          </div>
        ))}
      </div>
    );
  }

  return (
    <div style={{ width: "var(--shell-sidebar, 260px)", flexShrink: 0, background: "var(--panel)", borderRight: "1px solid var(--border)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "var(--s-3) var(--s-4)", borderBottom: "1px solid var(--border)" }}>
        <span style={{ fontSize: "var(--fs-xs)", fontWeight: "var(--fw-semibold)", color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Library</span>
        <button onClick={() => setCollapsed(true)} style={{ background: "none", border: "none", color: "var(--muted)", cursor: "pointer", fontSize: 14, padding: 4 }} title="Collapse">◂</button>
      </div>

      <div style={{ flex: 1, overflow: "auto", padding: "var(--s-2) 0" }}>
        {loading && (
          <div style={{ padding: "var(--s-4)", textAlign: "center", color: "var(--muted)", fontSize: "var(--fs-xs)" }}>Loading...</div>
        )}
        {error && (
          <div style={{ padding: "var(--s-4)", textAlign: "center", color: "var(--muted)", fontSize: "var(--fs-xs)" }}>{error}</div>
        )}
        {!loading && !error && projects.length === 0 && (
          <div style={{ padding: "var(--s-4)", textAlign: "center", color: "var(--muted)", fontSize: "var(--fs-xs)" }}>No projects yet</div>
        )}
        {projects.map((p) => (
          <div key={p.id} style={{ padding: "var(--s-2) var(--s-4)", fontSize: "var(--fs-sm)", color: "var(--text)", cursor: "pointer", transition: "background var(--dur)" }}>
            {p.name}
          </div>
        ))}
      </div>
    </div>
  );
}
