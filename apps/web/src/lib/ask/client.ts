import { ApiError, apiFetch } from "@/lib/api";
import type { AskContext, AskResponse } from "./types";

export type AskRequest = {
  question: string;
  context: AskContext;
};

export type AskFailure = {
  message: string;
  requestId: string | null;
};

export class AskRequestError extends Error {
  readonly status: number;
  readonly requestId: string | null;

  constructor(message: string, status: number, requestId: string | null = null) {
    super(message);
    this.name = "AskRequestError";
    this.status = status;
    this.requestId = requestId;
  }
}

function boundedAskMessage(status: number, backendMessage: string): string {
  const normalized = backendMessage.toLowerCase();
  if (normalized.includes("not configured")) return "Ask is not configured for this workspace.";

  switch (status) {
    case 401:
      return "Sign in again to use Ask.";
    case 403:
      return "Ask is not available for this workspace.";
    case 429:
      return "Ask is busy right now. Try again shortly.";
    case 504:
      return "Ask took too long.";
    case 502:
    case 503:
      return "Ask is temporarily unavailable.";
    default:
      if (normalized.includes("timed out") || normalized.includes("timeout")) return "Ask took too long.";
      if (normalized.includes("provider unavailable") || normalized.includes("processing service unavailable")) {
        return "Ask is temporarily unavailable.";
      }
      return "Ask is unavailable right now.";
  }
}

export function describeAskFailure(cause: unknown): AskFailure {
  if (cause instanceof AskRequestError) {
    return { message: cause.message, requestId: cause.requestId };
  }

  const message = cause instanceof Error ? cause.message : "";
  const normalized = message.toLowerCase();
  if (normalized.includes("not configured")) {
    return { message: "Ask is not configured for this workspace.", requestId: null };
  }
  if (normalized.includes("timed out") || normalized.includes("timeout")) {
    return { message: "Ask took too long.", requestId: null };
  }
  if (normalized.includes("provider unavailable") || normalized.includes("processing service unavailable")) {
    return { message: "Ask is temporarily unavailable.", requestId: null };
  }
  return { message: "Ask is unavailable right now.", requestId: null };
}

/**
 * Thin frontend boundary for the POST /api/v1/ask endpoint. Keeps fetch()
 * out of UI components and gives the conversation panel one obvious place to
 * send a question. Raw backend/provider details stop at this boundary: the UI
 * only receives bounded failure copy plus status/request correlation.
 */
export async function askMusic({ question, context }: AskRequest): Promise<AskResponse> {
  try {
    return await apiFetch<AskResponse>("/api/v1/ask", {
      method: "POST",
      body: JSON.stringify({ question, context }),
    });
  } catch (cause) {
    if (cause instanceof ApiError) {
      throw new AskRequestError(
        boundedAskMessage(cause.status, cause.message),
        cause.status,
        cause.requestId,
      );
    }
    throw cause;
  }
}
