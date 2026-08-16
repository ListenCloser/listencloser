import { apiFetch } from "@/lib/api";
import type { AskContext, AskResponse } from "./types";

export type AskRequest = {
  question: string;
  context: AskContext;
};

/**
 * Thin frontend boundary for the POST /api/v1/ask endpoint. Keeps fetch()
 * out of UI components and gives the conversation panel one obvious place to
 * send a question. Errors from the backend are surfaced as a retryable inline
 * state by the UI.
 */
export async function askMusic({ question, context }: AskRequest): Promise<AskResponse> {
  return apiFetch<AskResponse>("/api/v1/ask", {
    method: "POST",
    body: JSON.stringify({ question, context }),
  });
}