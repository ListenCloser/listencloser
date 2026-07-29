"use client";

import { useEffect } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import WorkspaceShell from "@/components/workspace/WorkspaceShell";

function SeedWorkspace() {
  const { addRepresentation } = useWorkspace();

  useEffect(() => {
    addRepresentation({
      kind: "piano_roll",
      label: "Piano Roll",
      sourceUrl: "#",
      sourceLabel: "Seed project",
      confidence: null,
      provenance: "seed",
    });
    addRepresentation({
      kind: "waveform",
      label: "Waveform",
      sourceUrl: "#",
      sourceLabel: "Seed project",
      confidence: null,
      provenance: "seed",
    });
  }, [addRepresentation]);

  return null;
}

export default function Home() {
  return (
    <WorkspaceShell>
      <SeedWorkspace />
    </WorkspaceShell>
  );
}
