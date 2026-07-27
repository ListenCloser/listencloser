/**
 * Music Chat — primary interface for the entire music workflow.
 *
 * UX-019: End-to-end chat flow — upload, transcribe, analyze, visualize
 * UX-020: Chat as primary interface with embedded components
 *
 * Architecture: Tool results render as interactive components inline.
 * Users can do everything from chat without switching tabs.
 */

"use client";

import { useChat } from "@ai-sdk/react";
import { useRef, useEffect, useState, useCallback } from "react";
import { blobToBase64, synthAudio, type TranscribeResult } from "@/lib/music";
import PianoRoll from "@/components/PianoRoll";

type MusicChatProps = {
  onTranscribed?: (result: TranscribeResult, name: string) => void;
  onAnalyzed?: (midiBase64?: string, name?: string) => void;
  onNavigate?: (tab: string) => void;
};

function ToolCallCard({ toolName }: { toolName: string }) {
  const labels: Record<string, string> = {
    transcribe_audio: "🎵 Transcribing audio…",
    analyze_midi: "🎼 Analyzing music theory…",
    enhance_audio: "🔊 Enhancing audio…",
    convert_format: "🔄 Converting format…",
  };
  return (
    <div className="chat-tool-card">
      <span className="chat-spinner" />
      {labels[toolName] || `Running ${toolName}…`}
    </div>
  );
}

function TranscribeResultCard({
  result,
  onNavigate,
}: {
  result: Record<string, unknown>;
  onNavigate?: (tab: string) => void;
}) {
  const notes = (result.notes as TranscribeResult["notes"]) ?? [];
  const numNotes = (result.num_notes as number) ?? notes.length;
  const midiBase64 = result.midi_base64 as string | undefined;
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [loadingAudio, setLoadingAudio] = useState(false);

  const handleSynth = useCallback(async () => {
    if (!midiBase64 || loadingAudio) return;
    setLoadingAudio(true);
    try {
      const synth = await synthAudio(midiBase64);
      const bytes = Uint8Array.from(atob(synth.wav_base64), (c) => c.charCodeAt(0));
      const blob = new Blob([bytes], { type: "audio/wav" });
      setAudioUrl(URL.createObjectURL(blob));
    } catch {
      // synth failed
    } finally {
      setLoadingAudio(false);
    }
  }, [midiBase64, loadingAudio]);

  return (
    <div className="chat-tool-result">
      <div className="chat-tool-success">✓ Transcribed {numNotes} notes</div>

      {notes.length > 0 && (
        <div style={{ margin: "var(--s-2) 0" }}>
          <PianoRoll notes={notes} />
        </div>
      )}

      <div style={{ display: "flex", gap: "var(--s-2)", flexWrap: "wrap", marginTop: "var(--s-2)" }}>
        {midiBase64 && !audioUrl && (
          <button className="chat-nav-btn" onClick={handleSynth} disabled={loadingAudio}>
            {loadingAudio ? "Loading…" : "▶ Play MIDI"}
          </button>
        )}
        {audioUrl && (
          <audio controls src={audioUrl} style={{ height: 32, flex: 1 }} />
        )}
        {onNavigate && (
          <button className="chat-nav-btn" onClick={() => onNavigate("transcribe")}>
            Open in Transform
          </button>
        )}
        {onNavigate && notes.length > 0 && (
          <button className="chat-nav-btn" onClick={() => onNavigate("viz")}>
            Visualize
          </button>
        )}
      </div>
    </div>
  );
}

function AnalyzeResultCard({
  result,
  onNavigate,
}: {
  result: Record<string, unknown>;
  onNavigate?: (tab: string) => void;
}) {
  const key = result.key && typeof result.key === "object" && "tonic" in result.key
    ? `${(result.key as Record<string, string>).tonic} ${(result.key as Record<string, string>).mode}`
    : null;
  const tempo = result.tempo && typeof result.tempo === "object" && "bpm" in result.tempo
    ? `${Math.round((result.tempo as Record<string, number>).bpm)} BPM`
    : null;
  const chords = result.chords;
  const hasChords = Array.isArray(chords) && chords.length > 0;

  return (
    <div className="chat-tool-result">
      <div className="chat-tool-success">✓ Analysis complete</div>
      <div className="chat-tool-grid">
        {key && <div><span className="chat-muted">Key:</span> {key}</div>}
        {tempo && <div><span className="chat-muted">Tempo:</span> {tempo}</div>}
        {result.time_signature != null && typeof result.time_signature === "object" && (
          <div><span className="chat-muted">Time:</span> {(result.time_signature as Record<string, number>).numerator}/{(result.time_signature as Record<string, number>).denominator}</div>
        )}
        {result.num_notes != null && <div><span className="chat-muted">Notes:</span> {String(result.num_notes)}</div>}
      </div>
      {hasChords && (
        <div style={{ marginTop: "var(--s-2)", fontSize: "var(--fs-xs)", color: "var(--muted)" }}>
          {chords.length} chords detected
        </div>
      )}
      {onNavigate && (
        <div style={{ marginTop: "var(--s-2)" }}>
          <button className="chat-nav-btn" onClick={() => onNavigate("analyze")}>
            View Full Analysis
          </button>
        </div>
      )}
    </div>
  );
}

