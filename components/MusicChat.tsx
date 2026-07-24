"use client";

import { AssistantRuntimeProvider, Suggestions } from "@assistant-ui/react";
import { useChatRuntime } from "@assistant-ui/react-ai-sdk";
import { Thread } from "@/components/assistant-ui/thread";

export default function MusicChat() {
  const runtime = useChatRuntime();

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
          <Thread />
        </div>
      </div>
    </AssistantRuntimeProvider>
  );
}
