import '@testing-library/jest-dom'

// React's act() contract is part of the shared Vitest environment. Set it
// explicitly so async primitive/store updates are treated as test-managed
// updates instead of producing environment warnings.
;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

// jsdom exposes media methods but intentionally reports "Not implemented"
// when application cleanup/source changes call them. Unit tests exercise our
// state transitions rather than browser decoding, so keep those browser APIs
// deterministic and quiet here. Individual media-behavior tests can still spy
// on/replace these configurable methods.
Object.defineProperties(HTMLMediaElement.prototype, {
  pause: {
    configurable: true,
    value: () => {},
  },
  load: {
    configurable: true,
    value: () => {},
  },
})

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
