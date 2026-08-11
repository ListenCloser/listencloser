"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import type { Insight } from "@/lib/domain.types";
import type { Project, Work } from "@/lib/domain.types";

export type RepresentationKind =
  | "piano_roll"
  | "waveform"
  | "spectrogram"
  | "score"
  | "harmony"
  | "structure"
  | "annotations";

type Note = { pitch: number; start: number; end: number; velocity: number };

export type RepresentationEntry = {
  kind: RepresentationKind;
  label: string;
  sourceUrl: string;
  sourceLabel: string;
  confidence: number | null;
  provenance: string;
  notes?: Note[];
  musicxml?: string;
  audioUrl?: string;
  versionId?: string;
};

export type StudioTake = {
  versionId: string;
  label: string;
  parentVersionId: string | null;
  audioUrl?: string;
};

export type StudioOperation = {
  state: "idle" | "running" | "success" | "error" | "disconnected";
  label: string;
  message?: string;
};

type WorkspaceState = {
  project: Project | null;
  works: Work[];
  activeWorkId: string | null;
  isLoadingWork: boolean;
  importRequestId: number;
  libraryCollapsed: boolean;
  inspectorCollapsed: boolean;
  representations: RepresentationEntry[];
  insights: Insight[];
  takes: StudioTake[];
  studioAction: { id: number; kind: "variation" | "compare"; versionIds: string[]; semitones?: number } | null;
  studioOperation: StudioOperation;
  expandedRepresentation: RepresentationKind | null;
  focusRepresentation: RepresentationKind | null;
};

type WorkspaceContextValue = {
  workspace: WorkspaceState;
  setProject: (project: Project | null) => void;
  setWorks: (works: Work[]) => void;
  setActiveWorkId: (workId: string | null) => void;
  setLoadingWork: (loading: boolean) => void;
  requestImport: () => void;
  toggleLibrary: () => void;
  toggleInspector: () => void;
  removeWork: (workId: string) => void;
  addRepresentation: (rep: RepresentationEntry) => void;
  replaceRepresentations: (reps: RepresentationEntry[]) => void;
  setInsights: (insights: Insight[]) => void;
  setTakes: (takes: StudioTake[]) => void;
  requestVariation: (versionId: string, semitones: number) => void;
  requestComparison: (versionIdA: string, versionIdB: string) => void;
  setStudioOperation: (operation: StudioOperation) => void;
  removeRepresentation: (kind: RepresentationKind) => void;
  expandRepresentation: (kind: RepresentationKind | null) => void;
  focusRepresentation: (kind: RepresentationKind | null) => void;
  reorderRepresentations: (fromIndex: number, toIndex: number) => void;
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [workspace, setWorkspace] = useState<WorkspaceState>({
    project: null,
    works: [],
    activeWorkId: null,
    isLoadingWork: false,
    importRequestId: 0,
    libraryCollapsed: false,
    inspectorCollapsed: false,
    representations: [],
    insights: [],
    takes: [],
    studioAction: null,
    studioOperation: { state: "idle", label: "" },
    expandedRepresentation: null,
    focusRepresentation: null,
  });

  const setProject = useCallback((project: Project | null) => {
    setWorkspace((prev) => ({ ...prev, project }));
  }, []);

  const setWorks = useCallback((works: Work[]) => {
    setWorkspace((prev) => ({ ...prev, works }));
  }, []);

  const setActiveWorkId = useCallback((activeWorkId: string | null) => {
    setWorkspace((prev) => {
      if (prev.activeWorkId === activeWorkId) return prev;
      return {
        ...prev,
        activeWorkId,
        isLoadingWork: Boolean(activeWorkId),
        representations: [],
        insights: [],
        takes: [],
        expandedRepresentation: null,
        focusRepresentation: null,
      };
    });
  }, []);

  const setLoadingWork = useCallback((isLoadingWork: boolean) => {
    setWorkspace((prev) => ({ ...prev, isLoadingWork }));
  }, []);

  const requestImport = useCallback(() => {
    setWorkspace((prev) => ({
      ...prev,
      importRequestId: prev.importRequestId + 1,
    }));
  }, []);

  const toggleLibrary = useCallback(() => {
    setWorkspace((prev) => ({ ...prev, libraryCollapsed: !prev.libraryCollapsed }));
  }, []);

  const removeWork = useCallback((workId: string) => {
    setWorkspace((prev) => ({
      ...prev,
      works: prev.works.filter((w) => w.id !== workId),
      activeWorkId: prev.activeWorkId === workId ? null : prev.activeWorkId,
      representations: prev.activeWorkId === workId ? [] : prev.representations,
      insights: prev.activeWorkId === workId ? [] : prev.insights,
    }));
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

  const setInsights = useCallback((insights: Insight[]) => {
    setWorkspace((prev) => ({ ...prev, insights }));
  }, []);

  const setTakes = useCallback((takes: StudioTake[]) => {
    setWorkspace((prev) => ({ ...prev, takes }));
  }, []);

  const requestVariation = useCallback((versionId: string, semitones: number) => {
    setWorkspace((prev) => ({
      ...prev,
      studioAction: { id: (prev.studioAction?.id ?? 0) + 1, kind: "variation", versionIds: [versionId], semitones },
    }));
  }, []);

  const requestComparison = useCallback((versionIdA: string, versionIdB: string) => {
    setWorkspace((prev) => ({
      ...prev,
      studioAction: { id: (prev.studioAction?.id ?? 0) + 1, kind: "compare", versionIds: [versionIdA, versionIdB] },
    }));
  }, []);

  const setStudioOperation = useCallback((studioOperation: StudioOperation) => {
    setWorkspace((prev) => ({ ...prev, studioOperation }));
  }, []);

  const replaceRepresentations = useCallback((representations: RepresentationEntry[]) => {
    setWorkspace((prev) => ({
      ...prev,
      representations,
      expandedRepresentation: representations[0]?.kind ?? null,
      focusRepresentation: null,
    }));
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

  return (
    <WorkspaceContext.Provider
      value={{
        workspace,
        setProject,
        setWorks,
        setActiveWorkId,
        setLoadingWork,
        requestImport,
        toggleLibrary,
        toggleInspector,
        removeWork,
        addRepresentation,
        replaceRepresentations,
        setInsights,
        setTakes,
        requestVariation,
        requestComparison,
        setStudioOperation,
        removeRepresentation,
        expandRepresentation,
        focusRepresentation,
        reorderRepresentations,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}
