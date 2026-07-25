import { describe, it, expect } from "vitest";
import { blobToBase64, formatTime, audioFmtFromBlob, audioFmtFromName } from "@/lib/format";

describe("blobToBase64", () => {
  it("converts a small blob to base64", async () => {
    const blob = new Blob(["hello"], { type: "text/plain" });
    const result = await blobToBase64(blob);
    expect(result).toBe(btoa("hello"));
  });

  it("converts an empty blob", async () => {
    const blob = new Blob([], { type: "text/plain" });
    const result = await blobToBase64(blob);
    expect(result).toBe("");
  });

  it("handles binary data", async () => {
    const data = new Uint8Array([0, 1, 2, 255]);
    const blob = new Blob([data]);
    const result = await blobToBase64(blob);
    const decoded = atob(result);
    expect(decoded.charCodeAt(0)).toBe(0);
    expect(decoded.charCodeAt(3)).toBe(255);
  });
});

describe("formatTime", () => {
  it("formats zero seconds", () => {
    expect(formatTime(0)).toBe("0:00");
  });

  it("formats seconds under a minute", () => {
    expect(formatTime(45)).toBe("0:45");
  });

  it("formats exactly one minute", () => {
    expect(formatTime(60)).toBe("1:00");
  });

  it("formats minutes and seconds", () => {
    expect(formatTime(125)).toBe("2:05");
  });

  it("pads single-digit seconds", () => {
    expect(formatTime(61)).toBe("1:01");
  });
});

describe("audioFmtFromBlob", () => {
  it("detects WAV", () => {
    expect(audioFmtFromBlob(new Blob([], { type: "audio/wav" }))).toBe("wav");
  });

  it("detects MP3", () => {
    expect(audioFmtFromBlob(new Blob([], { type: "audio/mpeg" }))).toBe("mp3");
  });

  it("detects OGG", () => {
    expect(audioFmtFromBlob(new Blob([], { type: "audio/ogg" }))).toBe("ogg");
  });

  it("detects FLAC", () => {
    expect(audioFmtFromBlob(new Blob([], { type: "audio/flac" }))).toBe("flac");
  });

  it("detects M4A as MP4", () => {
    expect(audioFmtFromBlob(new Blob([], { type: "audio/mp4" }))).toBe("mp4");
  });

  it("defaults to WAV for unknown types", () => {
    expect(audioFmtFromBlob(new Blob([], { type: "application/octet-stream" }))).toBe("wav");
  });
});

describe("audioFmtFromName", () => {
  it("detects .wav", () => {
    expect(audioFmtFromName("song.wav")).toBe("wav");
  });

  it("detects .mp3", () => {
    expect(audioFmtFromName("song.mp3")).toBe("mp3");
  });

  it("detects .ogg", () => {
    expect(audioFmtFromName("song.ogg")).toBe("ogg");
  });

  it("detects .m4a as mp4", () => {
    expect(audioFmtFromName("song.m4a")).toBe("mp4");
  });

  it("detects .webm", () => {
    expect(audioFmtFromName("song.webm")).toBe("webm");
  });

  it("defaults to WAV for unknown extensions", () => {
    expect(audioFmtFromName("song.xyz")).toBe("wav");
  });

  it("handles no extension", () => {
    expect(audioFmtFromName("song")).toBe("wav");
  });
});
