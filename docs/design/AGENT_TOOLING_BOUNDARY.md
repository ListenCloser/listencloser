# Agent design-tooling integration boundary

Owner: #1143

## Current environment finding

No directly installable ChatGPT plugin was discovered for the initial external design-tool candidates (21st.dev, Mobbin, SuperDesign, design-taste/frontend-design) in the current plugin catalog.

That means Phase 0 should **not** depend on a hidden ChatGPT-plugin integration to be reproducible.

## Integration policy

Evaluate external design tooling through one of these explicit paths:

1. **Web/reference-only** — use the product/site/repository as research input; no repo/runtime dependency.
2. **Repo-native skill/instruction** — after license review, adapt *principles* into a Listen Closer-owned agent instruction rather than creating a permanent runtime dependency on an external service.
3. **Developer-local CLI/MCP experiment** — use an external design agent/catalog only on a bounded research branch; document setup, credentials, version and output. Do not make normal repository verification depend on it.
4. **Production dependency** — exceptional; requires a concrete runtime product need. None is currently proposed by #1143.

## Default for initial candidates

| Candidate | Initial integration path |
| --- | --- |
| Mobbin | web/reference-only |
| 21st.dev | web/reference + bounded developer-local CLI/MCP experiment |
| frontend-design skill | repository-source review; bounded local skill experiment if license/setup fit |
| taste/design-taste skill | repository-source review; bounded critic experiment if license/setup fit |
| SuperDesign | bounded developer-local exploration only |
| Vercel Web Interface Guidelines | web/reference; later adapt applicable mechanical rules into repo-native review guidance |
| Playwright visual suite | existing repo-native evidence layer |

## Why

The design process should remain reproducible from the repository even if a third-party design service disappears, changes pricing, or is unavailable to a future agent.

External tools may improve exploration. **The durable result must be the chosen design reasoning, system, examples, and review gates—not the external tool itself.**
