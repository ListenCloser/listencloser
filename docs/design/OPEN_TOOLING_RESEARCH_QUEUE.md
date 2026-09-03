# Open design-tooling primary-source research queue

Owner: #1143

Before any candidate is installed, vendored, or adapted, inspect the canonical source and complete `TOOLING_LICENSE_CHECKLIST.md`.

## Priority A — likely to change agent behavior

1. Anthropic frontend-design skill
   - canonical repository/source;
   - exact skill text and intended use;
   - license;
   - whether the useful behavior can be evaluated without copying the skill into production repo guidance.

2. Taste / design-taste skill families
   - canonical repository/source for each candidate;
   - distinguish critique-oriented rules from generation-style presets;
   - license;
   - identify rules that are general anti-patterns vs author's aesthetic preferences.

3. Design-DNA `/taste` extraction workflow
   - canonical repository/source;
   - extraction method and output format;
   - license;
   - test on one heterogeneous reference before broader use.

4. SuperDesign
   - canonical repository/source;
   - local/runtime setup;
   - license;
   - whether it can operate against existing code/screenshot context without becoming a second design source of truth.

## Priority B — implementation/reference infrastructure

5. 21st.dev / 21st MCP
   - CLI/MCP setup;
   - account/API-key requirements;
   - community component licensing model;
   - code/dependency installation behavior;
   - ability to scope search/reuse to a project's own approved components;
   - cost/usage constraints.

6. Vercel Web Interface Guidelines / agent skill
   - canonical source;
   - license;
   - separate universal mechanical rules from Vercel-specific copy/brand preferences;
   - evaluate as reviewer, not generator.

7. Mobbin
   - research access model;
   - terms relevant to screenshots/reference use;
   - do not vendor or redistribute reference imagery without explicit rights.

## Required output

For every candidate:

```text
SOURCE:
VERSION / COMMIT:
LICENSE:
HOSTED SERVICE REQUIRED:
ACCOUNT / KEY REQUIRED:
WRITES CODE / INSTALLS DEPENDENCIES:
NETWORK REQUIRED:
CI / HEADLESS FIT:
SECURITY NOTES:
BEST JOB:
MAIN FAILURE MODE:
LISTEN CLOSER EVALUATION:
INITIAL DECISION:
```
