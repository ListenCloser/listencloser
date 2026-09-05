export default {
  mutate: ["lib/evidence-projections.ts"],
  testRunner: "vitest",
  vitest: {
    related: true,
  },
  reporters: ["clear-text", "progress"],
  thresholds: {
    high: 80,
    low: 60,
    break: 0,
  },
  concurrency: 2,
};
