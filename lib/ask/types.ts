import type { CategorizedInsight } from "@/lib/inspector/insights";
import type { MusicalSelection } from "@/lib/stores/workspace";
import type { RepresentationId } from "@/lib/representations";

/**
 * The workspace context a future music copilot can reason about.
 *
 * Derived — never a second source of truth — from the same existing
 * workspace/transport state that drives the rest of the app. No LLM call,
 * annotations, or user-facing UI depends on this in this PR; it is the typed
 * seam that later Ask features build on.
 */
export type AskContext = {
  workId: string;
  representationId: RepresentationId;
  currentTime: number;
  playbackSourceId: string | null;
  selection: MusicalSelection | null;
  /** Only insights visible in the current context, each tagged with its
      category (`selection` | `whole-work`) so whole-piece findings stay
      distinguishable from selection-scoped findings. `unrelated` insights are
      filtered out, matching what the workspace presents. */
  visibleInsights: CategorizedInsight[];
};

/**
 * A typed reference a copilot answer can point at. The frontend decides how
 * to resolve it; it is not an instruction to mutate state.
 */
export type AskReference =
  | { type: "time"; start: number; end?: number; domain: "performance" | "notation" }
  | { type: "measure"; start: number; end?: number }
  | { type: "notes"; ids: string[] }
  | { type: "insight"; id: string };

/**
 * A typed, user-triggerable action the model may *suggest*. The model never
 * executes these itself — the user explicitly triggers them.
 */
export type AskAction =
  | { type: "seek"; seconds: number; domain: "performance" | "notation" }
  | { type: "loop"; start: number; end: number; domain: "performance" | "notation" }
  | { type: "show_representation"; representationId: RepresentationId };

export type AskResponse = {
  answer: string;
  references: AskReference[];
  suggestedActions?: AskAction[];
};
