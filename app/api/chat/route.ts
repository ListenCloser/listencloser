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
      const allParts = [...textParts, ...toolParts];
      return { role: msg.role, content: allParts.join("\n") || "(tool result)" };
    }
    return { role: msg.role, content: msg.content ?? "" };
  });
}

export async function POST(req: Request) {
  try {
    const authHeader = req.headers.get("authorization");
    setRequestAuthHeader(authHeader ?? undefined);

    const { messages } = await req.json();

    if (!messages || !Array.isArray(messages) || messages.length === 0) {
      return new Response(JSON.stringify({ error: "No messages provided" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }

    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) {
      return new Response(JSON.stringify({ error: "OPENAI_API_KEY not set" }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      });
    }

    const convertedMessages = convertMessages(messages);

    const result = streamText({
      model: openrouter.chat(process.env.CHAT_MODEL ?? "google/gemma-4-26b-a4b-it:free"),
      system: `You are a music assistant for Music AI Studio. You are a fully self-contained workspace — the user can do everything through you.

Available tools:
- list_library: Browse the user's audio tracks and their processing status
- upload_audio: Save a new audio file to the user's library
- transcribe_audio: Convert audio to MIDI notes (returns notes, MIDI data)
- analyze_midi: Analyze MIDI for key, tempo, chords, cadences, modulations, voice leading
- enhance_audio: Clean and denoise audio recordings
- convert_format: Convert between MIDI and MusicXML formats

When the user asks about their music:
1. First use list_library to see what tracks they have
2. Then use the appropriate tool based on their request
3. Explain results in plain language

When the user uploads audio:
1. Use upload_audio to save it to their library
2. Then transcribe or analyze as requested

Always explain what each tool does and what the results mean.`,
      messages: convertedMessages,
      tools: musicTools,
      stopWhen: stepCountIs(5),
    });

    const encoder = new TextEncoder();
    const stream = new ReadableStream({
      async start(controller) {
        try {
          const reader = result.fullStream.getReader();
          let stepId = 0;

          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "start" })}\n\n`));

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = value as Record<string, unknown>;

            if (chunk.type === "text-start") {
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "text-start", id: String(stepId) })}\n\n`));
            } else if (chunk.type === "text-delta") {
              const delta = String(chunk.text ?? "");
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "text-delta", id: String(stepId), delta })}\n\n`));
            } else if (chunk.type === "text-end") {
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "text-end", id: String(stepId) })}\n\n`));
              stepId++;
            } else if (chunk.type === "tool-call") {
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "tool-call", id: String(stepId++), toolName: chunk.toolName, args: chunk.args })}\n\n`));
            } else if (chunk.type === "tool-result") {
              controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "tool-result", id: String(stepId), toolName: chunk.toolName, result: chunk.result })}\n\n`));
            }
          }

          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "finish" })}\n\n`));
          controller.enqueue(encoder.encode("data: [DONE]\n\n"));
        } catch (err) {
          console.error("Stream error:", err);
          controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "error", error: err instanceof Error ? err.message : "Stream failed" })}\n\n`));
        } finally {
          controller.close();
        }
      },
    });

    return new Response(stream, {
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
    });
  } catch (err) {
    console.error("Chat error:", err);
    return new Response(JSON.stringify({ error: err instanceof Error ? err.message : "Chat failed" }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });
  }
}
