"use client";

import { useState, useRef, useEffect } from "react";
import { loadModel, isModelLoaded, checkWebAssembly, explainMusic } from "@/lib/ai";
import type { TranscribeResult } from "@/lib/music";

type Message = { role: "user" | "assistant"; text: string };

const QUICK_PROMPTS = [
  "Explain the harmony of this piece",
  "Why does this key sound the way it does?",
  "What are the important cadences?",
  "Describe the overall form",
];

type Props = {
  analysis: NonNullable<TranscribeResult["analysis"]>;
};

export default function ExplainPanel({ analysis }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [modelStatus, setModelStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  async function ensureModel() {
    if (isModelLoaded()) {
      setModelStatus("ready");
      return true;
    }

    const wasmCheck = checkWebAssembly();
    if (!wasmCheck.supported) {
      setModelStatus("error");
      setErrorMsg(
        wasmCheck.error
          ? `${wasmCheck.error} The AI chat requires WebAssembly to run the language model.`
          : "Your browser does not support WebAssembly, which is required for AI chat. Please try a modern browser like Chrome, Firefox, Safari, or Edge."
      );
      return false;
    }

    setModelStatus("loading");
    setErrorMsg("");
    try {
      await loadModel();
      setModelStatus("ready");
      return true;
    } catch (err) {
      setModelStatus("error");
      const msg = err instanceof Error ? err.message : "Unknown error";
      if (msg.includes("WebAssembly") || msg.includes("wasm")) {
        setErrorMsg(`Failed to initialize the AI model: ${msg}. Please ensure your browser supports WebAssembly and try again.`);
      } else if (msg.includes("fetch") || msg.includes("network") || msg.includes("load")) {
        setErrorMsg(`Failed to download the AI model. Please check your internet connection and try again. The model is approximately 300MB.`);
      } else {
        setErrorMsg(`Failed to load AI model: ${msg}. Please try refreshing the page.`);
      }
      return false;
    }
  }

  async function ask(question: string) {
    if (!question.trim() || loading) return;

    const userMsg: Message = { role: "user", text: question.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    const ready = await ensureModel();
    if (!ready) {
      setLoading(false);
      return;
    }

    try {
      const answer = await explainMusic(question, analysis);
      setMessages((prev) => [...prev, { role: "assistant", text: answer }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: "Something went wrong generating the explanation. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    ask(input);
  }

  return (
    <div style={{ marginTop: "var(--s-4)" }}>
      <div className="section-label">Ask about this piece</div>

      {modelStatus === "loading" && (
        <div className="card" style={{ marginBottom: "var(--s-3)", fontSize: "var(--fs-sm)", color: "var(--muted)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "var(--s-2)" }}>
            <div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
            Loading AI model in your browser (one-time ~300MB download)…
          </div>
        </div>
      )}

      {modelStatus === "error" && (
        <div className="card" style={{ marginBottom: "var(--s-3)", fontSize: "var(--fs-sm)", borderColor: "var(--danger-soft)", background: "rgba(239,68,68,0.06)" }}>
          <p style={{ color: "var(--danger)", margin: 0, fontWeight: 500 }}>AI chat unavailable</p>
          <p style={{ color: "var(--muted)", margin: "var(--s-1) 0 0", fontSize: "var(--fs-xs)" }}>
            {errorMsg}
          </p>
          <button
            className="btn btn-ghost"
            style={{ marginTop: "var(--s-2)", fontSize: "var(--fs-xs)" }}
            onClick={() => { setModelStatus("idle"); setErrorMsg(""); }}
          >
            Try again
          </button>
        </div>
      )}

      {messages.length === 0 && modelStatus !== "loading" && modelStatus !== "error" && (
        <div style={{ display: "flex", gap: "var(--s-2)", flexWrap: "wrap", marginBottom: "var(--s-3)" }}>
          {QUICK_PROMPTS.map((q) => (
            <button key={q} className="chip" onClick={() => ask(q)}>
              {q}
            </button>
          ))}
        </div>
      )}

      {messages.length > 0 && (
        <div
          ref={listRef}
          style={{
            maxHeight: 320,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: "var(--s-2)",
            marginBottom: "var(--s-3)",
          }}
        >
          {messages.map((msg, i) => (
            <div
              key={i}
              className="card"
              style={{
                padding: "var(--s-3)",
                fontSize: "var(--fs-sm)",
                lineHeight: "var(--line-height-base)",
                borderColor: msg.role === "user" ? "var(--accent-soft)" : "var(--border)",
                background: msg.role === "user" ? "var(--accent-soft)" : "var(--panel)",
              }}
            >
              {msg.text}
            </div>
          ))}
          {loading && (
            <div className="card" style={{ padding: "var(--s-3)", fontSize: "var(--fs-sm)", color: "var(--muted)" }}>
              Thinking…
            </div>
          )}
        </div>
      )}

      {modelStatus !== "error" && (
        <form onSubmit={handleSubmit} style={{ display: "flex", gap: "var(--s-2)" }}>
          <input
            className="input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about harmony, cadences, form…"
            disabled={loading}
            style={{ flex: 1 }}
          />
          <button className="btn" type="submit" disabled={loading || !input.trim()}>
            Ask
          </button>
        </form>
      )}
    </div>
  );
}
