"use client";

import { useChat } from "@ai-sdk/react";
import { useRef, useEffect, useState, useCallback } from "react";
import { blobToBase64, type TranscribeResult } from "@/lib/music";

type MusicChatProps = {
  onTranscribed?: (result: TranscribeResult, name: string) => void;
  onAnalyzed?: (midiBase64?: string, name?: string) => void;
};

function ToolCallCard({ toolName }: { toolName: string }) {
  const labels: Record<string, string> = {
    transcribe_audio: "Transcribing audio…",
    analyze_midi: "Analyzing music theory…",
    enhance_audio: "Enhancing audio…",
    convert_format: "Converting format…",
  };
  return (
    <div className="chat-tool-card">
      <span className="chat-spinner" />
      {labels[toolName] || `Running ${toolName}…`}
    </div>
  );
}

function ToolResultCard({ toolName, result }: { toolName: string; result: Record<string, unknown> | null }) {
  if (!result) return null;
  if (toolName === "transcribe_audio") {
    return (
      <div className="chat-tool-result">
        <div className="chat-tool-success">✓ Transcribed {String(result.num_notes)} notes</div>
        <div className="chat-tool-hint">Open Transform tab to view piano roll, or Visualize tab for analysis.</div>
      </div>
    );
  }
  if (toolName === "analyze_midi") {
    const key = result.key && typeof result.key === "object" && "tonic" in result.key && "mode" in result.key
      ? `${(result.key as Record<string, string>).tonic} ${(result.key as Record<string, string>).mode}` : null;
    const tempo = result.tempo && typeof result.tempo === "object" && "bpm" in result.tempo
      ? `${Math.round((result.tempo as Record<string, number>).bpm)} BPM` : null;
    const ts = result.time_signature && typeof result.time_signature === "object"
      ? `${(result.time_signature as Record<string, number>).numerator}/${(result.time_signature as Record<string, number>).denominator}` : null;
    return (
      <div className="chat-tool-result">
        <div className="chat-tool-success">✓ Analysis complete</div>
        <div className="chat-tool-grid">
          {key && <div><span className="chat-muted">Key:</span> {key}</div>}
          {tempo && <div><span className="chat-muted">Tempo:</span> {tempo}</div>}
          {ts && <div><span className="chat-muted">Time:</span> {ts}</div>}
          {result.num_notes != null && <div><span className="chat-muted">Notes:</span> {String(result.num_notes)}</div>}
        </div>
      </div>
    );
  }
  if (toolName === "enhance_audio") {
    return (
      <div className="chat-tool-result">
        <div className="chat-tool-success">✓ Audio enhanced successfully</div>
      </div>
    );
  }
  if (toolName === "convert_format") {
    return (
      <div className="chat-tool-result">
        <div className="chat-tool-success">✓ {String(result.format || "converted")}</div>
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
  const processedToolCalls = useRef(new Set<string>());

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    for (const msg of messages) {
      if (msg.role !== "assistant") continue;
      for (const part of msg.parts ?? []) {
        if (!part.type.startsWith("tool-")) continue;
        const toolPart = part as { type: string; state?: string; output?: Record<string, unknown>; toolCallId?: string };
        if (toolPart.state !== "result" || !toolPart.output) continue;
        const callId = toolPart.toolCallId ?? `${msg.id}-${part.type}`;
        if (processedToolCalls.current.has(callId)) continue;
        processedToolCalls.current.add(callId);

        const toolName = toolPart.type.replace("tool-", "");
        const output = toolPart.output;

        if (toolName === "transcribe_audio" && onTranscribed) {
          const name = (output.file_name as string) || "audio";
          onTranscribed({
            notes: (output.notes as TranscribeResult["notes"]) ?? [],
            num_notes: (output.num_notes as number) ?? 0,
            midi_base64: output.midi_base64 as string,
            wav_url: output.wav_url as string,
          }, name);
        }
        if (toolName === "analyze_midi" && onAnalyzed) {
          onAnalyzed(output.midi_base64 as string, "analyzed");
        }
      }
    }
  }, [messages, onTranscribed, onAnalyzed]);

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    const base64 = await blobToBase64(file);
    setPendingFile({ file, base64 });
  }, []);

  const onSubmit = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() && !pendingFile) return;

    const text = pendingFile
      ? `[Audio file: ${pendingFile.file.name}, format: ${pendingFile.file.type || "wav"}]\n[Audio base64: ${pendingFile.base64}]\n\n${input || "Transcribe this audio"}`
      : input;

    sendMessage({ text });
    setInput("");
    setPendingFile(null);
  }, [input, pendingFile, sendMessage]);

  const isBusy = status === "submitted" || status === "streaming";

  return (
    <div className="card chat-container">
      <h3 className="card-title" style={{ marginBottom: 0 }}>
        <span className="glyph">◈</span> Chat
      </h3>
      <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "var(--s-1) 0 var(--s-3)" }}>
        Ask anything about your music — transcribe, analyze, convert, or clean audio.
      </p>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p style={{ marginBottom: "var(--s-2)" }}>Ask me about your music!</p>
            <p style={{ fontSize: "var(--fs-xs)" }}>
              Try: "Transcribe this audio", "What key is this in?", "Clean up this recording"
            </p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-msg ${msg.role === "user" ? "chat-msg-user" : "chat-msg-assistant"}`}>
            <div className={`chat-bubble ${msg.role === "user" ? "chat-bubble-user" : "chat-bubble-assistant"}`}>
              {msg.parts?.map((part, i) => {
                if (part.type === "text") return <span key={i} className="chat-text">{part.text}</span>;
                if (part.type.startsWith("tool-")) {
                  const toolName = part.type.replace("tool-", "");
                  const state = (part as { state?: string }).state;
                  if (state === "result") {
                    return <ToolResultCard key={i} toolName={toolName} result={(part as { output?: Record<string, unknown> }).output ?? null} />;
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
        <div className="chat-attachment">
          <span>📎 {pendingFile.file.name}</span>
          <button onClick={() => setPendingFile(null)} className="chat-attachment-remove">✕</button>
        </div>
      )}

      <form onSubmit={onSubmit} className="chat-form">
        <input ref={fileInputRef} type="file" accept="audio/*,.mid,.midi,.musicxml" onChange={handleFileSelect} style={{ display: "none" }} />
        <button type="button" onClick={() => fileInputRef.current?.click()} className="chat-attach-btn" title="Attach audio">📎</button>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your music..."
          className="chat-input"
          disabled={isBusy}
        />
        <button type="submit" disabled={isBusy || (!input.trim() && !pendingFile)} className="chat-send-btn">
          {isBusy ? "…" : "Send"}
        </button>
      </form>
    </div>
  );
}
