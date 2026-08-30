import '@testing-library/jest-dom'

// jsdom does not implement ResizeObserver, but accessible headless UI primitives
// use it to preserve focus when elements move or disappear. Tests do not need
// layout measurements, so a deterministic no-op observer is sufficient.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as typeof globalThis.ResizeObserver
}
