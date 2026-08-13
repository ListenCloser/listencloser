import { describe, it, expect } from 'vitest';
import { blobToBase64, formatTime, audioFmtFromBlob, audioFmtFromName, presentableTitle, understandStageLabel } from '@/lib/format';

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

describe('presentableTitle', () => {
  it('keeps a meaningful title unchanged', () => {
    expect(presentableTitle('my piano piece')).toBe('my piano piece');
  });

  it('strips a trailing audio extension when present', () => {
    expect(presentableTitle('recording.wav')).toBe('recording');
  });

  it('collapses pathological whitespace', () => {
    expect(presentableTitle('  take    two  ')).toBe('take two');
  });

  it('handles pathological raw filenames without throwing', () => {
    expect(presentableTitle('+_+')).toBe('+_+');
  });

  it('falls back when the title is empty', () => {
    expect(presentableTitle('   ')).toBe('Untitled piece');
  });

  it('truncates very long titles safely', () => {
    const long = 'a'.repeat(200);
    const result = presentableTitle(long);
    expect(result.length).toBeLessThanOrEqual(48);
    expect(result).toContain('…');
  });
});

describe('understandStageLabel', () => {
  it('describes the preparation stage early', () => {
    expect(understandStageLabel(0.1)).toBe('Preparing your recording…');
  });

  it('describes transcription in the middle', () => {
    expect(understandStageLabel(0.45)).toBe('Transcribing notes…');
  });

  it('describes analysis near the end', () => {
    expect(understandStageLabel(0.8)).toBe('Analyzing the music…');
  });

  it('describes score building at completion', () => {
    expect(understandStageLabel(0.95)).toBe('Building the score…');
  });
});
