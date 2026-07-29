"use client";

import { useEffect, useState } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import WorkspaceShell from "@/components/workspace/WorkspaceShell";

function InitProject({ onProjectName }: { onProjectName: (name: string) => void }) {
  const { addRepresentation } = useWorkspace();

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const res = await fetch("/api/v1/projects", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: "My First Project" }) });
        const p = await res.json();
        if (cancelled) return;
        onProjectName(p.name);

        addRepresentation({ kind: "piano_roll", label: "Piano Roll", sourceUrl: "#", sourceLabel: p.name, confidence: null, provenance: "project" });
        addRepresentation({ kind: "waveform", label: "Waveform", sourceUrl: "#", sourceLabel: p.name, confidence: null, provenance: "project" });
      } catch {
        if (!cancelled) onProjectName("hello-ai");
      }
    }
    init();
    return () => { cancelled = true; };
  }, [addRepresentation, onProjectName]);

  return null;
}

export default function Home() {
  const [projectName, setProjectName] = useState("");

  return (
    <WorkspaceShell projectName={projectName}>
      <InitProject onProjectName={setProjectName} />
    </WorkspaceShell>
  );
}
