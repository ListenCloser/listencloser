/**
 * AI Chat endpoint — streaming music assistant.
 *
 * Architecture: Uses Vercel AI SDK + OpenRouter for LLM access.
 * The model is configurable via CHAT_MODEL env var (default: Gemma 4 26B free).
 *
 * Tools are defined in lib/tools/index.ts and call the FastAPI backend
 * directly (not through the proxy) since this is a server-side route.
 *
 * Request: { messages: Array<{role, parts}> }
 * Response: SSE stream of UI message events
 */

import {
  streamText,
  toUIMessageStream,
  stepCountIs,
} from "ai";
import { createOpenAI } from "@ai-sdk/openai";
import { musicTools } from "@/lib/tools";

export const maxDuration = 60;

const openrouter = createOpenAI({
  baseURL: "https://openrouter.ai/api/v1",
  apiKey: process.env.OPENAI_API_KEY,
});

function convertMessages(messages: { role: "user" | "assistant" | "system"; parts?: { type: string; text?: string }[]; content?: string }[]) {
  return messages.map((msg) => {
    if (msg.parts) {
      const textParts = msg.parts
        .filter((p) => p.type === "text" && p.text)
        .map((p) => p.text!);
      // Include tool results as context so the LLM remembers what happened
      const toolParts = msg.parts
        .filter((p) => p.type.startsWith("tool-"))
        .map((p) => {
          const toolName = p.type.replace("tool-", "");
          const toolResult = (p as { output?: Record<string, unknown> }).output;
          if (toolResult) {
            return `[Tool result: ${toolName}] ${JSON.stringify(toolResult).slice(0, 500)}`;
          }
          return `[Tool: ${toolName}]`;
        });
      const allParts = [...textParts, ...toolParts];
      return { role: msg.role, content: allParts.join("\n") || "(tool result)" };
    }
    return { role: msg.role, content: msg.content ?? "" };
  });
}

export async function POST(req: Request) {
  try {
    const { messages } = await req.json();

    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      return new Response(JSON.stringify({ error: "No messages provided" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }

    const convertedMessages = convertMessages(messages);

    const result = streamText({
      model: openrouter.chat(process.env.CHAT_MODEL ?? "google/gemma-4-26b-a4b-it:free"),
      system: `You are a music assistant for Music AI Studio. You help users transcribe audio, analyze music theory, enhance audio quality, and convert between MIDI and MusicXML formats.

When a user asks you to do something, use the appropriate tool. If they mention a file but don't provide audio data, ask them to upload it using the attachment button. Always explain results in plain language after calling a tool.

Available operations:
- Transcribe audio to MIDI notes and sheet music
- Analyze music theory (key, tempo, chords, cadences, Roman numerals, modulations, voice leading)
- Clean and denoise audio recordings
- Convert between MIDI and MusicXML formats`,
      messages: convertedMessages,
      tools: musicTools,
      stopWhen: stepCountIs(5),
    });

    const uiStream = toUIMessageStream({ stream: result.fullStream });

    return new Response(uiStream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
      },
    });
  } catch (err) {
    console.error("Chat error:", err);
    return new Response(JSON.stringify({ error: err instanceof Error ? err.message : "Chat failed" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
