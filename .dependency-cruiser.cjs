module.exports = {
  forbidden: [
    {
      name: "no-circular",
      severity: "error",
      from: { pathNot: "^node_modules" },
      to: { circular: true },
    },
    {
      name: "not-to-unresolvable",
      severity: "error",
      from: {},
      to: { couldNotResolve: true },
    },
    {
      name: "production-does-not-import-test-code",
      severity: "error",
      from: { path: "^(app|components|lib)/" },
      to: { path: "^(tests|mocks)/" },
    },
  ],
  options: {
    doNotFollow: {
      dependencyTypes: [
        "npm",
        "npm-dev",
        "npm-optional",
        "npm-peer",
        "npm-bundled",
      ],
    },
    tsConfig: { fileName: "tsconfig.json" },
    reporterOptions: {
      mermaid: { minify: false },
    },
  },
};
