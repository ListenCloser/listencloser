# Design-tool license / adoption checklist

Owner: #1143

Before vendoring, adapting, or installing an external design skill/tool, record:

- repository / canonical source;
- exact version / commit;
- code license;
- separate model/data/content license if applicable;
- whether prompts/skills are redistributable;
- whether generated/copied component code has its own license or author terms;
- whether a hosted service is required;
- API key / account requirements;
- network access required during normal use;
- whether community code can be written into the repository automatically;
- dependency-install behavior;
- telemetry / data sent externally;
- CI/headless suitability;
- cost/usage caps;
- maintenance activity;
- security review implications;
- removal/fallback path.

Possible decisions:

- `REFERENCE_ONLY`
- `LOCAL_EXPERIMENT`
- `ADAPT_PRINCIPLES`
- `VENDOR_PINNED`
- `INSTALL_DEV_TOOL`
- `REJECT`

Do not infer redistributability from `public GitHub repository` alone.
