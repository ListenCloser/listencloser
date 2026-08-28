"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import type { Insight } from "@/lib/domain.types";
import type { Project, Work } from "@/lib/domain.types";
import type { RepresentationId } from "@/lib/representations";
import type { AskMessage } from "@/lib/ask/types";

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

export type AnalysisState = "idle" | "analyzing" | "completed";

export type SelectionOrigin = "waveform" | "piano_roll" | "score" | "spectrogram" | null;

export type MusicalSelection = {
  timeRange?: { start: number; end: number; domain: "performance" | "notation" };
  noteIds?: string[];
  measureRange?: { start: number; end: number };
  provenance: {
    origin: SelectionOrigin;
    timeExact: boolean;
    measureApproximate: boolean;
  };
};

export type TranscriptionProfile = "auto" | "solo_piano";

type WorkspaceState = {
  project: Project | null;
  works: Work[];
  activeWorkId: string | null;
  isLoadingWork: boolean;
  importRequestId: number;
  libraryCollapsed: boolean;
  inspectorCollapsed: boolean;
  inspectorMode: "analysis" | "ask";
  askConversation: AskMessage[];
  representations: RepresentationEntry[];
  insights: Insight[];
  takes: StudioTake[];
  studioAction: { id: number; kind: "variation" | "compare"; versionIds: string[]; semitones?: number } | null;
  studioOperation: StudioOperation;
  activeRepresentation: RepresentationId | null;
  selection: MusicalSelection | null;
  transcriptionProfile: TranscriptionProfile;
  analysisState: AnalysisState;
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
  setInspectorMode: (mode: "analysis" | "ask") => void;
  appendAskMessage: (message: AskMessage) => void;
  clearAskConversation: () => void;
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
  setTranscriptionProfile: (profile: TranscriptionProfile) => void;
  setAnalysisState: (state: AnalysisState) => void;
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

function representationKindToKnown(kind: RepresentationKind): RepresentationId | null {
  switch (kind) {
    case "waveform": return "listen";
    case "piano_roll": return "piano_roll";
    case "score": return "score";
    default: return null;
  }
}

export function useWorkspace(): WorkspaceContextValue {
  const ctx = useContext(WorkspaceContext);
  if (!ctx) throw new Error("useWorkspace must be used within WorkspaceProvider");
  return ctx;
}

export function WorkspaceProvider({
  children,
  initialLoading = false,
}: {
  children: ReactNode;
  initialLoading?: boolean;
}) {
  const [workspace, setWorkspace] = useState<WorkspaceState>({
    project: null,
    works: [],
    activeWorkId: null,
    // The signed-in app opts into this during session/library hydration. Tests
    // and isolated consumers keep normal work-loading semantics by default.
    isLoadingWork: initialLoading,
    importRequestId: 0,
    libraryCollapsed: false,
    inspectorCollapsed: false,
    inspectorMode: "analysis",
    askConversation: [],
    representations: [],
    insights: [],
    takes: [],
    studioAction: null,
    studioOperation: { state: "idle", label: "" },
    activeRepresentation: null,
    selection: null,
    transcriptionProfile: "auto",
    analysisState: "idle",
  });

  const setProject = useCallback((project: Project | null) => setWorkspace((prev) => ({ ...prev, project })), []);
  const setWorks = useCallback((works: Work[]) => setWorkspace((prev) => ({ ...prev, works })), []);

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
        askConversation: [],
        analysisState: "idle",
      };
    });
  }, []);

  const setLoadingWork = useCallback((isLoadingWork: boolean) => setWorkspace((prev) => ({ ...prev, isLoadingWork })), []);
  const requestImport = useCallback(() => setWorkspace((prev) => ({ ...prev, importRequestId: prev.importRequestId + 1 })), []);
  const toggleLibrary = useCallback(() => setWorkspace((prev) => ({ ...prev, libraryCollapsed: !prev.libraryCollapsed })), []);

  const removeWork = useCallback((workId: string) => {
    setWorkspace((prev) => {
      const removingActive = prev.activeWorkId === workId;
      return {
        ...prev,
        works: prev.works.filter((work) => work.id !== workId),
        activeWorkId: removingActive ? null : prev.activeWorkId,
        representations: removingActive ? [] : prev.representations,
        insights: removingActive ? [] : prev.insights,
        takes: removingActive ? [] : prev.takes,
        studioAction: removingActive ? null : prev.studioAction,
        studioOperation: removingActive ? { state: "idle", label: "" } : prev.studioOperation,
        activeRepresentation: removingActive ? null : prev.activeRepresentation,
        selection: removingActive ? null : prev.selection,
        askConversation: removingActive ? [] : prev.askConversation,
        isLoadingWork: removingActive ? false : prev.isLoadingWork,
        analysisState: removingActive ? "idle" : prev.analysisState,
      };
    });
  }, []);

  const restoreWork = useCallback((work: Work) => {
    setWorkspace((prev) => prev.works.some((item) => item.id === work.id) ? prev : { ...prev, works: [...prev.works, work] });
  }, []);

  const toggleInspector = useCallback(() => setWorkspace((prev) => ({ ...prev, inspectorCollapsed: !prev.inspectorCollapsed })), []);
  const setInspectorMode = useCallback((inspectorMode: "analysis" | "ask") => setWorkspace((prev) => ({ ...prev, inspectorMode })), []);
  const appendAskMessage = useCallback((message: AskMessage) => setWorkspace((prev) => ({ ...prev, askConversation: [...prev.askConversation, message] })), []);
  const clearAskConversation = useCallback(() => setWorkspace((prev) => ({ ...prev, askConversation: [] })), []);

  const addRepresentation = useCallback((rep: RepresentationEntry) => {
    setWorkspace((prev) => {
      const existing = prev.representations.find((item) => item.kind === rep.kind);
      if (existing) {
        return { ...prev, representations: prev.representations.map((item) => item.kind === rep.kind ? rep : item) };
      }
      return {
        ...prev,
        representations: [...prev.representations, rep],
        activeRepresentation: prev.activeRepresentation ?? representationKindToKnown(rep.kind),
      };
    });
  }, []);

  const setInsights = useCallback((insights: Insight[]) => setWorkspace((prev) => ({ ...prev, insights })), []);
  const setTakes = useCallback((takes: StudioTake[]) => setWorkspace((prev) => ({ ...prev, takes })), []);
  const requestVariation = useCallback((versionId: string, semitones: number) => setWorkspace((prev) => ({ ...prev, studioAction: { id: (prev.studioAction?.id ?? 0) + 1, kind: "variation", versionIds: [versionId], semitones } })), []);
  const requestComparison = useCallback((versionIdA: string, versionIdB: string) => setWorkspace((prev) => ({ ...prev, studioAction: { id: (prev.studioAction?.id ?? 0) + 1, kind: "compare", versionIds: [versionIdA, versionIdB] } })), []);
  const setStudioOperation = useCallback((studioOperation: StudioOperation) => setWorkspace((prev) => ({ ...prev, studioOperation })), []);
  const replaceRepresentations = useCallback((representations: RepresentationEntry[]) => setWorkspace((prev) => ({ ...prev, representations, activeRepresentation: prev.activeRepresentation ?? null })), []);
  const setActiveRepresentation = useCallback((activeRepresentation: RepresentationId | null) => setWorkspace((prev) => prev.activeRepresentation === activeRepresentation ? prev : { ...prev, activeRepresentation }), []);
  const setSelection = useCallback((selection: MusicalSelection | null) => setWorkspace((prev) => ({ ...prev, selection })), []);
  const clearSelection = useCallback(() => setWorkspace((prev) => ({ ...prev, selection: null })), []);
  const setTranscriptionProfile = useCallback((transcriptionProfile: TranscriptionProfile) => setWorkspace((prev) => prev.transcriptionProfile === transcriptionProfile ? prev : { ...prev, transcriptionProfile }), []);
  const setAnalysisState = useCallback((analysisState: AnalysisState) => setWorkspace((prev) => ({ ...prev, analysisState })), []);

  return (
    <WorkspaceContext.Provider value={{
      workspace,
      setProject,
      setWorks,
      setActiveWorkId,
      setLoadingWork,
      requestImport,
      toggleLibrary,
      toggleInspector,
      setInspectorMode,
      appendAskMessage,
      clearAskConversation,
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
      setTranscriptionProfile,
      setAnalysisState,
    }}>
      {children}
    </WorkspaceContext.Provider>
  );
}
