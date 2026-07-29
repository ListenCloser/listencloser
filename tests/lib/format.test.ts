import { describe, it, expect } from 'vitest';
import { blobToBase64, formatTime, audioFmtFromBlob, audioFmtFromName } from '@/lib/format';

describe('blobToBase64', () => {
  it('converts a small blob to base64', async () => {
    const blob = new Blob(['hello'], { type: 'text/plain' });
    const result = await blobToBase64(blob);
    expect(result).toBe(btoa('hello'));
  });

  it('converts an empty blob', async () => {
    const blob = new Blob([], { type: 'text/plain' });
    const result = await blobToBase64(blob);
    expect(result).toBe('');
  });
});

describe('formatTime', () => {
  it('formats zero seconds', () => {
    expect(formatTime(0)).toBe('0:00');
  });

  it('formats seconds under a minute', () => {
    expect(formatTime(45)).toBe('0:45');
  });

  it('formats exactly one minute', () => {
    expect(formatTime(60)).toBe('1:00');
  });

  it('formats minutes and seconds', () => {
    expect(formatTime(125)).toBe('2:05');
  });
});

describe('audioFmtFromBlob', () => {
  it('detects WAV', () => {
    expect(audioFmtFromBlob(new Blob([], { type: 'audio/wav' }))).toBe('wav');
  });

  it('detects MP3', () => {
    expect(audioFmtFromBlob(new Blob([], { type: 'audio/mpeg' }))).toBe('mp3');
  });

  it('detects M4A as MP4', () => {
    expect(audioFmtFromBlob(new Blob([], { type: 'audio/mp4' }))).toBe('mp4');
  });

  it('defaults to WAV', () => {
    expect(audioFmtFromBlob(new Blob([], { type: 'text/plain' }))).toBe('wav');
  });
});

describe('audioFmtFromName', () => {
  it('detects .wav', () => {
    expect(audioFmtFromName('song.wav')).toBe('wav');
  });

  it('detects .mp3', () => {
    expect(audioFmtFromName('song.mp3')).toBe('mp3');
  });

  it('detects .m4a as mp4', () => {
    expect(audioFmtFromName('song.m4a')).toBe('mp4');
  });

  it('defaults to WAV', () => {
    expect(audioFmtFromName('song.xyz')).toBe('wav');
  });
});