function EnhanceResultCard() {
  return (
    <div className="chat-tool-result">
      <div className="chat-tool-success">✓ Audio enhanced — noise removed, volume normalized</div>
    </div>
  );
}

function ConvertResultCard({ result }: { result: Record<string, unknown> }) {
  return (
    <div className="chat-tool-result">
      <div className="chat-tool-success">✓ Converted to {String(result.format || "target format")}</div>
    </div>
  );
}

const MESSAGES_KEY = "chat:messages";

function loadPersistedMessages() {
  try {
    const raw = sessionStorage.getItem(MESSAGES_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    // Only restore text messages, not tool calls (they can't be replayed)
    return parsed.filter((m: { role: string; parts?: { type: string }[] }) =>
      m.role === "user" || (m.role === "assistant" && m.parts?.some((p) => p.type === "text"))
    );
  } catch { return []; }
}

function persistMessages(msgs: { id: string; role: string; parts?: unknown[] }[]) {
  try { sessionStorage.setItem(MESSAGES_KEY, JSON.stringify(msgs.slice(-50))); } catch {}
}

export default function MusicChat({ onTranscribed, onAnalyzed, onNavigate }: MusicChatProps) {
  const persistedRef = useRef(loadPersistedMessages());
  const { messages, sendMessage, status, setMessages } = useChat();
  const endRef = useRef<HTMLDivElement>(null);
  const [input, setInput] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [pendingFile, setPendingFile] = useState<{ file: File; base64: string } | null>(null);
  const processedToolCalls = useRef(new Set<string>());

  // Restore persisted messages on mount
  useEffect(() => {
    if (persistedRef.current.length > 0 && messages.length === 0) {
      setMessages(persistedRef.current as any);
    }
  }, []);

  // Persist messages across tab switches
  useEffect(() => {
    if (messages.length > 0) persistMessages(messages);
  }, [messages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    for (const msg of messages) {
      if (msg.role !== "assistant") continue;
      for (const part of msg.parts ?? []) {
        // UseChat renders tool parts as type "tool-*" with state
        if (!part.type.startsWith("tool-")) continue;
        const toolPart = part as { type: string; state?: string; output?: Record<string, unknown>; toolCallId?: string };
        if (toolPart.state !== "result" || !toolPart.output) continue;
        const callId = toolPart.toolCallId ?? `${msg.id}-${part.type}`;
        if (processedToolCalls.current.has(callId)) continue;
        processedToolCalls.current.add(callId);
        const toolName = part.type.replace("tool-", "");
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
        Upload audio, ask questions, get transcriptions and analysis — all in one place.
      </p>

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p style={{ marginBottom: "var(--s-2)" }}>Ask me about your music!</p>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-2)", fontSize: "var(--fs-xs)" }}>
              <span>Try: "Transcribe this audio" (attach a file)</span>
              <span>Try: "What key is this in?"</span>
              <span>Try: "Clean up this recording"</span>
              <span>Try: "Convert this MIDI to sheet music"</span>
            </div>
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
                    const output = (part as { output?: Record<string, unknown> }).output ?? null;
                    if (toolName === "transcribe_audio" && output) {
                      return <TranscribeResultCard key={i} result={output} onNavigate={onNavigate} />;
                    }
                    if (toolName === "analyze_midi" && output) {
                      return <AnalyzeResultCard key={i} result={output} onNavigate={onNavigate} />;
                    }
                    if (toolName === "enhance_audio") {
                      return <EnhanceResultCard key={i} />;
                    }
                    if (toolName === "convert_format" && output) {
                      return <ConvertResultCard key={i} result={output} />;
                    }
                    return null;
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
