import { describe, it, expect, beforeEach } from 'vitest';
import { apiErrorMessage, clearTokenCache } from '@/lib/api';

describe('clearTokenCache', () => {
  beforeEach(() => {
    clearTokenCache();
  });

  it('does not throw', () => {
    expect(() => clearTokenCache()).not.toThrow();
  });

  it('can be called multiple times', () => {
    expect(() => {
      clearTokenCache();
      clearTokenCache();
      clearTokenCache();
    }).not.toThrow();
  });
});

describe('apiErrorMessage', () => {
  it('preserves existing error envelopes', () => {
    expect(apiErrorMessage({ error: 'Upload failed' }, 400)).toBe('Upload failed');
  });

  it('surfaces FastAPI string details', () => {
    expect(apiErrorMessage({ detail: 'Audio file is too large' }, 413)).toBe('Audio file is too large');
  });

  it('surfaces FastAPI validation messages', () => {
    expect(apiErrorMessage({
      detail: [
        { loc: ['body', 'filename'], msg: 'Field required', type: 'missing' },
        { loc: ['body', 'byte_size'], msg: 'Input should be greater than 0', type: 'greater_than' },
      ],
    }, 422)).toBe('Field required; Input should be greater than 0');
  });

  it('falls back safely for unknown payloads', () => {
    expect(apiErrorMessage({ detail: { unexpected: true } }, 502)).toBe('Request failed: 502');
  });
});
