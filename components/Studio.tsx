"use client";

import { useState, useCallback } from "react";
import { SharedAudioProvider } from "@/lib/audio-context";
import Library from "./library";
import TrackWorkspace from "./TrackWorkspace";
import ChatPanel from "./ChatPanel";
import {
  analyzeAudio,
  type TranscribeResult,
  type LibFile,
} from "@/lib/music";
import { supabase } from "@/lib/supabase";
import { clearTokenCache } from "@/lib/api";

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
      </div>
    </SharedAudioProvider>
  );
}
