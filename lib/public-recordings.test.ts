import { describe, expect, it } from "vitest";

import {
  filterPublicRecordings,
  parseCommonsImageInfo,
  PUBLIC_RECORDING_FETCH_MAX_BYTES,
  PUBLIC_RECORDINGS,
} from "./public-recordings";

const CURRENT_MAIN_UPLOAD_LIMIT = 4 * 1024 * 1024;
const SUPPORTED_AUDIO_EXTENSIONS = new Set(["wav", "mp3", "m4a", "flac", "ogg", "aac"]);

describe("public recording catalog", () => {
  it("uses unique IDs and current supported audio formats", () => {
    expect(new Set(PUBLIC_RECORDINGS.map((recording) => recording.id)).size).toBe(PUBLIC_RECORDINGS.length);
    for (const recording of PUBLIC_RECORDINGS) {
      const extension = recording.fileTitle.split(".").pop()?.toLowerCase();
      expect(extension && SUPPORTED_AUDIO_EXTENSIONS.has(extension)).toBe(true);
    }
  });

  it("stays independently compatible with the pre-25 MiB upload boundary", () => {
    for (const recording of PUBLIC_RECORDINGS) {
      expect(recording.estimatedBytes).toBeLessThanOrEqual(CURRENT_MAIN_UPLOAD_LIMIT);
    }
  });

  it("is intentionally not a classical-only catalog", () => {
    const styles = PUBLIC_RECORDINGS.map((recording) => recording.style.toLowerCase());
    expect(styles.some((style) => style.includes("classical"))).toBe(true);
    expect(styles.some((style) => style.includes("ragtime"))).toBe(true);
    expect(styles.some((style) => style.includes("tango"))).toBe(true);
    expect(styles.some((style) => style.includes("blues"))).toBe(true);
    expect(styles.some((style) => style.includes("reggae"))).toBe(true);
  });

  it("filters across titles, creators, styles, and tags", () => {
    expect(filterPublicRecordings("tango").map((recording) => recording.id)).toContain("el-choclo");
    expect(filterPublicRecordings("Huber").map((recording) => recording.id)).toEqual(["e-blues"]);
    expect(filterPublicRecordings("drums").map((recording) => recording.id)).toEqual(["reggae-bultron"]);
  });
});

describe("parseCommonsImageInfo", () => {
  const validPayload = {
    query: {
      pages: {
        "123": {
          imageinfo: [
            {
              url: "https://upload.wikimedia.org/wikipedia/commons/a/a1/example.ogg",
              size: 1234,
              mime: "audio/ogg",
            },
          ],
        },
      },
    },
  };

  it("accepts an expected Wikimedia upload response", () => {
    expect(parseCommonsImageInfo(validPayload)).toEqual({
      url: "https://upload.wikimedia.org/wikipedia/commons/a/a1/example.ogg",
      byteSize: 1234,
      mimeType: "audio/ogg",
    });
  });

  it("rejects missing file metadata", () => {
    expect(() => parseCommonsImageInfo({ query: { pages: { "-1": {} } } })).toThrow(
      "Wikimedia Commons did not return a playable file.",
    );
  });

  it("rejects an unexpected media host", () => {
    const payload = structuredClone(validPayload);
    payload.query.pages["123"].imageinfo[0].url = "https://example.com/example.ogg";
    expect(() => parseCommonsImageInfo(payload)).toThrow(
      "Wikimedia Commons returned an unexpected file host.",
    );
  });

  it("rejects missing, invalid, and oversized byte counts", () => {
    const missing = structuredClone(validPayload);
    missing.query.pages["123"].imageinfo[0].size = Number.NaN;
    expect(() => parseCommonsImageInfo(missing)).toThrow(
      "Wikimedia Commons did not return a valid file size.",
    );

    const oversized = structuredClone(validPayload);
    oversized.query.pages["123"].imageinfo[0].size = PUBLIC_RECORDING_FETCH_MAX_BYTES + 1;
    expect(() => parseCommonsImageInfo(oversized)).toThrow(
      "This public recording is too large to import.",
    );
  });
});
