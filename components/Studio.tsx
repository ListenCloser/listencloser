"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";
import { clearTokenCache } from "@/lib/api";
import Library from "./library";
import Transform from "./transcribe";
import Analysis from "./analyze";
import Viz from "./viz";
import MusicChat from "./MusicChat";
import { analyzeAudio, notesToMidiBase64, saveTranscription, listLibrary, listTranscriptions, formatTime, type TranscribeResult, type LibFile, type Transcription } from "@/lib/music";
import {
  loadLocalTranscription, saveLocalTranscription, type LocalTranscription,
  saveTab, loadTab,
  saveLastResult, loadLastResult,
  saveAnalysis, loadAnalysis,
  saveAudioName, loadAudioName,
} from "@/lib/browser-store";
import { SharedAudioProvider, useSharedAudio } from "@/lib/audio-context";


const TABS = [
  { id: "library", label: "Library" },
  { id: "transcribe", label: "Transform" },
  { id: "viz", label: "Visualize" },
  { id: "analyze", label: "Analyze" },
  { id: "chat", label: "Chat" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function Studio({
  initialTab = "transcribe",
  signedIn = false,
}: {
  initialTab?: string;
  signedIn?: boolean;
}) {
  const router = useRouter();

  const savedTab = loadTab();
  const safeInitial = savedTab && TABS.some((t) => t.id === savedTab)
    ? savedTab
    : TABS.some((t) => t.id === initialTab) ? initialTab : "transcribe";
  const [tab, setTab] = useState<TabId>(safeInitial as TabId);

  const [lastResult, setLastResult] = useState<TranscribeResult | null>(() => {
    const r = loadLastResult();
    return r as TranscribeResult | null;
  });
  const [audioName, setAudioName] = useState(loadAudioName);
  const [analysis, setAnalysis] = useState<TranscribeResult["analysis"] | null>(loadAnalysis);
  const [analysisError, setAnalysisError] = useState("");
  const [analyzeStatus, setAnalyzeStatus] = useState("");
  const [analyzeLibFiles, setAnalyzeLibFiles] = useState<LibFile[]>([]);
  const [pendingLibFile, setPendingLibFile] = useState<LibFile | null>(null);
  const [transcriptions, setTranscriptions] = useState<Transcription[]>([]);
  const [refreshKey, setRefreshKey] = useState(0);
  const [vizTrackId, setVizTrackId] = useState<string | null>(null);
  const [vizSelectedId, setVizSelectedId] = useState<string>("");
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const vizStopRef = useRef<(() => void) | null>(null);

  useEffect(() => { saveTab(tab); }, [tab]);

  useEffect(() => {
    if (tab !== "viz" && vizStopRef.current) {
      vizStopRef.current();
      vizStopRef.current = null;
    }
  }, [tab]);

  useEffect(() => {
    if (signedIn) {
      listLibrary().catch(() => {});
    }
  }, [signedIn]);

  useEffect(() => {
    if (tab === "analyze") {
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
      }).catch(() => {});
    }
    if (tab === "library" && signedIn) {
      listTranscriptions().then(setTranscriptions).catch(() => setTranscriptions([]));
    }
  }, [tab, signedIn]);

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
    }
  }

  function goToTab(id: TabId) {
    setTab(id);
    router.replace(`/?tab=${id}`, { scroll: false });
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

  return (
    <SharedAudioProvider>
    <div className="page">
      <header className="topbar" style={{ justifyContent: "space-between" }}>
        <div className="brand">
          <span className="brand-dot" />
          Music Studio
        </div>
        <nav className="nav">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={`nav-item${tab === t.id ? " active" : ""}`}
              onClick={() => goToTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="account">
          {signedIn ? (
            <button className="btn btn-ghost" onClick={signOut}>
              Sign out
            </button>
          ) : (
            <button className="btn btn-ghost" id="signInBtn" onClick={signIn}>
              Sign in
            </button>
          )}
        </div>
      </header>

      <div className="workbench">
        {tab === "library" && (
          <Library
            signedIn={signedIn}
            onSignIn={signIn}
            onTranscribe={handleLibraryTranscribe}
            onAnalyze={handleLibraryAnalyze}
            onVisualize={handleLibraryVisualize}
            transcriptions={transcriptions}
            refreshKey={refreshKey}
            isTranscribing={isTranscribing}
            isAnalyzing={isAnalyzing}
          />
        )}

        <div style={{ display: tab === "transcribe" ? "block" : "none" }}>
          <Transform
            signedIn={signedIn}
            onTranscribed={onTranscribed}
            onGoToAnalyze={() => goToTab("analyze")}
            onAnalyze={handleAnalyze}
            libraryFileToLoad={pendingLibFile}
            onClearLibraryFile={() => setPendingLibFile(null)}
            onTranscriptionSaved={refreshTranscriptions}
            onBusyChange={setIsTranscribing}
            onNewTranscription={() => {
              setAnalysis(null);
              setAnalysisError("");
              saveAnalysis(null);
              saveLastResult(null);
              saveAudioName("");
            }}
            analysis={analysis}
            initialResult={lastResult}
            initialAudioName={audioName}
          />
        </div>

        {tab === "viz" && (
          <Viz
            initialTrackId={vizTrackId}
            selectedId={vizSelectedId}
            onTrackSelected={(id) => { setVizTrackId(null); setVizSelectedId(id); }}
            onStopRef={vizStopRef}
          />
        )}

        {tab === "chat" && (
          <MusicChat
            onTranscribed={(result, name) => {
              onTranscribed(result, name);
              goToTab("transcribe");
            }}
            onAnalyzed={(midi, name) => {
              if (midi) handleAnalyze(midi, name);
              goToTab("analyze");
            }}
          />
        )}

        <div style={{ display: tab === "analyze" ? "block" : "none" }}>
          <div className="card">
            <h3 className="card-title"><span className="glyph">◈</span> Analyze</h3>

            {!analysis && !analyzeStatus && signedIn && analyzeLibFiles.filter(f => f.notes?.length).length === 0 && (
              <>
                <div className="section-label">Select a transcribed track</div>
                <p className="muted" style={{ textAlign: "center", margin: "var(--s-4) 0" }}>
                  No transcribed tracks in your library — transcribe one first.
                </p>
              </>
            )}

            {!analysis && !analyzeStatus && signedIn && analyzeLibFiles.filter(f => f.notes?.length).length > 0 && (
              <>
                <div className="section-label">Select a transcribed track</div>
                <div style={{ display: "flex", gap: "var(--s-2)", marginBottom: "var(--s-4)" }}>
                  <select
                    className="sel"
                    value=""
                    onChange={(e) => {
                      const file = analyzeLibFiles.find(f => f.id === e.target.value);
                      if (file) handleAnalyzeLibrary(file);
                    }}
                    style={{ flex: 1 }}
                  >
                    <option value="">-- Pick a track --</option>
                    {analyzeLibFiles.filter(f => f.notes?.length).map((f) => (
                      <option key={f.id} value={f.id}>{f.name}{f.analysis ? " ✓" : ""}</option>
                    ))}
                  </select>
                </div>
              </>
            )}

            {!analysis && !analyzeStatus && !signedIn && analyzeLibFiles.filter(f => f.notes?.length).length > 0 && (
              <div style={{ textAlign: "center", padding: "var(--s-4)" }}>
                <p className="muted" style={{ margin: "0 0 var(--s-3)" }}>
                  Using: <strong>{analyzeLibFiles.find(f => f.notes?.length)?.name}</strong>
                </p>
                <button className="btn btn-primary" onClick={() => {
                  const first = analyzeLibFiles.find(f => f.notes?.length);
                  if (first) handleAnalyzeLibrary(first);
                }}>
                  Analyze
                </button>
              </div>
            )}

            {!analysis && !analyzeStatus && !signedIn && analyzeLibFiles.filter(f => f.notes?.length).length === 0 && (
              <p className="muted" style={{ textAlign: "center", margin: "var(--s-4) 0" }}>
                Transcribe an audio song first — then come back to analyze.
              </p>
            )}

            {analyzeStatus && (
              <div style={{ marginBottom: "var(--s-3)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--s-2)", marginBottom: "var(--s-2)" }}>
                  <span className="status" style={{ fontSize: "var(--fs-sm)" }}>{analyzeStatus}</span>
                </div>
                <div style={{ height: 6, background: "var(--panel-3)", borderRadius: "var(--r-full)" }}>
                  <div className="pulse" style={{ height: "100%", width: "50%", background: "var(--accent)", borderRadius: "var(--r-full)" }} />
                </div>
                <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "var(--s-1) 0 0" }}>
                  Analyzing key, tempo, chords, Roman numerals, cadences…
                </p>
              </div>
            )}

            {analysisError && !analysis && !analyzeStatus && (
              <div className="alert-danger" style={{ marginBottom: "var(--s-3)" }}>
                <p className="status" style={{ color: "var(--danger)", margin: 0 }}>⚠️ {analysisError}</p>
              </div>
            )}

            {analysis && (
              <>
                <Analysis
                  analysis={analysis}
                  notes={lastResult?.notes ?? []}
                  audioName={audioName}
                  numNotes={lastResult?.num_notes ?? 0}
                />
                {signedIn && (
                  <div className="toolbar" style={{ marginTop: "var(--s-4)" }}>
                    <button className="btn" onClick={() => { setAnalysis(null); setAnalysisError(""); listLibrary().then(setAnalyzeLibFiles).catch(() => {}); }}>
                      ← Analyze another track
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      <div className="toast" id="toast" />
    </div>
    </SharedAudioProvider>
  );
}
