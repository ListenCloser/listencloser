import { apiFetch } from "@/lib/api";
import type { AskContext, AskResponse } from "./types";

export type AskRequest = {
  question: string;
  context: AskContext;
};

/**
 * Thin frontend boundary for the (not-yet-existing) Ask endpoint. Keeps
 * fetch() out of UI components and gives the conversation panel one obvious
 * place to send a question. The backend may return an error until the Ask
 * endpoint exists; the UI surfaces that as a retryable inline state.
 */
export async function askMusic({ question, context }: AskRequest): Promise<AskResponse> {
  return apiFetch<AskResponse>("/api/v1/ask", {
    method: "POST",
    body: JSON.stringify({ question, context }),
  });
}