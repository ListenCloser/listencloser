export type PublicRecording = {
  id: string;
  title: string;
  creator: string;
  style: string;
  description: string;
  fileTitle: string;
  licenseLabel: string;
  licenseUrl: string;
  sourcePageUrl: string;
  estimatedBytes: number;
  durationSeconds: number;
  tags: readonly string[];
};

export type ResolvedPublicRecording = {
  url: string;
  byteSize: number;
  mimeType: string;
};

export const PUBLIC_RECORDING_FETCH_MAX_BYTES = 25 * 1024 * 1024;
const COMMONS_API_URL = "https://commons.wikimedia.org/w/api.php";
const COMMONS_UPLOAD_HOST = "upload.wikimedia.org";

function commonsFilePage(fileTitle: string): string {
  return `https://commons.wikimedia.org/wiki/${encodeURIComponent(`File:${fileTitle}`)}`;
}

export const PUBLIC_RECORDINGS: readonly PublicRecording[] = [
  {
    id: "fur-elise",
    title: "Für Elise",
    creator: "Ludwig van Beethoven · performed by Gaodifan",
    style: "Classical · solo piano",
    description: "A familiar piano reference with a public-domain/CC0 performance.",
    fileTitle: "FurElise.ogg",
    licenseLabel: "CC0 / public domain",
    licenseUrl: "https://creativecommons.org/publicdomain/zero/1.0/",
    sourcePageUrl: commonsFilePage("FurElise.ogg"),
    estimatedBytes: 2_144_088,
    durationSeconds: 177,
    tags: ["classical", "piano", "beethoven", "bagatelle"],
  },
  {
    id: "maple-leaf-rag",
    title: "Maple Leaf Rag",
    creator: "Scott Joplin",
    style: "Ragtime · solo piano",
    description: "A compact ragtime excerpt with syncopated piano writing.",
    fileTitle: "Maple Leaf Rag.ogg",
    licenseLabel: "Public domain",
    licenseUrl: "https://creativecommons.org/publicdomain/mark/1.0/",
    sourcePageUrl: commonsFilePage("Maple Leaf Rag.ogg"),
    estimatedBytes: 263_000,
    durationSeconds: 53,
    tags: ["ragtime", "piano", "joplin", "syncopation"],
  },
  {
    id: "el-choclo",
    title: "El Choclo",
    creator: "Ángel Villoldo · Buenos Aires City Band",
    style: "Tango · band",
    description: "A 1907 tango recording with ensemble rhythm and melody.",
    fileTitle: "El Choclo-Villoldo.ogg",
    licenseLabel: "Public domain",
    licenseUrl: "https://creativecommons.org/publicdomain/mark/1.0/",
    sourcePageUrl: commonsFilePage("El Choclo-Villoldo.ogg"),
    estimatedBytes: 2_510_000,
    durationSeconds: 154,
    tags: ["tango", "argentina", "band", "latin"],
  },
  {
    id: "e-blues",
    title: "E Blues",
    creator: "Michael Huber",
    style: "Blues · solo piano",
    description: "A modern blues piano performance released under Creative Commons.",
    fileTitle: "E Blues by Michael Huber.ogg",
    licenseLabel: "CC BY-SA 3.0",
    licenseUrl: "https://creativecommons.org/licenses/by-sa/3.0/",
    sourcePageUrl: commonsFilePage("E Blues by Michael Huber.ogg"),
    estimatedBytes: 4_060_000,
    durationSeconds: 227,
    tags: ["blues", "piano", "improvisation", "huber"],
  },
  {
    id: "jazz-blues-c",
    title: "Jazz Blues in C",
    creator: "Serolillo",
    style: "Jazz / blues · short example",
    description: "A short C-blues example useful for harmony and groove exploration.",
    fileTitle: "Jazz Blues C.ogg",
    licenseLabel: "CC BY 2.5",
    licenseUrl: "https://creativecommons.org/licenses/by/2.5/",
    sourcePageUrl: commonsFilePage("Jazz Blues C.ogg"),
    estimatedBytes: 898_000,
    durationSeconds: 20,
    tags: ["jazz", "blues", "groove", "c blues"],
  },
  {
    id: "reggae-bultron",
    title: "Reggae Bultron",
    creator: "Muffinman",
    style: "Reggae en Español · beat example",
    description: "A compact drums-and-guitar reggae rhythm made in FL Studio.",
    fileTitle: "Reggae bultron.ogg",
    licenseLabel: "CC BY 3.0",
    licenseUrl: "https://creativecommons.org/licenses/by/3.0/",
    sourcePageUrl: commonsFilePage("Reggae bultron.ogg"),
    estimatedBytes: 281_000,
    durationSeconds: 13,
    tags: ["reggae", "panama", "rhythm", "guitar", "drums"],
  },
] as const;

