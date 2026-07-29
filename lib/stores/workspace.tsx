"use client";

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";

const STORAGE_KEY = "hello-ai-workspace";

export type WorkspaceMode = "explore" | "compare" | "correct" | "create" | "history";

export type RepresentationKind =
  | "piano_roll"
  | "waveform"
  | "spectrogram"
  | "score"
  | "harmony"
  | "structure"
  | "annotations";

type Note = { pitch: number; start: number; end: number; velocity: number };

type RepresentationEntry = {
  kind: RepresentationKind;
  label: string;
  sourceUrl: string;
  sourceLabel: string;
  confidence: number | null;
  provenance: string;
  notes?: Note[];
};

type WorkspaceState = {
  mode: WorkspaceMode;
  libraryCollapsed: boolean;
  inspectorCollapsed: boolean;
  representations: RepresentationEntry[];
  expandedRepresentation: RepresentationKind | null;
  focusRepresentation: RepresentationKind | null;
  versionIds: string[];
  currentVersionId: string | null;
  midiVersionId: string | null;
};

type WorkspaceContextValue = {
  workspace: WorkspaceState;
  setMode: (mode: WorkspaceMode) => void;
  toggleLibrary: () => void;
  toggleInspector: () => void;
  addRepresentation: (rep: RepresentationEntry) => void;
  removeRepresentation: (kind: RepresentationKind) => void;
  expandRepresentation: (kind: RepresentationKind | null) => void;
  focusRepresentation: (kind: RepresentationKind | null) => void;
  reorderRepresentations: (fromIndex: number, toIndex: number) => void;
  addVersionId: (id: string, label?: string) => void;
  versions: { id: string; label: string }[];
  currentVersionId: string | null;
  midiVersionId: string | null;
  setMidiVersionId: (id: string) => void;
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [workspace, setWorkspace] = useState<WorkspaceState>(() => {
    if (typeof window === "undefined") return {
      mode: "explore", libraryCollapsed: false, inspectorCollapsed: false,
      representations: [], expandedRepresentation: null, focusRepresentation: null,
      versionIds: [], currentVersionId: null, midiVersionId: null,
    };
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) return { ...JSON.parse(saved), representations: [], midiVersionId: null };
    } catch { /* ignore */ }
    return {
      mode: "explore", libraryCollapsed: false, inspectorCollapsed: false,
      representations: [], expandedRepresentation: null, focusRepresentation: null,
      versionIds: [], currentVersionId: null, midiVersionId: null,
    };
  });

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(workspace));
    } catch { /* ignore */ }
  }, [workspace]);

  const setMode = useCallback((mode: WorkspaceMode) => {
    setWorkspace((prev) => ({ ...prev, mode }));
  }, []);

  const toggleLibrary = useCallback(() => {
    setWorkspace((prev) => ({ ...prev, libraryCollapsed: !prev.libraryCollapsed }));
  }, []);

  const toggleInspector = useCallback(() => {
    setWorkspace((prev) => ({ ...prev, inspectorCollapsed: !prev.inspectorCollapsed }));
  }, []);

  const addRepresentation = useCallback((rep: RepresentationEntry) => {
    setWorkspace((prev) => {
      const existing = prev.representations.find((r) => r.kind === rep.kind);
      if (existing) {
        return {
          ...prev,
          representations: prev.representations.map((r) => (r.kind === rep.kind ? rep : r)),
        };
      }
      return {
        ...prev,
        representations: [...prev.representations, rep],
        expandedRepresentation: prev.expandedRepresentation ?? rep.kind,
      };
    });
  }, []);

  const removeRepresentation = useCallback((kind: RepresentationKind) => {
    setWorkspace((prev) => {
      const filtered = prev.representations.filter((r) => r.kind !== kind);
      return {
        ...prev,
        representations: filtered,
        expandedRepresentation:
          prev.expandedRepresentation === kind
            ? filtered.length > 0
              ? filtered[0].kind
              : null
            : prev.expandedRepresentation,
        focusRepresentation:
          prev.focusRepresentation === kind ? null : prev.focusRepresentation,
      };
    });
  }, []);

  const expandRepresentation = useCallback((kind: RepresentationKind | null) => {
    setWorkspace((prev) => {
      if (prev.expandedRepresentation === kind) {
        return { ...prev, expandedRepresentation: null };
      }
      return { ...prev, expandedRepresentation: kind };
    });
  }, []);

  const focusRepresentation = useCallback((kind: RepresentationKind | null) => {
    setWorkspace((prev) => ({
      ...prev,
      focusRepresentation: prev.focusRepresentation === kind ? null : kind,
    }));
  }, []);

  const reorderRepresentations = useCallback((fromIndex: number, toIndex: number) => {
    setWorkspace((prev) => {
      const reps = [...prev.representations];
      const [moved] = reps.splice(fromIndex, 1);
      reps.splice(toIndex, 0, moved);
      return { ...prev, representations: reps };
    });
  }, []);

  const [versionLabels, setVersionLabels] = useState<Map<string, string>>(new Map());

  const addVersionId = useCallback((id: string, label?: string) => {
    setWorkspace((prev) => {
      if (prev.versionIds.includes(id)) return prev;
      return {
        ...prev,
        versionIds: [...prev.versionIds, id],
        currentVersionId: prev.currentVersionId ?? id,
      };
    });
    if (label) setVersionLabels((prev) => new Map(prev).set(id, label));
  }, []);

  const versions = workspace.versionIds.map((id) => ({ id, label: versionLabels.get(id) ?? id }));

  const setMidiVersionId = useCallback((id: string) => {
    setWorkspace((prev) => ({ ...prev, midiVersionId: id }));
  }, []);

  return (
    <WorkspaceContext.Provider
      value={{
        workspace,
        setMode,
        toggleLibrary,
        toggleInspector,
        addRepresentation,
        removeRepresentation,
        expandRepresentation,
        focusRepresentation,
        reorderRepresentations,
        addVersionId,
        versions,
        currentVersionId: workspace.currentVersionId,
        midiVersionId: workspace.midiVersionId,
        setMidiVersionId,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}
