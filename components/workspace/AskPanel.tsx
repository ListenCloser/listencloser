"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import { deriveAskContext } from "@/lib/ask/context";
import { askMusic } from "@/lib/ask/client";
import {
  actionLabel,
  describeAskContext,
  formatReference,
  resolveReference,
  validateAction,
  type ReferenceContext,
} from "@/lib/ask/render";
import { composeNoteSelection } from "@/lib/selection";
import type { PlaybackSource } from "@/lib/stores/transport";
import type { AskAction, AskMessage, AskReference, AskResponse } from "@/lib/ask/types";

const STARTER_PROMPTS = [
  "What is happening harmonically here?",
  "What changes in this section?",
  "Why does this passage sound different?",
  "Summarize this piece.",
];

function makeId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function referenceLabel(ref: AskReference, insights: { id: string; claim: string }[]): string {
  const resolveInsight = (id: string) => insights.find((i) => i.id === id)?.claim ?? null;
  return formatReference(ref, resolveInsight);
}

function ActionChip({ action, blocked, reason, onClick }: { action: AskAction; blocked: boolean; reason?: string; onClick: (action: AskAction) => void }) {
  return (
    <button
      type="button"
      className="ask-action-chip"
      disabled={blocked}
      title={reason}
      onClick={() => onClick(action)}
    >
      {actionLabel(action)}
    </button>
  );
}