export function filterPublicRecordings(query: string): readonly PublicRecording[] {
  const needle = query.trim().toLocaleLowerCase();
  if (!needle) return PUBLIC_RECORDINGS;
  return PUBLIC_RECORDINGS.filter((recording) =>
    [
      recording.title,
      recording.creator,
      recording.style,
      recording.description,
      ...recording.tags,
    ].some((value) => value.toLocaleLowerCase().includes(needle)),
  );
}

type CommonsImageInfo = {
  url?: unknown;
  size?: unknown;
  mime?: unknown;
};

type CommonsResponse = {
  query?: {
    pages?: Record<string, { imageinfo?: CommonsImageInfo[] }>;
  };
};

export function parseCommonsImageInfo(payload: unknown): ResolvedPublicRecording {
  const data = payload as CommonsResponse;
  const page = Object.values(data.query?.pages ?? {})[0];
  const info = page?.imageinfo?.[0];
  if (!info || typeof info.url !== "string") {
    throw new Error("Wikimedia Commons did not return a playable file.");
  }

  const sourceUrl = new URL(info.url);
  if (sourceUrl.protocol !== "https:" || sourceUrl.hostname !== COMMONS_UPLOAD_HOST) {
    throw new Error("Wikimedia Commons returned an unexpected file host.");
  }

  const byteSize = typeof info.size === "number" ? info.size : Number(info.size);
  if (!Number.isSafeInteger(byteSize) || byteSize <= 0) {
    throw new Error("Wikimedia Commons did not return a valid file size.");
  }
  if (byteSize > PUBLIC_RECORDING_FETCH_MAX_BYTES) {
    throw new Error("This public recording is too large to import.");
  }

  const mimeType = typeof info.mime === "string" && info.mime.startsWith("audio/")
    ? info.mime
    : "audio/ogg";
  return { url: sourceUrl.toString(), byteSize, mimeType };
}

export async function resolvePublicRecording(
  recording: PublicRecording,
  fetchImpl: typeof fetch = fetch,
): Promise<ResolvedPublicRecording> {
  const params = new URLSearchParams({
    action: "query",
    format: "json",
    origin: "*",
    prop: "imageinfo",
    iiprop: "url|size|mime",
    titles: `File:${recording.fileTitle}`,
  });
  const response = await fetchImpl(`${COMMONS_API_URL}?${params.toString()}`, {
    method: "GET",
    credentials: "omit",
    mode: "cors",
  });
  if (!response.ok) throw new Error("Could not reach Wikimedia Commons.");
  return parseCommonsImageInfo(await response.json());
}

export async function downloadPublicRecording(
  recording: PublicRecording,
  fetchImpl: typeof fetch = fetch,
): Promise<File> {
  const resolved = await resolvePublicRecording(recording, fetchImpl);
  const response = await fetchImpl(resolved.url, {
    method: "GET",
    credentials: "omit",
    mode: "cors",
  });
  if (!response.ok) throw new Error("Could not download this public recording.");

  const blob = await response.blob();
  if (blob.size <= 0 || blob.size > PUBLIC_RECORDING_FETCH_MAX_BYTES) {
    throw new Error("The downloaded public recording has an invalid size.");
  }
  if (blob.size !== resolved.byteSize) {
    throw new Error("The public recording changed while it was being imported. Try again.");
  }

  const extension = recording.fileTitle.split(".").pop()?.toLowerCase() ?? "ogg";
  return new File([blob], `${recording.title}.${extension}`, {
    type: resolved.mimeType || blob.type || "audio/ogg",
  });
}
