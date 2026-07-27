import { describe, it, expect, vi, beforeEach } from 'vitest';
import { clearTokenCache } from '@/lib/api';

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
