"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { useChat } from "@ai-sdk/react";
import { blobToBase64, synthAudio, type TranscribeResult } from "@/lib/music";
import PianoRoll from "@/components/PianoRoll";

type ChatPanelProps = {
  isOpen: boolean;
  onToggle: () => void;
  selectedTrack: { name: string; notes?: any[]; midi_base64?: string; analysis?: any } | null;
  onTranscribed?: (result: TranscribeResult, name: string) => void;
  onAnalyzed?: (midiBase64?: string, name?: string) => void;
};

function ToolCallCard({ toolName }: { toolName: string }) {
  const labels: Record<string, string> = {
    list_library: "Browsing library...",
    upload_audio: "Uploading audio...",
    transcribe_audio: "Transcribing audio...",
    analyze_midi: "Analyzing music theory...",
    enhance_audio: "Enhancing audio...",
    convert_format: "Converting format...",
  };
  return (
    <div className="chat-tool-card">
      <span className="chat-spinner" />
      {labels[toolName] || `Running ${toolName}...`}
    </div>
  );
}

function TranscribeResultCard({ result }: { result: Record<string, unknown> }) {
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
    } catch {} finally { setLoadingAudio(false); }
  }, [midiBase64, loadingAudio]);

  return (
    <div className="chat-tool-result">
      <div className="chat-tool-success">Transcribed {numNotes} notes</div>
      {notes.length > 0 && <div style={{ margin: "var(--s-2) 0" }}><PianoRoll notes={notes} /></div>}
      <div style={{ display: "flex", gap: "var(--s-2)", flexWrap: "wrap", marginTop: "var(--s-2)" }}>
        {midiBase64 && !audioUrl && (
          <button className="chat-nav-btn" onClick={handleSynth} disabled={loadingAudio}>
            {loadingAudio ? "Loading..." : "Play MIDI"}
          </button>
        )}
        {audioUrl && <audio controls src={audioUrl} style={{ height: 32, flex: 1 }} />}
      </div>
    </div>
  );
}

function AnalyzeResultCard({ result }: { result: Record<string, unknown> }) {
  const key = result.key && typeof result.key === "object" && "tonic" in result.key
    ? `${(result.key as Record<string, string>).tonic} ${(result.key as Record<string, string>).mode}` : null;
  const tempo = result.tempo && typeof result.tempo === "object" && "bpm" in result.tempo
    ? `${Math.round((result.tempo as Record<string, number>).bpm)} BPM` : null;
  return (
    <div className="chat-tool-result">
      <div className="chat-tool-success">Analysis complete</div>
      <div className="chat-tool-grid">
        {key && <div><span className="chat-muted">Key:</span> {key}</div>}
        {tempo && <div><span className="chat-muted">Tempo:</span> {tempo}</div>}
      </div>
    </div>
  );
}

const MESSAGES_KEY = "chat:messages";
function loadPersistedMessages() {
  try { const raw = sessionStorage.getItem(MESSAGES_KEY); return raw ? JSON.parse(raw) : []; } catch { return []; }
}
function persistMessages(msgs: unknown[]) {
  try { sessionStorage.setItem(MESSAGES_KEY, JSON.stringify(msgs.slice(-50))); } catch {}
}

export default function ChatPanel({
  isOpen,
  onToggle,
  selectedTrack,
  onTranscribed,
  onAnalyzed,
}: ChatPanelProps) {
  const persistedRef = useRef(loadPersistedMessages());
  const { messages, sendMessage, status, setMessages } = useChat();
  const endRef = useRef<HTMLDivElement>(null);
  const [input, setInput] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [pendingFile, setPendingFile] = useState<{ file: File; base64: string } | null>(null);
  const processedToolCalls = useRef(new Set<string>());

  useEffect(() => {
    if (persistedRef.current.length > 0 && messages.length === 0) {
      setMessages(persistedRef.current as any);
    }
  }, []);

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
        if (!part.type.startsWith("tool-")) continue;
        const toolPart = part as { type: string; state?: string; output?: Record<string, unknown>; toolCallId?: string };
        if (toolPart.state !== "result" || !toolPart.output) continue;
        const callId = toolPart.toolCallId ?? `${msg.id}-${part.type}`;
        if (processedToolCalls.current.has(callId)) continue;
        processedToolCalls.current.add(callId);
        const toolName = toolPart.type.replace("tool-", "");
        const output = toolPart.output;
        if (toolName === "transcribe_audio" && onTranscribed) {
          onTranscribed({
            notes: (output.notes as TranscribeResult["notes"]) ?? [],
            num_notes: (output.num_notes as number) ?? 0,
            midi_base64: output.midi_base64 as string,
          }, (output.file_name as string) || "audio");
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

  const quickActions = selectedTrack ? [
    { label: "Analyze", msg: `Analyze "${selectedTrack.name}" — key, tempo, chords, cadences` },
    { label: "Explain harmony", msg: `Explain the chord progression in "${selectedTrack.name}"` },
    { label: "Generate MIDI", msg: `Generate a MIDI transcription of "${selectedTrack.name}"` },
  ] : [
    { label: "Show library", msg: "Show me my library" },
    { label: "Upload audio", msg: "I want to upload and transcribe audio" },
  ];

  const isBusy = status === "submitted" || status === "streaming";

  if (!isOpen) {
    return (
      <button className="chat-fab" onClick={onToggle} title="Open AI Chat">
        AI
      </button>
    );
  }

  return (
    <div className="shell-chat">
      <div className="chat-header">
        <div className="chat-header-title">
          <span className="glyph" style={{ width: 20, height: 20, fontSize: 10 }}>AI</span>
          Assistant
        </div>
        <button className="icon-btn" onClick={onToggle}>×</button>
      </div>

      {quickActions.length > 0 && (
        <div className="chat-quick-actions">
          {quickActions.map((a) => (
            <button
              key={a.label}
              className="chat-quick-btn"
              onClick={() => sendMessage({ text: a.msg })}
              disabled={isBusy}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}

      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p style={{ marginBottom: "var(--s-2)" }}>Ask about your music</p>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--s-2)", fontSize: "var(--fs-xs)" }}>
              <span>"What key is this piece in?"</span>
              <span>"Explain this chord progression"</span>
              <span>"Clean up this recording"</span>
              <span>"Show me my library"</span>
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
                    if (toolName === "transcribe_audio" && output) return <TranscribeResultCard key={i} result={output} />;
                    if (toolName === "analyze_midi" && output) return <AnalyzeResultCard key={i} result={output} />;
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
          <span>{pendingFile.file.name}</span>
          <button onClick={() => setPendingFile(null)} className="chat-attachment-remove">x</button>
        </div>
      )}

      <form onSubmit={onSubmit} className="chat-form">
        <input ref={fileInputRef} type="file" accept="audio/*,.mid,.midi,.musicxml" onChange={handleFileSelect} style={{ display: "none" }} />
        <button type="button" onClick={() => fileInputRef.current?.click()} className="chat-attach" title="Attach audio">+</button>
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask about your music..." className="chat-input" disabled={isBusy} />
        <button type="submit" disabled={isBusy || (!input.trim() && !pendingFile)} className="chat-send">
          {isBusy ? "..." : "Send"}
        </button>
      </form>
    </div>
  );
}
