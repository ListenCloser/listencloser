import {
  streamText,
  createUIMessageStreamResponse,
  toUIMessageStream,
  convertToModelMessages,
  stepCountIs,
} from "ai";
import { google } from "@ai-sdk/google";
import { musicTools } from "@/lib/tools";

export const maxDuration = 60;

export async function POST(req: Request) {
  const { messages } = await req.json();

  const result = streamText({
    model: google("gemini-2.0-flash"),
    system: `You are a music assistant for Music AI Studio. You help users transcribe audio, analyze music theory, enhance audio quality, and convert between MIDI and MusicXML formats.

When a user asks you to do something, use the appropriate tool. If they mention a file but don't provide audio data, ask them to upload or describe it. Always explain results in plain language after calling a tool.

Available operations:
- Transcribe audio to MIDI notes and sheet music
- Analyze music theory (key, tempo, chords, cadences, Roman numerals, modulations, voice leading)
- Clean and denoise audio recordings
- Convert between MIDI and MusicXML formats`,
    messages: await convertToModelMessages(messages),
    tools: musicTools,
    stopWhen: stepCountIs(5),
  });

  return createUIMessageStreamResponse({
    stream: toUIMessageStream({ stream: result.stream }),
  });
}
