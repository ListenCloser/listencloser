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
      name: "production-does-not-import-tests",
      severity: "error",
      from: { path: "^(app|components|lib)/" },
      to: { path: "^tests/" },
    },
    {
      name: "production-does-not-statically-import-runtime-mocks",
      severity: "error",
      from: { path: "^(app|components|lib)/" },
      to: { path: "^mocks/", dynamic: false },
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
