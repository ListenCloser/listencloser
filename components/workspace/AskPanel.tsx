"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Tooltip from "@/components/ui/Tooltip";
import { useWorkspace } from "@/lib/stores/workspace";
import { useTransport } from "@/lib/stores/transport";
import { useTimeline } from "@/lib/stores/timeline";
import { deriveAskContext } from "@/lib/ask/context";
import { askMusic } from "@/lib/ask/client";
import { deriveAskStarterPrompts } from "@/lib/ask/prompts";
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

function makeId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function referenceLabel(ref: AskReference, insights: { id: string; claim: string }[]): string {
  const resolveInsight = (id: string) => insights.find((item) => item.id === id)?.claim ?? null;
  return formatReference(ref, resolveInsight);
}

function ActionChip({ action, blocked, reason, onClick }: { action: AskAction; blocked: boolean; reason?: string; onClick: (action: AskAction) => void }) {
  const chip = (
    <button
      type="button"
      className="ask-action-chip"
      aria-disabled={blocked || undefined}
      onClick={() => {
        if (!blocked) onClick(action);
      }}
    >
      {actionLabel(action)}
    </button>
  );

  return blocked && reason ? <Tooltip content={reason}>{chip}</Tooltip> : chip;
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
    scoreDuration: scoreEntry?.measureStarts?.length ? transport.duration : null,
    notes: pianoRollEntry?.notes ?? [],
  };

  const runAsk = useCallback(async (question: string, context: NonNullable<ReturnType<typeof deriveAskContext>>, workId: string) => {
    const token = ++askTokenRef.current;
    setPending(true);
    setError(null);
    try {
      const response = await askMusic({ question, context });
      if (token !== askTokenRef.current || workId !== activeWorkIdRef.current) return;
      appendAskMessage({ id: makeId(), role: "assistant", response });
      setLastAsked(null);
    } catch (cause) {
      if (token !== askTokenRef.current || workId !== activeWorkIdRef.current) return;
      const message = cause instanceof Error ? cause.message : "Ask is not available right now.";
      setError(message.includes("not configured") ? "Ask is not configured for this workspace." : "Ask is unavailable right now.");
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
      setError("Open a piece before asking about it.");
      return;
    }
    appendAskMessage({ id: makeId(), role: "user", text: trimmed });
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
  const showScope = Boolean(workspace.selection && scope);
  const starterContext = deriveAskContext(
    activeWorkId,
    workspace.activeRepresentation,
    transport.position,
    activeSource,
    workspace.selection,
    workspace.insights,
    timeline.bpm,
  );
  const starterPrompts = deriveAskStarterPrompts(starterContext);
  const conversation = workspace.askConversation;

  const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleAsk(draft);
    }
  };

  return (
    <div className="ask-panel ask-panel-v4">
      {showScope && (
        <div className="ask-context" aria-label={`Question context: ${scope}`}>
          <span>{scope}</span>
        </div>
      )}

      <div className="ask-conversation" aria-live="polite">
        {conversation.length === 0 && (
          <div className="ask-empty">
            <strong>Ask about the current music</strong>
            <p>Questions are grounded in analysis currently available for this recording and selection.</p>
            {starterPrompts.length > 0 && (
              <div className="ask-prompts">
                {starterPrompts.map((prompt) => (
                  <button type="button" className="ask-prompt" key={prompt} onClick={() => void handleAsk(prompt)}>
                    {prompt}
                  </button>
                ))}
              </div>
            )}
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
            <span className="ask-thinking-dot" />
            <span>Thinking</span>
          </div>
        )}
      </div>

      {error && (
        <div className="ask-error" role="alert">
          <span>{error}</span>
          {lastAsked && <button type="button" onClick={retry}>Retry</button>}
        </div>
      )}

      <form className="ask-composer" onSubmit={(event) => { event.preventDefault(); void handleAsk(draft); }}>
        <textarea
          ref={inputRef}
          className="ask-input"
          placeholder={showScope ? "Ask a question about this selection…" : "Ask a question about this recording…"}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          rows={2}
          disabled={!activeWorkId}
          aria-label="Ask about the music"
        />
        <button type="submit" className="ask-send" disabled={pending || !draft.trim()} aria-label="Send question">
          <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
            <path d="M3 8h9M8.5 3.5 13 8l-4.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
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
    return <div className="ask-turn ask-turn-user"><p>{message.text}</p></div>;
  }

  const response: AskResponse = message.response;
  return (
    <div className="ask-turn ask-turn-assistant">
      <p>{response.answer}</p>
      {response.references.length > 0 && (
        <div className="ask-references">
          <span className="ask-ref-label">Evidence</span>
          <div className="ask-ref-chips">
            {response.references.map((ref, index) => {
              const resolution = resolveReference(ref, referenceContext);
              const blocked = resolution.kind === "blocked";
              const chip = (
                <button
                  type="button"
                  className="ask-ref-chip"
                  key={`${ref.type}-${index}`}
                  aria-disabled={blocked || undefined}
                  onClick={() => {
                    if (!blocked) onReference(ref);
                  }}
                >
                  {referenceLabel(ref, insights)}
                </button>
              );

              return blocked
                ? <Tooltip key={`${ref.type}-${index}`} content={resolution.reason}>{chip}</Tooltip>
                : chip;
            })}
          </div>
        </div>
      )}
      {response.suggestedActions && response.suggestedActions.length > 0 && (
        <div className="ask-actions">
          {response.suggestedActions.map((action, index) => {
            const { allowed, reason } = validateAction(action, activeSource);
            return <ActionChip key={`${action.type}-${index}`} action={action} blocked={!allowed} reason={reason} onClick={onAction} />;
          })}
        </div>
      )}
    </div>
  );
}
