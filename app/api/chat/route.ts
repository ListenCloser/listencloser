/**
 * AI Chat endpoint — fully self-contained music workspace.
 *
 * The chat can do everything the regular UI can do:
 * - Browse library tracks
 * - Upload new audio files
 * - Transcribe audio to MIDI
 * - Analyze music theory
 * - Clean/denoise audio
 * - Convert MIDI ↔ MusicXML
 *
 * Tools are defined in lib/tools/index.ts and execute server-side
 * with access to the user's auth token.
 *
 * SSE format follows uiMessageChunkSchema from @ai-sdk/react:
 * - text-start, text-delta, text-end (for text)
 * - tool-input-start, tool-input-available (for tool calls)
 * - tool-output-available (for tool results)
 */

import { streamText, stepCountIs } from "ai";
import { createOpenAI } from "@ai-sdk/openai";
import { musicTools, setRequestAuthHeader } from "@/lib/tools";

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
      return { role: msg.role, content: [...textParts, ...toolParts].join("\n") || "(tool result)" };
    }
    return { role: msg.role, content: msg.content ?? "" };
  });
}

export async function POST(req: Request) {
  try {
    setRequestAuthHeader(req.headers.get("authorization") ?? undefined);

    const { messages } = await req.json();
    if (!messages?.length) {
      return new Response(JSON.stringify({ error: "No messages" }), { status: 400, headers: { "Content-Type": "application/json" } });
    }

    if (!process.env.OPENAI_API_KEY) {
      return new Response(JSON.stringify({ error: "OPENAI_API_KEY not set" }), { status: 500, headers: { "Content-Type": "application/json" } });
    }

    const result = streamText({
      model: openrouter.chat(process.env.CHAT_MODEL ?? "google/gemma-4-26b-a4b-it:free"),
      system: `You are a music assistant for Music AI Studio. You are a fully self-contained workspace.

Available tools:
- list_library: Browse the user's audio tracks
- upload_audio: Save audio to library
- transcribe_audio: Convert audio to MIDI
- analyze_midi: Analyze MIDI for key, tempo, chords, cadences, modulations, voice leading
- enhance_audio: Clean and denoise audio
- convert_format: Convert MIDI ↔ MusicXML

When the user asks about their music, first use list_library to see what they have, then use the appropriate tool. Explain results in plain language.`,
      messages: convertMessages(messages),
      tools: musicTools,
      stopWhen: stepCountIs(5),
    });

    // Format stream as SSE matching uiMessageChunkSchema
    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        try {
          const reader = result.fullStream.getReader();
          let stepId = 0;

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            const c = value as Record<string, unknown>;

            if (c.type === "text-start") {
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "text-start", id: String(stepId) })}\n\n`));
            } else if (c.type === "text-delta") {
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "text-delta", id: String(stepId), delta: String(c.text ?? "") })}\n\n`));
            } else if (c.type === "text-end") {
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "text-end", id: String(stepId) })}\n\n`));
              stepId++;
            } else if (c.type === "tool-call") {
              const tcId = `tc-${stepId++}`;
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "tool-input-start", toolCallId: tcId, toolName: c.toolName })}\n\n`));
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "tool-input-available", toolCallId: tcId, toolName: c.toolName, input: c.args })}\n\n`));
            } else if (c.type === "tool-result") {
              // Use the same ID that was sent with tool-input-start (stepId was already incremented)
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "tool-output-available", toolCallId: `tc-${stepId - 1}`, output: c.result })}\n\n`));
            }
          }

          controller.enqueue(encoder.encode("data: [DONE]\n\n"));
        } catch (err) {
          console.error("Stream error:", err);
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "error", errorText: err instanceof Error ? err.message : "Stream failed" })}\n\n`));
        } finally {
          controller.close();
        }
      },
    });

    return new Response(stream, { headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" } });
  } catch (err) {
    console.error("Chat error:", err);
    return new Response(JSON.stringify({ error: err instanceof Error ? err.message : "Chat failed" }), { status: 500, headers: { "Content-Type": "application/json" } });
  }
}
