/**
 * Studio state management hook.
 *
 * WHY: Studio.tsx was a 400+ line god component with 15+ useState hooks.
 * The constitution says "Keep state closest to where it is used" and
 * "Avoid business logic in components." This hook extracts ALL state
 * management into a testable, reusable unit.
 *
 * WHAT IT DOES:
 * - Manages tab navigation with URL sync
 * - Manages transcription results and analysis state
 * - Manages library file selection
 * - Manages visualization track selection
 * - Provides auth sign-in/sign-out
 * - Handles cross-tab data flow (transcribe → analyze)
 *
 * WHAT STUDIO.TSX DOES:
 * - Renders the UI layout
 * - Delegates state to this hook
 * - Passes state/callbacks to child components
 *
 * This separation means Studio.tsx is now a pure rendering component
 * that's easy to understand and modify.
 */

"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { clearTokenCache } from "@/lib/api";
import {
  analyzeAudio,
  notesToMidiBase64,
  saveTranscription,
  listLibrary,
  listTranscriptions,
  type TranscribeResult,
  type LibFile,
  type Transcription,
} from "@/lib/music";
import {
  loadLocalTranscription,
  saveLocalTranscription,
  saveTab,
  loadTab,
  saveLastResult,
  loadLastResult,
  saveAnalysis,
  loadAnalysis,
  saveAudioName,
  loadAudioName,
  saveSelectedTrack,
  loadSelectedTrack,
} from "@/lib/browser-store";

const TABS = [
  { id: "library", label: "Library" },
  { id: "transcribe", label: "Transform" },
  { id: "viz", label: "Visualize" },
  { id: "analyze", label: "Analyze" },
  { id: "chat", label: "Chat" },
] as const;

export type TabId = (typeof TABS)[number]["id"];
export { TABS };

