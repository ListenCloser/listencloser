"use client";

import { useChat } from "@ai-sdk/react";
import { useRef, useEffect, useState, useCallback } from "react";
import type { TranscribeResult } from "@/lib/music";

type MusicChatProps = {
  onTranscribed?: (result: TranscribeResult, name: string) => void;
  onAnalyzed?: (midiBase64?: string, name?: string) => void;
};

function ToolCallCard({ toolName }: { toolName: string }) {
  const labels: Record<string, string> = {
    transcribe_audio: "🎵 Transcribing audio…",
    analyze_midi: "🎼 Analyzing music theory…",
    enhance_audio: "🔊 Enhancing audio…",
    convert_format: "🔄 Converting format…",
  };
  return (
    <div style={{
      background: "var(--panel-3)", border: "1px solid var(--border)",
      borderRadius: "var(--r-sm)", padding: "var(--s-2) var(--s-3)",
      margin: "var(--s-2) 0", fontSize: "var(--fs-xs)", color: "var(--muted)",
      display: "flex", alignItems: "center", gap: "var(--s-2)",
    }}>
      <span style={{ display: "inline-block", width: 12, height: 12, border: "2px solid var(--border)", borderTopColor: "var(--accent)", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
      {labels[toolName] || `Running ${toolName}…`}
    </div>
  );
}

function ToolResultCard({ toolName, result }: { toolName: string; result: any }) {
  if (!result) return null;
  if (toolName === "transcribe_audio") {
    return (
      <div style={{ margin: "var(--s-2) 0", padding: "var(--s-2) var(--s-3)", background: "var(--panel-3)", borderRadius: "var(--r-sm)", border: "1px solid var(--border)", fontSize: "var(--fs-xs)" }}>
        <div style={{ color: "var(--accent)", fontWeight: "var(--fw-medium)" }}>✓ {result.notes_summary || `Transcribed ${result.num_notes} notes`}</div>
        <div style={{ color: "var(--muted)", marginTop: 2 }}>Open Transform or Visualize tab to view.</div>
      </div>
    );
  }
  if (toolName === "analyze_midi") {
    const key = result.key?.tonic && result.key?.mode ? `${result.key.tonic} ${result.key.mode}` : null;
    const bpm = result.tempo?.bpm ? Math.round(result.tempo.bpm) : null;
    return (
      <div style={{ margin: "var(--s-2) 0", padding: "var(--s-2) var(--s-3)", background: "var(--panel-3)", borderRadius: "var(--r-sm)", border: "1px solid var(--border)", fontSize: "var(--fs-xs)" }}>
        <div style={{ color: "var(--accent)", fontWeight: "var(--fw-medium)" }}>✓ Analysis complete</div>
        {key && <div style={{ color: "var(--muted)" }}>Key: {key}</div>}
        {bpm && <div style={{ color: "var(--muted)" }}>Tempo: {bpm} BPM</div>}
      </div>
    );
  }
  if (toolName === "enhance_audio") {
    return (
      <div style={{ margin: "var(--s-2) 0", padding: "var(--s-2) var(--s-3)", background: "var(--panel-3)", borderRadius: "var(--r-sm)", border: "1px solid var(--border)", fontSize: "var(--fs-xs)" }}>
        <div style={{ color: "var(--accent)", fontWeight: "var(--fw-medium)" }}>✓ Audio enhanced</div>
      </div>
    );
  }
  if (toolName === "convert_format") {
    return (
      <div style={{ margin: "var(--s-2) 0", padding: "var(--s-2) var(--s-3)", background: "var(--panel-3)", borderRadius: "var(--r-sm)", border: "1px solid var(--border)", fontSize: "var(--fs-xs)" }}>
        <div style={{ color: "var(--accent)", fontWeight: "var(--fw-medium)" }}>✓ {result.message || `Converted to ${result.format}`}</div>
      </div>
    );
  }
  return null;
}

export default function MusicChat({ onTranscribed, onAnalyzed }: MusicChatProps) {
  const { messages, sendMessage, status } = useChat();
  const endRef = useRef<HTMLDivElement>(null);
  const [input, setInput] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [pendingFile, setPendingFile] = useState<{ file: File; base64: string } | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    const bytes = await file.arrayBuffer();
    const base64 = btoa(Array.from(new Uint8Array(bytes)).map((b) => String.fromCharCode(b)).join(""));
    setPendingFile({ file, base64 });
  }, []);

  const onSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    const text = pendingFile ? `[Attached: ${pendingFile.file.name}]\n${input}` : input;
    if (!text.trim() && !pendingFile) return;
    sendMessage({ text });
    setInput("");
    setPendingFile(null);
  }, [input, pendingFile, sendMessage]);

  return (
    <div className="card" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <h3 className="card-title" style={{ marginBottom: 0 }}>
        <span className="glyph">◈</span> Chat
      </h3>
      <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "var(--s-1) 0 var(--s-3)" }}>
        Ask anything about your music — transcribe, analyze, convert, or clean audio.
      </p>

      <div style={{ flex: 1, overflowY: "auto", padding: "var(--s-3)" }}>
        {messages.length === 0 && (
          <div style={{ textAlign: "center", color: "var(--muted)", fontSize: "var(--fs-sm)", padding: "var(--s-5)" }}>
            <p style={{ marginBottom: "var(--s-2)" }}>Ask me about your music!</p>
            <p style={{ fontSize: "var(--fs-xs)" }}>
              Try: "Transcribe this audio", "What key is this in?", "Clean up this recording"
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} style={{ marginBottom: "var(--s-3)", display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
            <div style={{
              maxWidth: "80%", padding: "var(--s-2) var(--s-3)", borderRadius: "var(--r-md)",
              fontSize: "var(--fs-sm)", lineHeight: 1.5,
              ...(msg.role === "user"
                ? { background: "var(--accent)", color: "var(--bg)", borderBottomRightRadius: "var(--s-1)" }
                : { background: "var(--panel-2)", color: "var(--text)", border: "1px solid var(--border)", borderBottomLeftRadius: "var(--s-1)" }),
            }}>
              {msg.parts?.map((part, i) => {
                if (part.type === "text") return <span key={i} style={{ whiteSpace: "pre-wrap" }}>{part.text}</span>;
                if (part.type.startsWith("tool-")) {
                  const toolName = part.type.replace("tool-", "");
                  const state = (part as any).state;
                  if (state === "result") {
                    return <ToolResultCard key={i} toolName={toolName} result={(part as any).output} />;
                  }
                  return <ToolCallCard key={i} toolName={toolName} />;
                }
                return null;
              })}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>

      {pendingFile && (
        <div style={{ padding: "var(--s-2) var(--s-3)", background: "var(--panel-3)", borderTop: "1px solid var(--border)", fontSize: "var(--fs-xs)", color: "var(--muted)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span>📎 {pendingFile.file.name}</span>
          <button onClick={() => setPendingFile(null)} style={{ background: "none", border: "none", color: "var(--muted)", cursor: "pointer" }}>✕</button>
        </div>
      )}

      <form onSubmit={onSubmit} style={{ display: "flex", gap: "var(--s-2)", padding: "var(--s-3)", borderTop: "1px solid var(--border)" }}>
        <input ref={fileInputRef} type="file" accept="audio/*,.mid,.midi,.musicxml" onChange={handleFileSelect} style={{ display: "none" }} />
        <button type="button" onClick={() => fileInputRef.current?.click()} style={{ background: "var(--panel-2)", color: "var(--muted)", border: "1px solid var(--border)", borderRadius: "var(--r-md)", padding: "var(--s-2)", cursor: "pointer", fontSize: "var(--fs-sm)" }} title="Attach audio">📎</button>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about your music..." style={{ flex: 1, background: "var(--panel-2)", color: "var(--text)", border: "1px solid var(--border)", borderRadius: "var(--r-md)", padding: "var(--s-2) var(--s-3)", fontFamily: "inherit", fontSize: "var(--fs-sm)", outline: "none" }} />
        <button type="submit" disabled={status === "submitted" || (!input.trim() && !pendingFile)} style={{ background: "var(--accent)", color: "var(--bg)", border: "none", borderRadius: "var(--r-md)", padding: "var(--s-2) var(--s-4)", fontWeight: "var(--fw-medium)", fontSize: "var(--fs-sm)", cursor: "pointer", opacity: (status === "submitted" || (!input.trim() && !pendingFile)) ? 0.4 : 1 }}>
          {status === "submitted" ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}
