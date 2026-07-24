import {
  streamText,
  createUIMessageStreamResponse,
  toUIMessageStream,
  stepCountIs,
} from "ai";
import { openai } from "@ai-sdk/openai";
import { musicTools } from "@/lib/tools";

export const maxDuration = 60;

export async function POST(req: Request) {
  const { messages } = await req.json();

  if (!messages || !Array.isArray(messages) || messages.length === 0) {
    return new Response(JSON.stringify({ error: "No messages provided" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const result = streamText({
    model: openai.chat("google/gemma-4-26b-a4b-it:free", {
      baseURL: "https://openrouter.ai/api/v1",
    }),
    system: `You are a music assistant for Music AI Studio. You help users transcribe audio, analyze music theory, enhance audio quality, and convert between MIDI and MusicXML formats.

When a user asks you to do something, use the appropriate tool. If they mention a file but don't provide audio data, ask them to upload it using the attachment button. Always explain results in plain language after calling a tool.

Available operations:
- Transcribe audio to MIDI notes and sheet music
- Analyze music theory (key, tempo, chords, cadences, Roman numerals, modulations, voice leading)
- Clean and denoise audio recordings
- Convert between MIDI and MusicXML formats`,
    messages,
    tools: musicTools,
    stopWhen: stepCountIs(5),
  });

  return createUIMessageStreamResponse({
    stream: toUIMessageStream({ stream: result.stream }),
  });
}