export default function AskPanel() {
  const { workspace, appendAskMessage, setActiveRepresentation, setSelection } = useWorkspace();
  const { transport, seek, setLoop, toggleLoop } = useTransport();
  const { timeline } = useTimeline();
  const [draft, setDraft] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastAsked, setLastAsked] = useState<{ question: string; context: NonNullable<ReturnType<typeof deriveAskContext>>; workId: string } | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const askTokenRef = useRef(0);

  const activeWorkId = workspace.activeWorkId;
  const activeWorkIdRef = useRef(activeWorkId);
  activeWorkIdRef.current = activeWorkId;
  const activeSource = transport.activeSource;
  const scoreEntry = workspace.representations.find((entry) => entry.kind === "score");
  const pianoRollEntry = workspace.representations.find((entry) => entry.kind === "piano_roll");

  const referenceContext: ReferenceContext = {
    activeSource,
    insights: workspace.insights,
    bpm: timeline.bpm,
    measureStarts: scoreEntry?.measureStarts ?? [],
    scoreDuration: scoreEntry?.audioUrl ? transport.duration : null,
    notes: pianoRollEntry?.notes ?? [],
  };

  const runAsk = useCallback(async (question: string, context: NonNullable<ReturnType<typeof deriveAskContext>>, workId: string) => {
    const token = ++askTokenRef.current;
    setPending(true);
    setError(null);
    try {
      const response = await askMusic({ question, context });
      if (token !== askTokenRef.current || workId !== activeWorkIdRef.current) return;
      const assistantMessage: AskMessage = { id: makeId(), role: "assistant", response };
      appendAskMessage(assistantMessage);
      setLastAsked(null);
    } catch (err) {
      if (token !== askTokenRef.current || workId !== activeWorkIdRef.current) return;
      const msg = err instanceof Error ? err.message : "Ask is not available right now.";
      setError(msg.includes("not configured") ? "Ask is not configured. Contact your administrator." : "Ask is not available right now. Please try again.");
    } finally {
      if (token === askTokenRef.current) {
        setPending(false);
        inputRef.current?.focus();
      }
    }
  }, [appendAskMessage]);

  useEffect(() => {
    askTokenRef.current += 1;
    setLastAsked(null);
    setError(null);
    setPending(false);
  }, [activeWorkId]);

  const handleAsk = useCallback(async (question: string) => {
    const trimmed = question.trim();
    if (!trimmed || pending || !activeWorkId) return;
    const context = deriveAskContext(
      activeWorkId,
      workspace.activeRepresentation,
      transport.position,
      activeSource,
      workspace.selection,
      workspace.insights,
      timeline.bpm,
    );
    if (!context) {
      setError("Ask needs an open work to answer questions.");
      return;
    }
    const userMessage: AskMessage = { id: makeId(), role: "user", text: trimmed };
    appendAskMessage(userMessage);
    setDraft("");
    setLastAsked({ question: trimmed, context, workId: activeWorkId });
    void runAsk(trimmed, context, activeWorkId);
  }, [activeWorkId, activeSource, appendAskMessage, pending, runAsk, timeline.bpm, transport.position, workspace.activeRepresentation, workspace.insights, workspace.selection]);

  const retry = useCallback(() => {
    if (lastAsked?.question && lastAsked.context && lastAsked.workId === activeWorkIdRef.current) {
      void runAsk(lastAsked.question, lastAsked.context, lastAsked.workId);
    }
  }, [lastAsked, runAsk]);

  const handleReference = useCallback((ref: AskReference) => {
    const resolution = resolveReference(ref, referenceContext);
    switch (resolution.kind) {
      case "seek":
        seek(resolution.seconds);
        break;
      case "open-representation":
        setActiveRepresentation(resolution.representationId);
        break;
      case "select-notes": {
        const composed = composeNoteSelection(pianoRollEntry?.notes ?? [], resolution.ids);
        setActiveRepresentation("piano_roll");
        if (composed) setSelection(composed);
        break;
      }
      case "blocked":
        break;
    }
  }, [referenceContext, seek, setActiveRepresentation, setSelection]);

  const handleAction = useCallback((action: AskAction) => {
    const { allowed } = validateAction(action, activeSource);
    if (!allowed) return;
    switch (action.type) {
      case "seek":
        seek(action.seconds);
        break;
      case "loop":
        setLoop(action.start, action.end);
        if (!transport.loopEnabled) toggleLoop();
        break;
      case "show_representation":
        setActiveRepresentation(action.representationId);
        break;
    }
  }, [activeSource, seek, setActiveRepresentation, setLoop, toggleLoop, transport.loopEnabled]);

  const scope = describeAskContext(workspace.selection);
  const conversation = workspace.askConversation;
  const starterPrompts = conversation.length === 0;

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleAsk(draft);
    }
  };

  return (
    <div className="ask-panel">
      <div className="ask-context">
        <span className="ask-context-label">Context</span>
        <span className="ask-context-value">{scope}</span>
      </div>

      <div className="ask-conversation" aria-live="polite">
        {conversation.length === 0 && starterPrompts && (
          <div className="ask-empty">
            <p>Ask questions about this piece. Answers reference evidence in the workspace.</p>
            <div className="ask-prompts">
              {STARTER_PROMPTS.map((prompt) => (
                <button
                  type="button"
                  className="ask-prompt"
                  key={prompt}
                  onClick={() => void handleAsk(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        {conversation.map((message) => (
          <AskMessageView
            key={message.id}
            message={message}
            insights={workspace.insights}
            referenceContext={referenceContext}
            activeSource={activeSource}
            onReference={handleReference}
            onAction={handleAction}
          />
        ))}

        {pending && (
          <div className="ask-turn ask-thinking" role="status">
            <span className="spinner" aria-hidden="true" />
            <span>Thinking…</span>
          </div>
        )}
      </div>

      {error && (
        <div className="ask-error" role="alert">
          <span>{error}</span>
          <button type="button" onClick={retry}>
            Try again
          </button>
        </div>
      )}

      <form
        className="ask-composer"
        onSubmit={(event) => {
          event.preventDefault();
          void handleAsk(draft);
        }}
      >
        <textarea
          ref={inputRef}
          className="ask-input"
          placeholder="Ask about this piece…"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          disabled={!activeWorkId}
        />
        <button type="submit" className="ask-send" disabled={pending || !draft.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

function AskMessageView({
  message,
  insights,
  referenceContext,
  activeSource,
  onReference,
  onAction,
}: {
  message: AskMessage;
  insights: { id: string; claim: string }[];
  referenceContext: ReferenceContext;
  activeSource: PlaybackSource | null;
  onReference: (ref: AskReference) => void;
  onAction: (action: AskAction) => void;
}) {
  if (message.role === "user") {
    return (
      <div className="ask-turn ask-turn-user">
        <span className="ask-turn-label">You</span>
        <p>{message.text}</p>
      </div>
    );
  }

  const response: AskResponse = message.response;
  return (
    <div className="ask-turn ask-turn-assistant">
      <span className="ask-turn-label">Ask</span>
      <p>{response.answer}</p>
      {response.references.length > 0 && (
        <div className="ask-references">
          <span className="ask-ref-label">Evidence</span>
          <div className="ask-ref-chips">
            {response.references.map((ref, index) => {
              const resolution = resolveReference(ref, referenceContext);
              const blocked = resolution.kind === "blocked";
              return (
                <button
                  type="button"
                  className="ask-ref-chip"
                  key={`${ref.type}-${index}`}
                  disabled={blocked}
                  title={blocked ? resolution.reason : undefined}
                  onClick={() => onReference(ref)}
                >
                  {referenceLabel(ref, insights)}
                </button>
              );
            })}
          </div>
        </div>
      )}
      {response.suggestedActions && response.suggestedActions.length > 0 && (
        <div className="ask-actions">
          {response.suggestedActions.map((action, index) => {
            const { allowed, reason } = validateAction(action, activeSource);
            return (
              <ActionChip
                key={`${action.type}-${index}`}
                action={action}
                blocked={!allowed}
                reason={reason}
                onClick={onAction}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}