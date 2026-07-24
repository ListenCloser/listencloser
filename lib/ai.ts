import type { TranscribeResult } from "./music";

type TextGenerationPipeline = {
  (text: string, options?: Record<string, unknown>): Promise<
    { generated_text: string }[]
  >;
  dispose: () => Promise<void>;
};

let generatorPromise: Promise<TextGenerationPipeline> | null = null;
let generatorInstance: TextGenerationPipeline | null = null;

const MODEL_ID = "Xenova/distilgpt2";
const MODEL_CACHE = "music-studio-ai-cache";

export function checkWebAssembly(): { supported: boolean; error?: string } {
  try {
    if (typeof WebAssembly === "undefined") {
      return { supported: false, error: "WebAssembly is not supported in this browser." };
    }
    // Test basic WASM instantiation
    const module = new WebAssembly.Module(new Uint8Array([0, 97, 115, 109, 1, 0, 0, 0]));
    if (!WebAssembly.Module.prototype) {
      return { supported: false, error: "WebAssembly module support is limited." };
    }
    void module;
    return { supported: true };
  } catch {
    return { supported: false, error: "WebAssembly is available but not functioning correctly." };
  }
}

async function loadGenerator(): Promise<TextGenerationPipeline> {
  if (generatorInstance) return generatorInstance;
  if (generatorPromise) return generatorPromise;

  generatorPromise = (async () => {
    const { pipeline, env } = await import("@huggingface/transformers");
    env.cacheDir = MODEL_CACHE;

    const pipe = (await pipeline("text-generation", MODEL_ID)) as unknown as TextGenerationPipeline;

    generatorInstance = pipe;
    return pipe;
  })();

  return generatorPromise;
}

export async function loadModel(): Promise<void> {
  const wasmCheck = checkWebAssembly();
  if (!wasmCheck.supported) {
    throw new Error(wasmCheck.error ?? "WebAssembly is not available.");
  }
  await loadGenerator();
}

export function isModelLoaded(): boolean {
  return generatorInstance !== null;
}

const SYSTEM_PROMPT = `You are a music theory tutor. Explain the following music analysis in plain language. Be concise and educational. Write 2-3 sentences max.`;

export async function explainMusic(
  question: string,
  analysis: NonNullable<TranscribeResult["analysis"]>,
): Promise<string> {
  const generator = await loadGenerator();

  const key = `${analysis.key.tonic} ${analysis.key.mode}`;
  const tempo = analysis.tempo ? `${analysis.tempo.bpm} BPM` : "unknown tempo";
  const chords = analysis.chords?.slice(0, 8).map((c) => {
    const q = c.quality === "M" ? "" : c.quality === "m" ? "m" : c.quality;
    return `${c.root}${q}`;
  }).join(", ") ?? "none detected";

  const prompt = `Music analysis: Key of ${key}, ${tempo}. Chords: ${chords}.

Question: ${question}

Answer:`;

  const output = await generator(prompt, {
    max_new_tokens: 150,
    temperature: 0.7,
    do_sample: true,
  });

  const text = output[0]?.generated_text ?? "";
  const answerStart = text.indexOf("Answer:");
  if (answerStart !== -1) {
    return text.slice(answerStart + "Answer:".length).trim();
  }
  return text.slice(-150).trim();
}

export async function disposeModel(): Promise<void> {
  if (generatorInstance) {
    await generatorInstance.dispose();
    generatorInstance = null;
    generatorPromise = null;
  }
}
