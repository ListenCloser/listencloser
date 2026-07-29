"use client";

import { useState, useCallback } from "react";
import { SharedAudioProvider } from "@/lib/audio-context";
import Library from "./library";
import Transform from "./transcribe";
import Analysis from "./analyze";
import Viz from "./viz";
import MusicChat from "./MusicChat";
import ExplainPanel from "./ExplainPanel";
import { analyzeAudio, notesToMidiBase64, saveTranscription, listLibrary, listTranscriptions, type TranscribeResult, type LibFile, type Transcription } from "@/lib/music";
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
  signedIn = false,
}: {
  signedIn?: boolean;
}) {
  const [selectedTrack, setSelectedTrack] = useState<LibFile | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);

  const handleTrackSelect = useCallback((file: LibFile) => {
    setSelectedTrack(file);
  }, []);

  const handleTrackDeleted = useCallback((id: string) => {
    setSelectedTrack((prev) => (prev?.id === id ? null : prev));
    setRefreshKey((k) => k + 1);
  }, []);

  const handleTrackUpdated = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  const handleTranscribed = useCallback((result: TranscribeResult, name: string) => {
    setSelectedTrack((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        notes: result.notes,
        midi_base64: result.midi_base64,
        analysis: result.analysis,
      };
    });
  }, []);

  const handleAnalyzed = useCallback((midiBase64?: string, name?: string) => {
    if (!midiBase64) return;
    analyzeAudio(midiBase64).then((result) => {
      setSelectedTrack((prev) => {
        if (!prev) return prev;
        return { ...prev, analysis: result };
      });
    }).catch(() => {});
  }, []);

  async function signIn() {
    if (!supabase) return;
    const callbackUrl = `${window.location.origin}/auth/callback`;
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: callbackUrl },
    });
  }

  async function signOut() {
    clearTokenCache();
    await supabase?.auth.signOut();
    window.location.reload();
  }

  return (
    <SharedAudioProvider>
      <div className="shell">
        {/* Left Sidebar — Library */}
        <aside className="shell-sidebar">
          <Library
            signedIn={signedIn}
            onSignIn={signedIn ? signOut : signIn}
            onTrackSelect={handleTrackSelect}
            onTrackDeleted={handleTrackDeleted}
            refreshKey={refreshKey}
            selectedTrackId={selectedTrack?.id}
          />
        </aside>

        {/* Main Content — Track Workspace */}
        <main className="shell-main">
          {selectedTrack ? (
            <TrackWorkspace
              file={selectedTrack}
              signedIn={signedIn}
              onTrackUpdated={handleTrackUpdated}
              autoProcess={true}
            />
          ) : (
            <div className="main-empty">
              <div className="main-empty-icon">♪</div>
              <div style={{ fontSize: "var(--fs-lg)", fontWeight: "var(--fw-semibold)" }}>Select a track</div>
              <div style={{ fontSize: "var(--fs-sm)" }}>Choose a song from the library to start working</div>
              {!signedIn && (
                <button className="btn btn-primary" onClick={signIn}>
                  Sign in to get started
                </button>
              )}
            </div>
          )}
        </main>

        {/* Right Panel — AI Chat */}
        <ChatPanel
          isOpen={chatOpen}
          onToggle={() => setChatOpen(!chatOpen)}
          selectedTrack={selectedTrack}
          onTranscribed={handleTranscribed}
          onAnalyzed={handleAnalyzed}
        />

        {/* FAB when chat is closed */}
        {!chatOpen && (
          <button className="chat-fab" onClick={() => setChatOpen(true)} title="Open AI Chat">
            AI
          </button>
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

            {!analysis && !analyzeStatus && signedIn && (
              <div className="section-label">Select a transcribed track</div>
            )}

            {!analysis && !analyzeStatus && signedIn && analyzeLibFiles.filter(f => f.notes?.length).length === 0 && (
              <p className="muted" style={{ textAlign: "center", margin: "var(--s-4) 0" }}>
                No transcribed tracks in your library — transcribe one first.
              </p>
            )}

            {!analysis && !analyzeStatus && signedIn && analyzeLibFiles.filter(f => f.notes?.length).length > 0 && (
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
            )}

            {!analysis && !analyzeStatus && !signedIn && (
              analyzeLibFiles.filter(f => f.notes?.length).length > 0 ? (
                <div style={{ textAlign: "center", padding: "var(--s-4)" }}>
                  <p className="muted" style={{ margin: "0 0 var(--s-3)" }}>
                    Using: <strong>{analyzeLibFiles[0].name}</strong>
                  </p>
                  <button className="btn btn-primary" onClick={() => handleAnalyzeLibrary(analyzeLibFiles[0])}>
                    Analyze
                  </button>
                </div>
              ) : (
                <p className="muted" style={{ textAlign: "center", margin: "var(--s-4) 0" }}>
                  Transcribe an audio song first — then come back to analyze.
                </p>
              )
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
    </SharedAudioProvider>
  );
}
