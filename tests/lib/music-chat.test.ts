import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { deriveTrackState, type LibFile } from '@/lib/types';

// Mock useChat
vi.mock('@ai-sdk/react', () => ({
  useChat: () => ({
    messages: [],
    sendMessage: vi.fn(),
    status: 'ready',
    setMessages: vi.fn(),
  }),
}));

// Mock PianoRoll
vi.mock('@/components/PianoRoll', () => ({
  default: ({ notes }: { notes: unknown[] }) =>
    React.createElement('div', { 'data-testid': 'piano-roll' }, `${notes.length} notes`),
}));

// Mock synthAudio
vi.mock('@/lib/music', () => ({
  synthAudio: vi.fn(),
  blobToBase64: vi.fn(),
}));

describe('deriveTrackState', () => {
  it('returns uploaded=true for all tracks', () => {
    const file: LibFile = { name: 'test.wav', url: '', id: '1' };
    const state = deriveTrackState(file);
    expect(state.uploaded).toBe(true);
  });

  it('returns transcribed=true when notes exist', () => {
    const file: LibFile = { name: 'test.wav', url: '', id: '1', notes: [{ pitch: 60, start: 0, end: 1, velocity: 100 }] };
    const state = deriveTrackState(file);
    expect(state.transcribed).toBe(true);
    expect(state.hasMidi).toBe(false);
  });

  it('returns transcribed=false when no notes', () => {
    const file: LibFile = { name: 'test.wav', url: '', id: '1' };
    const state = deriveTrackState(file);
    expect(state.transcribed).toBe(false);
  });

  it('returns analysis=true when analysis exists', () => {
    const file: LibFile = { name: 'test.wav', url: '', id: '1', analysis: { key: { tonic: 'C', mode: 'major', confidence: 0.85 } } };
    const state = deriveTrackState(file);
    expect(state.analysis).toBe(true);
  });

  it('returns hasMidi=true when midi_base64 exists', () => {
    const file: LibFile = { name: 'test.wav', url: '', id: '1', midi_base64: 'abc123' };
    const state = deriveTrackState(file);
    expect(state.hasMidi).toBe(true);
  });

  it('returns sheetMusic=true when musicxml exists', () => {
    const file: LibFile = { name: 'test.wav', url: '', id: '1', musicxml: '<xml>...</xml>' };
    const state = deriveTrackState(file);
    expect(state.sheetMusic).toBe(true);
  });
});
