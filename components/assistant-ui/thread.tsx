"use client";

import { useRef, useEffect } from "react";
import { ComposerPrimitive, useThread } from "@assistant-ui/react";

export function Thread() {
  const thread = useThread();
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [thread.messages]);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: "var(--s-3)" }}>
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
                if (part.type === "text") return <span key={i}>{part.text}</span>;
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
                        {part.toolName}
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
      <ComposerPrimitive.Root
        style={{
          display: "flex",
          gap: "var(--s-2)",
          padding: "var(--s-3)",
          borderTop: "1px solid var(--border)",
        }}
      >
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
