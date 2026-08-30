# Architecture source-of-truth matrix

The purpose of this table is to prevent architecture documentation from becoming another configuration authority.

When two sources disagree, prefer the machine/code authority listed below and either update descriptive docs or open a correctness issue.

| Question | Canonical authority | Descriptive/supporting sources | Explicit non-authority / warning |
|---|---|---|---|
| What product/runtime is deployed? | deployment configuration + runtime release identity | `docs/ARCHITECTURE.md`, this directory | old PR descriptions, stale production-readiness reports |
| What is the future product/analysis direction? | `docs/MASTER_SPEC.md` + accepted ADRs/product roadmap issues | research/implementation plans | shipped-runtime docs |
| What HTTP endpoints/schema exist? | FastAPI app/OpenAPI (`openapi/openapi.json`) | generated `lib/api-types.ts`, client methods | handwritten TS type copies, docs tables |
| Does frontend match backend HTTP schema? | `npm run api:check` + generated operation contract | `lib/api-client.ts` normalization | prose saying contracts are synced |
| What tables/columns/RLS/grants exist from source? | `supabase/migrations/` | generated DB types, DB integration tests | Pydantic models alone |
| What actually exists in deployed DB? | provider/live schema inspection + release/migration identity | migrations expected to reproduce it | assumptions from latest migration filename |
| Who owns a Project/Work request? | auth + repository/domain authorization logic and DB policy | architecture trust-boundary docs | service-role possession |
| Which Storage object may be signed/deleted? | authoritative Version→Artifact→Work→Project provenance/locator policy | private Storage configuration | raw `storage_key` text alone |
| What analysis capability is product-visible? | `backend/config/capabilities.json` + policy tests | Inspector/Ask docs | presence of a handler/result file |
| What internal worker capabilities exist? | worker registration/composition code | tests, capability docs | public API action list |
| What public workflow actions exist? | FastAPI route/request policy | generated OpenAPI | worker registry names (#632) |
| Which concrete engine can be constructed? | `backend/engines/registry.py` | engine adapters/tests | capability registry alone |
| Which engine is effective in production? | registry selection **plus deployment env/config** plus persisted provenance | `backend/docker-compose.yml`, release config | registry default alone |
| What version of an npm dependency is installed? | lockfile/package manifest | dependency docs | README prose |
| What version of a Python dependency is installed? | `backend/pyproject.toml` + `backend/uv.lock` | Docker/build config | `pip install` snippets in old docs |
| Which dependency belongs to API vs worker/eval? | target dependency groups after #287 + import-boundary tests | dependency inventory | "unused" static warning alone |
| What is the durable musical object graph? | Supabase schema + domain persistence behavior | `domain/models.py`, `data-model.md` | UI component state |
| Which Version is authoritative for a visible representation/claim? | exact Version identity + explicit representation-role/lineage policy | Work bundle/client resolver | newest-by-kind heuristic (#613) |
| What musical evidence was produced? | persisted Entity/Insight/Alignment + provenance on exact Version | Work bundle/Inspector | UI copy or model reputation |
| What does `confidence` mean? | field-specific model/producer semantics + evaluation | truthfulness tests | arbitrary defaults/fixed literals (#640) |
| Why was an OSS/model candidate promoted? | durable evaluation result + decision record + capability policy | evaluation summary docs | PR body alone (#636) |
| What benchmark methodology/result is current? | machine-readable dataset/evaluator/result manifests | generated Markdown summary | copied metric numbers in multiple docs |
| What tests are required for a change? | repository check policy + protected CI workflow/risk classifier | `AGENTS.md`, execution docs | agent assertion that "tests passed" without exact evidence |
| What checks protect `main`? | GitHub branch protection/rules + workflow definitions | control-plane docs | historical required-check list |
| What exact source was deployed? | deploy artifact/image metadata + runtime release identity | GitHub workflow run | branch name `main` alone |
| Is API/worker healthy? | health/readiness endpoints + worker heartbeat/queue health | production smoke | process exists / container is running |
| What telemetry is emitted? | `observability.py`, instrumentation call sites and runtime config | `docs/observability/` once #637 lands | dashboard screenshot without code/runtime provenance |
| What are the product SLOs? | version-controlled SLO definitions backed by emitted metrics/smokes | dashboards/runbooks | ad-hoc threshold in one workflow |
| What frontend component owns a behavior? | current imports/state/data flow + tested component/hook contract | Storybook if adopted, frontend map | CSS selector filename or visual resemblance |
| What global style wins? | current CSS cascade/import order until #523 consolidates it | design docs | file suffix `v6` meaning "canonical" |
| Is code dead? | reachability/import/runtime evidence + tests + ownership classification | Knip/Vulture/Ruff candidates | one static analyzer warning |
| Is an architecture dependency legal? | explicit import contracts once #417/#639 land | architecture docs | informal folder naming |

## Generated vs handwritten contract rule

Prefer one direction of generation:

```text
source model/schema
  → generated artifact
  → drift check
  → handwritten application normalization where genuinely stricter semantics are needed
```

Do not maintain two editable representations of the same wire/database contract.

## Registry rule

A registry should answer one coherent question.

Examples:

- `capabilities.json`: evidence maturity/exposure;
- engine registry: construct/select engine adapters;
- future evaluation registry: datasets/evaluators/results/decisions.

Do not reuse one registry merely because adding another field is easy when the policy question is different. The public workflow-action bug tracked by #632 is an example of why internal execution registration and external API exposure need distinct contracts.

## Documentation lifecycle rule

A document that describes current behavior must either:

1. be maintained as a canonical current-state entry point; or
2. clearly state that it is historical/superseded and point to the current authority.

Names such as `CURRENT`, `FINAL`, `V3`, or a PR-era readiness report do not make a file authoritative. #641/#629 own the broader repository documentation-authority cleanup.