export function useStudioState({
  initialTab = "transcribe",
  initialTrack,
  signedIn = false,
}: {
  initialTab?: string;
  initialTrack?: string;
  signedIn?: boolean;
}) {
  const router = useRouter();

  // ── Tab state ────────────────────────────────────────────────────────────
  const savedTab = loadTab();
  const safeInitial = savedTab && TABS.some((t) => t.id === savedTab)
    ? savedTab
    : TABS.some((t) => t.id === initialTab) ? initialTab : "transcribe";
  const [tab, setTab] = useState<TabId>(safeInitial as TabId);

  // ── Transcription state ──────────────────────────────────────────────────
  const [lastResult, setLastResult] = useState<TranscribeResult | null>(() => {
    const r = loadLastResult();
    return r as TranscribeResult | null;
  });
  const [audioName, setAudioName] = useState(loadAudioName);
  const [isTranscribing, setIsTranscribing] = useState(false);

  // ── Analysis state ───────────────────────────────────────────────────────
  const [analysis, setAnalysis] = useState<TranscribeResult["analysis"] | null>(loadAnalysis);
  const [analysisError, setAnalysisError] = useState("");
  const [analyzeStatus, setAnalyzeStatus] = useState("");
  const [analyzeLibFiles, setAnalyzeLibFiles] = useState<LibFile[]>([]);
  const [analyzeLoading, setAnalyzeLoading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // ── Library state ────────────────────────────────────────────────────────
  const [pendingLibFile, setPendingLibFile] = useState<LibFile | null>(null);
  const [transcriptions, setTranscriptions] = useState<Transcription[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);

  // ── Viz state ────────────────────────────────────────────────────────────
  const [vizTrackId, setVizTrackId] = useState<string | null>(() => initialTrack ?? loadSelectedTrack());
  const [vizSelectedId, setVizSelectedId] = useState<string>(() => initialTrack ?? loadSelectedTrack() ?? "");
  const vizStopRef = useRef<(() => void) | null>(null);

  // ── Effects ──────────────────────────────────────────────────────────────
  useEffect(() => { saveTab(tab); }, [tab]);

  useEffect(() => {
    const trackId = vizTrackId ?? vizSelectedId;
    if (trackId) saveSelectedTrack(trackId);
    else saveSelectedTrack(null);
  }, [vizTrackId, vizSelectedId]);

  useEffect(() => {
    if (tab !== "viz" && vizStopRef.current) {
      vizStopRef.current();
      vizStopRef.current = null;
    }
  }, [tab]);

  useEffect(() => {
    if (signedIn) {
      listLibrary().catch((e) => console.warn("Failed to load library:", e));
    }
  }, [signedIn]);

  useEffect(() => {
    if (tab === "analyze") {
      setAnalyzeLoading(true);
      listLibrary().then((lib) => {
        const local = loadLocalTranscription();
        const localFile = local && local.notes.length > 0 ? [{
          name: local.name,
          url: local.audioDataUrl || "",
          id: "__local__",
          notes: local.notes,
          midi_base64: local.midi_base64,
          analysis: local.analysis,
        } as LibFile] : [];
        setAnalyzeLibFiles([...localFile, ...lib]);
      }).catch((e) => console.warn("Failed to load library for analyze:", e))
        .finally(() => setAnalyzeLoading(false));
    }
    if (tab === "library" && signedIn) {
      listTranscriptions().then(setTranscriptions).catch(() => setTranscriptions([]));
    }
  }, [tab, signedIn]);

  // ── Actions ──────────────────────────────────────────────────────────────
  function goToTab(id: TabId) {
    setTab(id);
    router.replace(`/?tab=${id}`, { scroll: false });
  }

  function refreshTranscriptions() {
    if (signedIn) {
      listTranscriptions().then(setTranscriptions).catch(() => setTranscriptions([]));
      setRefreshKey((k) => k + 1);
    }
  }

  function onTranscribed(result: TranscribeResult, name: string) {
    setLastResult(result);
    setAudioName(name);
    setAnalysis(result.analysis ?? null);
    setAnalysisError("");
    saveLastResult(result);
    saveAudioName(name);
    if (result.analysis) saveAnalysis(result.analysis);
  }

  async function handleAnalyze(midiBase64?: string, name?: string, libraryFileId?: string) {
    if (isAnalyzing) return;
    if (name) setAudioName(name);
    if (!midiBase64) {
      setAnalysisError("Transcribe a track first, then analyze it");
      goToTab("analyze");
      return;
    }
    if (analysis && name && audioName === name) {
      goToTab("analyze");
      return;
    }
    setAnalyzeStatus("Analyzing…");
    setAnalysisError("");
    setIsAnalyzing(true);
    try {
      const result = await analyzeAudio(midiBase64);
      setAnalysis(result);
      saveAnalysis(result);

      if (libraryFileId && signedIn) {
        try {
          const libFile = analyzeLibFiles.find(f => f.id === libraryFileId);
          await saveTranscription(libraryFileId, libFile?.notes ?? lastResult?.notes ?? [], midiBase64, result);
          refreshTranscriptions();
        } catch {
          console.error("save analysis failed");
        }
      } else if (!signedIn) {
        const local = loadLocalTranscription();
        if (local) {
          saveLocalTranscription(local.name, local.notes, local.midi_base64, local.audioBlob, result);
        }
      }
      goToTab("analyze");
    } catch (err) {
      setAnalysisError(err instanceof Error ? err.message : "analysis failed");
    } finally {
      setAnalyzeStatus("");
      setIsAnalyzing(false);
      // Refresh library files so deriveTrackState picks up the new analysis
      listLibrary().then(setAnalyzeLibFiles).catch(() => {});
    }
  }

  async function handleAnalyzeLibrary(item: LibFile) {
    setAudioName(item.name);
    saveAudioName(item.name);
    if (item.analysis) {
      setAnalysis(item.analysis);
      saveAnalysis(item.analysis);
      goToTab("analyze");
      return;
    }
    let midi = item.midi_base64;
    if (!midi && item.notes && item.notes.length > 0) {
      midi = notesToMidiBase64(item.notes);
    }
    await handleAnalyze(midi, item.name, item.id);
  }

  function handleLibraryTranscribe(file: LibFile) {
    setPendingLibFile(file);
    goToTab("transcribe");
  }

  function handleLibraryAnalyze(file: LibFile) {
    goToTab("analyze");
    handleAnalyzeLibrary(file);
  }

  function handleLibraryVisualize(file: LibFile) {
    setVizTrackId(file.id);
    goToTab("viz");
  }

  function handleTrackDeleted(deletedId: string) {
    if (vizTrackId === deletedId) setVizTrackId(null);
    if (vizSelectedId === deletedId) setVizSelectedId("");
    saveSelectedTrack(null);
    // Clear analysis if the deleted track was the analyzed one
    if (lastResult && audioName) {
      setAnalysis(null);
      setAnalysisError("");
    }
  }

  async function signIn() {
    if (!supabase) return;
    const callbackUrl = `${window.location.origin}/auth/callback`;
    const currentPath = window.location.pathname + window.location.search;
    const redirectTo = currentPath && currentPath !== "/" ? `${callbackUrl}?next=${encodeURIComponent(currentPath)}` : callbackUrl;
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo },
    });
  }

  async function signOut() {
    clearTokenCache();
    await supabase?.auth.signOut();
    window.location.reload();
  }

  return {
    // State
    tab,
    lastResult,
    audioName,
    analysis,
    analysisError,
    analyzeStatus,
    analyzeLibFiles,
    analyzeLoading,
    pendingLibFile,
    transcriptions,
    refreshKey,
    vizTrackId,
    vizSelectedId,
    isTranscribing,
    isAnalyzing,
    vizStopRef,
    signedIn,
    // Actions
    goToTab,
    onTranscribed,
    handleAnalyze,
    handleAnalyzeLibrary,
    handleLibraryTranscribe,
    handleLibraryAnalyze,
    handleLibraryVisualize,
    handleTrackDeleted,
    signIn,
    signOut,
    setIsTranscribing,
    setVizTrackId,
    setVizSelectedId,
    setPendingLibFile,
    setAnalysis,
    setAnalysisError,
    refreshTranscriptions,
  };
}
