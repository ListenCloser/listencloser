import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SharedAudioProvider, useSharedAudio } from '@/lib/audio-context';
import React from 'react';

function TestComponent() {
  const { playing, currentTime, duration } = useSharedAudio();
  return React.createElement('div', null,
    React.createElement('span', { 'data-testid': 'playing' }, String(playing)),
    React.createElement('span', { 'data-testid': 'currentTime' }, String(currentTime)),
    React.createElement('span', { 'data-testid': 'duration' }, String(duration)),
  );
}

describe('SharedAudioProvider', () => {
  it('provides default state', () => {
    render(
      React.createElement(SharedAudioProvider, null,
        React.createElement(TestComponent)
      )
    );
    expect(screen.getByTestId('playing')).toHaveTextContent('null');
    expect(screen.getByTestId('currentTime')).toHaveTextContent('0');
    expect(screen.getByTestId('duration')).toHaveTextContent('0');
  });

  it('throws when useSharedAudio is used outside provider', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(React.createElement(TestComponent))).toThrow();
    consoleSpy.mockRestore();
  });
});
