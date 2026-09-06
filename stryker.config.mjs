export default {
  // This probe is intentionally scoped to projection policy. Equivalent or
  // table-unreachable mutants are suppressed in-source with explicit reasons.
  mutate: ["lib/evidence-projections.ts"],
  testRunner: "vitest",
  vitest: {
    related: true,
  },
  ignoreStatic: true,
  reporters: ["clear-text", "progress"],
  thresholds: {
    high: 80,
    low: 60,
    break: 0,
  },
  concurrency: 2,
};
