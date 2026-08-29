import type { AskContext } from "@/lib/ask/types";

const HARMONY_KINDS = new Set(["chord", "roman_numeral", "harmonic_function"]);
const KEY_KINDS = new Set(["key"]);
const TEMPO_KINDS = new Set(["tempo", "audio_tempo"]);
const METER_KINDS = new Set(["time_signature"]);
const RHYTHM_KINDS = new Set(["rhythm"]);

function isMelodyKind(kind: string): boolean {
  return kind === "melody" || kind.startsWith("melody_");
}

function hasAny(kinds: Set<string>, candidates: Set<string>): boolean {
  return [...kinds].some((kind) => candidates.has(kind));
}

function hasMelody(kinds: Set<string>): boolean {
  return [...kinds].some(isMelodyKind);
}

function pushRhythmPrompt(kinds: Set<string>, scope: "selection" | "recording", push: (question: string) => void): void {
  const hasTempo = hasAny(kinds, TEMPO_KINDS);
  const hasMeter = hasAny(kinds, METER_KINDS);
  const hasRhythm = hasAny(kinds, RHYTHM_KINDS);

  if (hasTempo && hasMeter) {
    push(scope === "selection"
      ? "What do the detected tempo and meter show in this selection?"
      : "What do the detected tempo and meter show in this recording?");
  } else if (hasTempo) {
    push(scope === "selection"
      ? "What tempo is detected in this selection?"
      : "What tempo is detected in this recording?");
  } else if (hasMeter) {
    push(scope === "selection"
      ? "What meter is detected in this selection?"
      : "What meter is detected in this recording?");
  } else if (hasRhythm) {
    push(scope === "selection"
      ? "What does the rhythm evidence show in this selection?"
      : "What does the rhythm evidence show across this recording?");
  }
}

/**
 * Offer only questions that the already-filtered Ask context can plausibly
 * ground. This is presentation policy over supplied evidence, not a promise
 * that the model can infer unavailable musical facts.
 */
export function deriveAskStarterPrompts(context: AskContext | null): string[] {
  if (!context) return [];

  const allKinds = new Set(context.visibleInsights.map((item) => item.insight.kind));
  const selectionKinds = new Set(
    context.visibleInsights
      .filter((item) => item.category === "selection")
      .map((item) => item.insight.kind),
  );
  const hasSelection = context.selection !== null;
  const prompts: string[] = [];
  const push = (question: string) => {
    if (!prompts.includes(question) && prompts.length < 3) prompts.push(question);
  };

  if (hasSelection) {
    if (hasAny(selectionKinds, HARMONY_KINDS) && hasAny(allKinds, KEY_KINDS)) {
      push("How do the detected chord changes in this selection relate to the detected key?");
    } else if (hasAny(selectionKinds, HARMONY_KINDS)) {
      push("What chord changes are detected in this selection?");
    }

    pushRhythmPrompt(selectionKinds, "selection", push);

    if (hasMelody(selectionKinds)) {
      push("What does the detected melody do in this selection?");
    }

    return prompts;
  }

  if (hasAny(allKinds, HARMONY_KINDS) && hasAny(allKinds, KEY_KINDS)) {
    push("How do the detected chords relate to the detected key?");
  } else if (hasAny(allKinds, HARMONY_KINDS)) {
    push("What chord changes are detected in this recording?");
  } else if (hasAny(allKinds, KEY_KINDS)) {
    push("What key is detected in this recording?");
  }

  pushRhythmPrompt(allKinds, "recording", push);

  if (hasMelody(allKinds)) {
    push("What does the detected melody evidence show across the recording?");
  }

  return prompts;
}
