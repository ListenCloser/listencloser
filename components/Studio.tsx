/**
 * Main application shell — renders the UI layout.
 *
 * WHY: This component is now a pure rendering layer. All state management
 * lives in hooks/useStudioState.ts. This separation means:
 * - Studio.tsx is easy to understand (just layout + routing)
 * - State is testable independently of the UI
 * - Adding a new tab only requires adding to TABS and rendering
 *
 * The Analyze tab UI is inlined here (not in components/analyze/)
 * because it needs cross-tab state that would require 3+ levels of
 * prop drilling to reach a separate component.
 */

"use client";

import { useStudioState, TABS } from "@/hooks/useStudioState";
import Library from "./library";
import Transform from "./transcribe";
import Analysis from "./analyze";
import Viz from "./viz";
import MusicChat from "./MusicChat";
import { SharedAudioProvider } from "@/lib/audio-context";

export default function Studio({
  initialTab = "transcribe",
  initialTrack,
  signedIn = false,
}: {
  initialTab?: string;
  initialTrack?: string;
  signedIn?: boolean;
}) {
  const state = useStudioState({ initialTab, initialTrack, signedIn });

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
              className={`nav-item${state.tab === t.id ? " active" : ""}`}
              onClick={() => state.goToTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="account">
          {signedIn ? (
            <button className="btn btn-ghost" onClick={state.signOut}>
              Sign out
            </button>
          ) : (
            <button className="btn btn-ghost" id="signInBtn" onClick={state.signIn}>
              Sign in
            </button>
          )}
        </div>
      </header>

      <div className="workbench">
        {state.tab === "library" && (
          <Library
            signedIn={signedIn}
            onSignIn={state.signIn}
            onTranscribe={state.handleLibraryTranscribe}
            onAnalyze={state.handleLibraryAnalyze}
            onVisualize={state.handleLibraryVisualize}
            onTrackDeleted={state.handleTrackDeleted}
            transcriptions={state.transcriptions}
            refreshKey={state.refreshKey}
            isTranscribing={state.isTranscribing}
            isAnalyzing={state.isAnalyzing}
          />
        )}

        <div style={{ display: state.tab === "transcribe" ? "block" : "none" }}>
          <Transform
            signedIn={signedIn}
            onTranscribed={state.onTranscribed}
            onGoToAnalyze={() => state.goToTab("analyze")}
            onAnalyze={state.handleAnalyze}
            libraryFileToLoad={state.pendingLibFile}
            onClearLibraryFile={() => state.setPendingLibFile(null)}
            onTranscriptionSaved={state.refreshTranscriptions}
            onBusyChange={state.setIsTranscribing}
            onNewTranscription={() => {
              state.setAnalysis(null);
              state.setAnalysisError("");
            }}
            analysis={state.analysis}
            initialResult={state.lastResult}
            initialAudioName={state.audioName}
          />
        </div>

        {state.tab === "viz" && (
          <Viz
            initialTrackId={state.vizTrackId}
            selectedId={state.vizSelectedId}
            onTrackSelected={(id) => { state.setVizTrackId(null); state.setVizSelectedId(id); }}
            onStopRef={state.vizStopRef}
          />
        )}

        {state.tab === "chat" && (
          <MusicChat
            onTranscribed={(result, name) => {
              state.onTranscribed(result, name);
              state.goToTab("transcribe");
            }}
            onAnalyzed={(midi, name) => {
              if (midi) state.handleAnalyze(midi, name);
              state.goToTab("analyze");
            }}
            onNavigate={(tab) => state.goToTab(tab as any)}
          />
        )}

        <div style={{ display: state.tab === "analyze" ? "block" : "none" }}>
          <div className="card">
            <h3 className="card-title"><span className="glyph">◈</span> Analyze</h3>

            {!state.analysis && !state.analyzeStatus && signedIn && !state.analyzeLoading && state.analyzeLibFiles.filter(f => f.notes?.length).length === 0 && (
              <>
                <div className="section-label">Select a transcribed track</div>
                <p className="muted" style={{ textAlign: "center", margin: "var(--s-4) 0" }}>
                  No transcribed tracks in your library — transcribe one first.
                </p>
              </>
            )}

            {!state.analysis && !state.analyzeStatus && signedIn && state.analyzeLoading && (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-2)" }}>
                {[1, 2, 3].map((i) => (
                  <div key={i} style={{ padding: "var(--s-3)", background: "var(--panel-2)", borderRadius: "var(--r-md)", opacity: 0.5 }}>
                    <div className="skel line" style={{ width: "60%" }} />
                  </div>
                ))}
              </div>
            )}

            {!state.analysis && !state.analyzeStatus && signedIn && !state.analyzeLoading && state.analyzeLibFiles.filter(f => f.notes?.length).length > 0 && (
              <>
                <div className="section-label">Select a transcribed track</div>
                <div style={{ display: "flex", gap: "var(--s-2)", marginBottom: "var(--s-4)" }}>
                  <select
                    className="sel"
                    value=""
                    onChange={(e) => {
                      const file = state.analyzeLibFiles.find(f => f.id === e.target.value);
                      if (file) state.handleAnalyzeLibrary(file);
                    }}
                    style={{ flex: 1 }}
                  >
                    <option value="">-- Pick a track --</option>
                    {state.analyzeLibFiles.filter(f => f.notes?.length).map((f) => (
                      <option key={f.id} value={f.id}>{f.name}{f.analysis ? " ✓" : ""}</option>
                    ))}
                  </select>
                </div>
              </>
            )}

            {!state.analysis && !state.analyzeStatus && !signedIn && state.analyzeLibFiles.filter(f => f.notes?.length).length > 0 && (
              <div style={{ textAlign: "center", padding: "var(--s-4)" }}>
                <p className="muted" style={{ margin: "0 0 var(--s-3)" }}>
                  Using: <strong>{state.analyzeLibFiles.find(f => f.notes?.length)?.name}</strong>
                </p>
                <button className="btn btn-primary" onClick={() => {
                  const first = state.analyzeLibFiles.find(f => f.notes?.length);
                  if (first) state.handleAnalyzeLibrary(first);
                }}>
                  Analyze
                </button>
              </div>
            )}

            {!state.analysis && !state.analyzeStatus && !signedIn && state.analyzeLibFiles.filter(f => f.notes?.length).length === 0 && (
              <p className="muted" style={{ textAlign: "center", margin: "var(--s-4) 0" }}>
                Transcribe an audio song first — then come back to analyze.
              </p>
            )}

            {state.analyzeStatus && (
              <div style={{ marginBottom: "var(--s-3)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "var(--s-2)", marginBottom: "var(--s-2)" }}>
                  <span className="status" style={{ fontSize: "var(--fs-sm)" }}>{state.analyzeStatus}</span>
                </div>
                <div style={{ height: 6, background: "var(--panel-3)", borderRadius: "var(--r-full)" }}>
                  <div className="pulse" style={{ height: "100%", width: "50%", background: "var(--accent)", borderRadius: "var(--r-full)" }} />
                </div>
                <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "var(--s-1) 0 0" }}>
                  Analyzing key, tempo, chords, Roman numerals, cadences…
                </p>
              </div>
            )}

            {state.analysisError && !state.analysis && !state.analyzeStatus && (
              <div className="alert-danger" style={{ marginBottom: "var(--s-3)" }}>
                <p className="status" style={{ color: "var(--danger)", margin: 0 }}>⚠️ {state.analysisError}</p>
              </div>
            )}

            {state.analysis && (
              <>
                <Analysis
                  analysis={state.analysis}
                  notes={state.lastResult?.notes ?? []}
                  audioName={state.audioName}
                  numNotes={state.lastResult?.num_notes ?? 0}
                />
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
