"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import { useChatRuntime } from "@assistant-ui/react-ai-sdk";
import { Thread } from "@/components/assistant-ui/thread";
import type { TranscribeResult, LibFile } from "@/lib/music";

type MusicChatProps = {
  onTranscribed?: (result: TranscribeResult, name: string) => void;
  onAnalyzed?: (midiBase64?: string, name?: string) => void;
  onGoToTab?: (tab: string) => void;
};

export default function MusicChat({ onTranscribed, onAnalyzed, onGoToTab }: MusicChatProps) {
  const runtime = useChatRuntime();

  const handleToolResult = (toolName: string, result: any) => {
    if (toolName === "transcribe_audio" && result?.midi_base64 && onTranscribed) {
      const resultObj: TranscribeResult = {
        notes: result.notes ?? [],
        num_notes: result.num_notes ?? 0,
        midi_base64: result.midi_base64,
      };
      onTranscribed(resultObj, result.name || "chat-upload");
    }
    if (toolName === "analyze_midi" && result && onAnalyzed) {
      onAnalyzed(result.midi_base64, result.name);
    }
  };

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="card" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
        <h3 className="card-title" style={{ marginBottom: 0 }}>
          <span className="glyph">◈</span> Chat
        </h3>
        <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "var(--s-1) 0 var(--s-3)" }}>
          Ask anything about your music — transcribe, analyze, convert, or clean audio.
        </p>
        <div style={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
          <Thread onToolResult={handleToolResult} />
        </div>
      </div>
    </AssistantRuntimeProvider>
  );
}
