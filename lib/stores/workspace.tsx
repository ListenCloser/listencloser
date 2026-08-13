"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import type { Insight } from "@/lib/domain.types";
import type { Project, Work } from "@/lib/domain.types";
import type { RepresentationId } from "@/lib/representations";

export type RepresentationKind =
  | "piano_roll"
  | "waveform"
  | "spectrogram"
  | "score"
  | "harmony"
  | "structure"
  | "annotations";

type Note = { id?: string; pitch: number; start: number; end: number; velocity: number };

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
  measureStarts?: number[];
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

/**
 * Shared musical selection across representations.
 *
 * Owned by the WorkSession (not per representation). Exactly the fields that
 * can be mapped honestly are set, never fabricated:
 *   - timeRange  — seconds in the currently active playback source's timeline.
 *   - noteIds    — piano-roll note ids (a direct, exact reading).
 *   - measureRange — score measure indices (a direct, exact reading on the score).
 * Composing fields (e.g. timeRange derived from measures, or measures derived
 * from time) is kept coarse and marked in `provenance`, never presented as an
 * exact cross-timing-domain mapping.
 */
export type SelectionOrigin = "waveform" | "piano_roll" | "score" | null;

export type MusicalSelection = {
  timeRange?: { start: number; end: number };
  noteIds?: string[];
  measureRange?: { start: number; end: number };
  provenance: {
    origin: SelectionOrigin;
    /** True when timeRange is a direct reading in the active source's
        timeline (waveform and piano-roll selections). False when the
        timeRange was composed from measure data (approximate). */
    timeExact: boolean;
    /** True when measureRange was composed from a time-based selection
        (approximate). False for direct score measure selections. */
    measureApproximate: boolean;
  };
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
  activeRepresentation: RepresentationId | null;
  selection: MusicalSelection | null;
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
  restoreWork: (work: Work) => void;
  addRepresentation: (rep: RepresentationEntry) => void;
  replaceRepresentations: (reps: RepresentationEntry[]) => void;
  setInsights: (insights: Insight[]) => void;
  setTakes: (takes: StudioTake[]) => void;
  requestVariation: (versionId: string, semitones: number) => void;
  requestComparison: (versionIdA: string, versionIdB: string) => void;
  setStudioOperation: (operation: StudioOperation) => void;
  setActiveRepresentation: (representation: RepresentationId | null) => void;
  setSelection: (selection: MusicalSelection | null) => void;
  clearSelection: () => void;
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

function representationKindToKnown(kind: RepresentationKind): RepresentationId | null {
  switch (kind) {
    case "waveform":
      return "listen";
    case "piano_roll":
      return "piano_roll";
    case "score":
      return "score";
    default:
      return null;
  }
}

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
    activeRepresentation: null,
    selection: null,
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
        studioAction: null,
        studioOperation: { state: "idle", label: "" },
        activeRepresentation: null,
        selection: null,
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
    setWorkspace((prev) => {
      const removingActive = prev.activeWorkId === workId;
      return {
        ...prev,
        works: prev.works.filter((w) => w.id !== workId),
        activeWorkId: removingActive ? null : prev.activeWorkId,
        representations: removingActive ? [] : prev.representations,
        insights: removingActive ? [] : prev.insights,
        takes: removingActive ? [] : prev.takes,
        studioAction: removingActive ? null : prev.studioAction,
        studioOperation: removingActive ? { state: "idle", label: "" } : prev.studioOperation,
        activeRepresentation: removingActive ? null : prev.activeRepresentation,
        selection: removingActive ? null : prev.selection,
        isLoadingWork: removingActive ? false : prev.isLoadingWork,
      };
    });
  }, []);

  const restoreWork = useCallback((work: Work) => {
    setWorkspace((prev) => {
      if (prev.works.some((w) => w.id === work.id)) return prev;
      return { ...prev, works: [...prev.works, work] };
    });
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
        activeRepresentation: prev.activeRepresentation ?? representationKindToKnown(rep.kind),
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
      activeRepresentation: prev.activeRepresentation ?? null,
    }));
  }, []);

  const setActiveRepresentation = useCallback((representation: RepresentationId | null) => {
    setWorkspace((prev) => ({
      ...prev,
      activeRepresentation: representation,
    }));
  }, []);

  const setSelection = useCallback((selection: MusicalSelection | null) => {
    setWorkspace((prev) => ({
      ...prev,
      selection,
    }));
  }, []);

  const clearSelection = useCallback(() => {
    setWorkspace((prev) => ({
      ...prev,
      selection: null,
    }));
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
        restoreWork,
        addRepresentation,
        replaceRepresentations,
        setInsights,
        setTakes,
        requestVariation,
        requestComparison,
        setStudioOperation,
        setActiveRepresentation,
        setSelection,
        clearSelection,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  );
}
