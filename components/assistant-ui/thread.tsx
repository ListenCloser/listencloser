"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { ComposerPrimitive, useThread } from "@assistant-ui/react";

type ThreadProps = {
  onToolResult?: (toolName: string, result: any) => void;
};

export function Thread({ onToolResult }: ThreadProps) {
  const thread = useThread();
  const endRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [pendingFile, setPendingFile] = useState<{ file: File; base64: string } | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thread.messages]);

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";
    const bytes = await file.arrayBuffer();
    const base64 = btoa(
      Array.from(new Uint8Array(bytes))
        .map((b) => String.fromCharCode(b))
        .join("")
    );
    setPendingFile({ file, base64 });
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: "var(--s-3)" }}>
        {thread.messages.length === 0 && (
          <div style={{ textAlign: "center", color: "var(--muted)", fontSize: "var(--fs-sm)", padding: "var(--s-5)" }}>
            <p style={{ marginBottom: "var(--s-2)" }}>Ask me about your music!</p>
            <p style={{ fontSize: "var(--fs-xs)" }}>
              Try: "Transcribe this audio", "What key is this in?", "Clean up this recording"
            </p>
          </div>
        )}
        {thread.messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              marginBottom: "var(--s-3)",
              display: "flex",
              justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            <div
              style={{
                maxWidth: "80%",
                padding: "var(--s-2) var(--s-3)",
                borderRadius: "var(--r-md)",
                fontSize: "var(--fs-sm)",
                lineHeight: 1.5,
                whiteSpace: "pre-wrap",
                ...(msg.role === "user"
                  ? {
                      background: "var(--accent)",
                      color: "var(--bg)",
                      borderBottomRightRadius: "var(--s-1)",
                    }
                  : {
                      background: "var(--panel-2)",
                      color: "var(--text)",
                      border: "1px solid var(--border)",
                      borderBottomLeftRadius: "var(--s-1)",
                    }),
              }}
            >
              {msg.content.map((part, i) => {
                if (part.type === "text") return <span key={i}>{(part as any).text}</span>;
                if (part.type === "tool-call") {
                  return (
                    <div
                      key={i}
                      style={{
                        background: "var(--panel-3)",
                        border: "1px solid var(--border)",
                        borderRadius: "var(--r-sm)",
                        padding: "var(--s-2)",
                        marginTop: "var(--s-2)",
                        fontSize: "var(--fs-xs)",
                        color: "var(--muted)",
                      }}
                    >
                      <span style={{ color: "var(--accent)", fontWeight: "var(--fw-medium)" }}>
                        {(part as any).toolName}
                      </span>
                      <span style={{ marginLeft: "var(--s-2)" }}>Running...</span>
                    </div>
                  );
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

      <ComposerPrimitive.Root
        style={{
          display: "flex",
          gap: "var(--s-2)",
          padding: "var(--s-3)",
          borderTop: "1px solid var(--border)",
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*,.mid,.midi,.musicxml"
          onChange={handleFileSelect}
          style={{ display: "none" }}
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          style={{
            background: "var(--panel-2)",
            color: "var(--muted)",
            border: "1px solid var(--border)",
            borderRadius: "var(--r-md)",
            padding: "var(--s-2)",
            cursor: "pointer",
            fontSize: "var(--fs-sm)",
          }}
          title="Attach audio file"
        >
          📎
        </button>
        <ComposerPrimitive.Input
          style={{
            flex: 1,
            background: "var(--panel-2)",
            color: "var(--text)",
            border: "1px solid var(--border)",
            borderRadius: "var(--r-md)",
            padding: "var(--s-2) var(--s-3)",
            fontFamily: "inherit",
            fontSize: "var(--fs-sm)",
            outline: "none",
          }}
          placeholder="Ask about your music..."
        />
        <ComposerPrimitive.Send
          style={{
            background: "var(--accent)",
            color: "var(--bg)",
            border: "none",
            borderRadius: "var(--r-md)",
            padding: "var(--s-2) var(--s-4)",
            fontWeight: "var(--fw-medium)",
            fontSize: "var(--fs-sm)",
            cursor: "pointer",
          }}
        >
          Send
        </ComposerPrimitive.Send>
      </ComposerPrimitive.Root>
    </div>
  );
}
