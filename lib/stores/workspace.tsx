"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";
import type { Insight } from "@/lib/domain.types";
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
export type ScoreEngine = "musescore" | "pm2s";

type WorkspaceState = {
  activeWorkId: string | null;
  isLoadingWork: boolean;
  importRequestId: number;
  libraryCollapsed: boolean;
  inspectorCollapsed: boolean;
  inspectorMode: "analysis" | "ask";
  askConversation: AskMessage[];
  representations: RepresentationEntry[];
  insights: Insight[];
  studioAction: { id: number; kind: "variation" | "compare"; versionIds: string[]; semitones?: number } | null;
  studioOperation: StudioOperation;
  activeRepresentation: RepresentationId | null;
  selection: MusicalSelection | null;
  transcriptionProfile: TranscriptionProfile;
  scoreEngine: ScoreEngine;
  scoreEngineAction: { id: number; engine: ScoreEngine } | null;
  analysisState: AnalysisState;
};

type WorkspaceContextValue = {
  workspace: WorkspaceState;
  setActiveWorkId: (workId: string | null) => void;
  setLoadingWork: (loading: boolean) => void;
  requestImport: () => void;
  toggleLibrary: () => void;
  toggleInspector: () => void;
  setInspectorMode: (mode: "analysis" | "ask") => void;
  appendAskMessage: (message: AskMessage) => void;
  clearAskConversation: () => void;
  replaceRepresentations: (reps: RepresentationEntry[]) => void;
  setInsights: (insights: Insight[]) => void;
  requestVariation: (versionId: string, semitones: number) => void;
  requestComparison: (versionIdA: string, versionIdB: string) => void;
  setStudioOperation: (operation: StudioOperation) => void;
  setActiveRepresentation: (representation: RepresentationId | null) => void;
  setSelection: (selection: MusicalSelection | null) => void;
  clearSelection: () => void;
  setTranscriptionProfile: (profile: TranscriptionProfile) => void;
  setScoreEngine: (engine: ScoreEngine) => void;
  requestScoreEngine: (engine: ScoreEngine) => void;
  setAnalysisState: (state: AnalysisState) => void;
};

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

function preserveImmutableRepresentationUrls(
  previous: RepresentationEntry[],
  incoming: RepresentationEntry[],
): RepresentationEntry[] {
  return incoming.map((next) => {
    if (!next.versionId) return next;
    const existing = previous.find(
      (item) => item.kind === next.kind && item.versionId === next.versionId,
    );
    if (!existing) return next;
    return {
      ...next,
      sourceUrl: existing.sourceUrl,
      ...(existing.audioUrl ? { audioUrl: existing.audioUrl } : {}),
    };
  });
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
    studioAction: null,
    studioOperation: { state: "idle", label: "" },
    activeRepresentation: null,
    selection: null,
    transcriptionProfile: "auto",
    scoreEngine: "musescore",
    scoreEngineAction: null,
    analysisState: "idle",
  });

  const setActiveWorkId = useCallback((activeWorkId: string | null) => {
    setWorkspace((prev) => {
      if (prev.activeWorkId === activeWorkId) return prev;
      return {
        ...prev,
        activeWorkId,
        isLoadingWork: Boolean(activeWorkId),
        representations: [],
        insights: [],
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
  const toggleInspector = useCallback(() => setWorkspace((prev) => ({ ...prev, inspectorCollapsed: !prev.inspectorCollapsed })), []);
  const setInspectorMode = useCallback((inspectorMode: "analysis" | "ask") => setWorkspace((prev) => ({ ...prev, inspectorMode })), []);
  const appendAskMessage = useCallback((message: AskMessage) => setWorkspace((prev) => ({ ...prev, askConversation: [...prev.askConversation, message] })), []);
  const clearAskConversation = useCallback(() => setWorkspace((prev) => ({ ...prev, askConversation: [] })), []);

  const setInsights = useCallback((insights: Insight[]) => setWorkspace((prev) => ({ ...prev, insights })), []);
  const requestVariation = useCallback((versionId: string, semitones: number) => setWorkspace((prev) => ({ ...prev, studioAction: { id: (prev.studioAction?.id ?? 0) + 1, kind: "variation", versionIds: [versionId], semitones } })), []);
  const requestComparison = useCallback((versionIdA: string, versionIdB: string) => setWorkspace((prev) => ({ ...prev, studioAction: { id: (prev.studioAction?.id ?? 0) + 1, kind: "compare", versionIds: [versionIdA, versionIdB] } })), []);
  const setStudioOperation = useCallback((studioOperation: StudioOperation) => setWorkspace((prev) => ({ ...prev, studioOperation })), []);
  const replaceRepresentations = useCallback((representations: RepresentationEntry[]) => setWorkspace((prev) => ({
    ...prev,
    representations: preserveImmutableRepresentationUrls(prev.representations, representations),
    activeRepresentation: prev.activeRepresentation ?? null,
  })), []);
  const setActiveRepresentation = useCallback((activeRepresentation: RepresentationId | null) => setWorkspace((prev) => prev.activeRepresentation === activeRepresentation ? prev : { ...prev, activeRepresentation }), []);
  const setSelection = useCallback((selection: MusicalSelection | null) => setWorkspace((prev) => ({ ...prev, selection })), []);
  const clearSelection = useCallback(() => setWorkspace((prev) => ({ ...prev, selection: null })), []);
  const setTranscriptionProfile = useCallback((transcriptionProfile: TranscriptionProfile) => setWorkspace((prev) => prev.transcriptionProfile === transcriptionProfile ? prev : { ...prev, transcriptionProfile }), []);
  const setScoreEngine = useCallback((scoreEngine: ScoreEngine) => setWorkspace((prev) => prev.scoreEngine === scoreEngine ? prev : { ...prev, scoreEngine }), []);
  const requestScoreEngine = useCallback((scoreEngine: ScoreEngine) => setWorkspace((prev) => ({
    ...prev,
    scoreEngine,
    scoreEngineAction: {
      id: (prev.scoreEngineAction?.id ?? 0) + 1,
      engine: scoreEngine,
    },
  })), []);
  const setAnalysisState = useCallback((analysisState: AnalysisState) => setWorkspace((prev) => ({ ...prev, analysisState })), []);

  return (
    <WorkspaceContext.Provider value={{
      workspace,
      setActiveWorkId,
      setLoadingWork,
      requestImport,
      toggleLibrary,
      toggleInspector,
      setInspectorMode,
      appendAskMessage,
      clearAskConversation,
      replaceRepresentations,
      setInsights,
      requestVariation,
      requestComparison,
      setStudioOperation,
      setActiveRepresentation,
      setSelection,
      clearSelection,
      setTranscriptionProfile,
      setScoreEngine,
      requestScoreEngine,
      setAnalysisState,
    }}>
      {children}
    </WorkspaceContext.Provider>
  );
}
