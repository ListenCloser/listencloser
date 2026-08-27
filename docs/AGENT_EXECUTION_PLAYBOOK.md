# Autonomous Agent Execution Playbook

> **Purpose:** Make implementation agents reliable enough to work for long sessions without repeatedly asking for product decisions or reporting half-working features as complete.
>
> **Read first:** `MASTER_SPEC.md`, then this document, then the relevant ADR/issue/capability registry.

---

## 1. Agent role

Implementation agents are **execution owners**, not product strategy owners.

They are expected to:

- inspect current main,
- reconcile open PRs,
- reproduce the actual problem,
- implement bounded changes,
- run the strongest reasonable verification,
- inspect the real application for user-facing work,
- open/update PRs,
- fix failures caused by their changes,
- merge routine safe work when authorized,
- continue to the next defined task.

They should not:

- invent a new product direction because it is easy to code,
- expose an unevaluated MIR output,
- replace strong OSS with a heuristic without evidence,
- spend the entire session on lint, cleanup, docs, or CI trivia when a higher-value product task is ready,
- call a feature “done” because a unit test passes.

---

## 2. Startup protocol

Every new agent starts with:

```bash
git status
git remote -v
git branch --show-current
git fetch origin
gh auth status
gh pr list
gh issue list --limit 50
```

Then read:

1. `docs/MASTER_SPEC.md`
2. `docs/AGENTS.md`
3. `docs/AGENT_EXECUTION_PLAYBOOK.md`
4. `docs/RESEARCH_LANDSCAPE.md` for MIR/model work
5. relevant ADR(s)
6. relevant GitHub issue
7. `backend/config/capabilities.json` for analysis work
8. recent merged/open PRs touching the same files/subsystem

If the working tree has unrelated user changes, preserve them. Prefer a clean worktree/branch rather than resetting or staging blindly.

---

## 3. Work selection

Use this priority function:

```text
priority ≈ user impact × confidence in direction × unblock value / implementation risk
```

Order:

1. P0 production/data/security failure.
2. P1 broken or misleading core flow.
3. Current bounded product feature already decided.
4. Reliability work that blocks multiple product PRs.
5. Evaluation work needed to unlock a major capability.
6. Cleanup/refactor only when it materially reduces current risk or agent friction.

Do not pick work merely because it is easy.

---

## 4. PR queue reconciliation

Before creating new branches, classify every relevant open PR:

- `CURRENT`
- `STACKED_DEPENDENCY`
- `NEEDS_REBASE`
- `SUPERSEDED`
- `ALREADY_IN_MAIN`
- `BLOCKED_BY_REAL_BUG`
- `BLOCKED_BY_INFRA`

Close stale PRs with a short reason.

For stacked PRs:

1. land the base,
2. rebase the child onto current main,
3. change base to main,
4. verify the child diff contains only intended changes.

Do not maintain long dependency chains if a rebase can flatten them safely.

---

## 5. Implementation loop

For each bounded task:

```text
READ
→ REPRODUCE
→ IDENTIFY ROOT CAUSE / TASK CONTRACT
→ IMPLEMENT
→ UNIT / STATIC VERIFY
→ INTEGRATION VERIFY
→ REAL PRODUCT VERIFY
→ PR
→ CI
→ FIX CAUSED FAILURES
→ MERGE
→ DEPLOY VERIFY
→ ISSUE/DOC UPDATE
→ NEXT TASK
```

Do not stop at “PR opened” unless blocked by an owner decision.

---

## 6. User-facing definition of done

A UI/product PR is complete only when the agent has inspected the actual behavior in a browser.

Minimum evidence where applicable:

- screenshot before/after,
- viewport at normal desktop/laptop size,
- interaction performed rather than static render only,
- loading/empty/error state if changed,
- real persisted work rather than only MSW mocks,
- no console/network errors relevant to the feature.

For music representations, explicitly check shared state:

- playhead,
- playback source,
- selection,
- loop,
- analysis focus,
- work switch/delete cleanup.

---

## 7. Core golden path

Changes touching workspace, jobs, analysis, representations, transport, persistence, or deployment should verify the relevant subset of:

```text
1. Sign in / library loads
2. Import a fresh licensed audio fixture
3. Work appears immediately
4. Processing progresses
5. Navigate away / return while processing
6. Processing completes
7. Reload persists Ready state
8. Original playback works
9. Transcription playback works
10. Piano Roll renders
11. Score renders
12. Score playback/cursor works
13. Spectrogram renders
14. Representation switches preserve position/source/selection
15. Analyze
16. Trusted analysis appears
17. Withheld capabilities remain absent
18. Click Inspector finding → shared selection
19. Selection visible across representations
20. Ask uses grounded evidence where provider configured
21. Reload persists analysis
22. Delete active work
23. Transport/selection/stale media clear
24. Reload confirms deletion
```

A mocked browser test does not prove steps involving worker, models, Supabase, deployment, or object storage.

---

## 8. MIR / analysis PR protocol

Any new analysis capability must have a clear task definition.

Before implementation, answer:

1. What exact musical fact/observation are we trying to infer?
2. Is the task audio, symbolic, score, stem, embedding, or multimodal?
3. What existing OSS/research systems solve it?
4. Which benchmark/data exists?
5. What current baseline exists?
6. What product wording is safe?

### 8.1 Hard inference requires evaluation

Examples:

- transcription,
- chord recognition,
- melody extraction,
- beat/downbeat tracking,
- structure segmentation,
- source separation,
- genre/instrument classifiers,
- semantic form labeling.

These should not be invented as ad-hoc heuristics unless existing solutions have been evaluated and a clear gap remains.

### 8.2 Safe deterministic derivation

Once evidence is reliable, small deterministic transformations are appropriate.

Examples:

- interval distribution from extracted melody,
- chord-change rate from trusted chord spans,
- range from melody notes,
- onset phase relative to trusted beats.

Even these require tests and conservative wording.

### 8.3 Capability gate

Update `backend/config/capabilities.json` in the same PR when product maturity/exposure changes.

Never create a second frontend truthfulness registry. Frontend allowlists may be defense-in-depth/presentation constraints only.

---

## 9. Music engine replacement checklist

Before changing a production default engine, record:

### Candidate identity

- project/repo,
- paper/venue,
- engine version,
- model version/checksum.

### Licensing

- code license,
- weight license,
- dataset/training restrictions.

### Operations

- Python/platform compatibility,
- CPU/GPU,
- latency,
- peak RAM,
- install/model size,
- runtime downloads,
- container/ARM fit.

### Evaluation

- dataset,
- split IDs / seed,
- baseline,
- established metrics,
- aggregate + per-piece distribution,
- failure rate,
- domain limitations.

### Integration

- thin adapter,
- canonical output contract,
- provenance,
- failure/fallback behavior,
- smoke test that cannot silently skip in supported production environment.

A code license does not imply trained weights are usable. Verify separately.

---

## 10. Research-agent protocol

Research agents should produce decisions, not surveys.

Timebox exploratory landscape work unless the user explicitly requests deep research.

Output:

```text
TASK
CANDIDATES
LICENSE
BENCHMARK
OPERATIONAL FIT
RESULTS
DECISION
PRODUCTION GATE
NEXT IMPLEMENTATION TASK
```

“Repository exists” is not evidence that it works.

“Looks plausible on real-piano.m4a” is not benchmark validation.

---

## 11. Test ladder

Use the cheapest test that can prove the claim, then move upward when the claim crosses system boundaries.

### Unit

For:

- pure derivations,
- coordinate/time mappings,
- transformations,
- schema helpers.

### Component / frontend unit

For:

- rendering states,
- presentation filtering,
- component interactions.

### MSW E2E

For:

- deterministic frontend interaction and API contract behavior.

Does not prove backend/model availability.

### Backend integration

For:

- repositories,
- DB behavior,
- worker lifecycle,
- persistence,
- engine adapter wiring.

### Real-stack E2E

For:

- fresh DB + API + worker + frontend,
- real artifacts,
- real job orchestration.

### Production smoke

For:

- secret/config correctness,
- deployed SHA,
- external networking,
- worker availability,
- actual service integration.

---

## 12. CI failure discipline

Classify every failure:

- `CAUSED_BY_PR`
- `PRE_EXISTING_MAIN`
- `INFRA`
- `FLAKE`
- `EXPECTED_VISUAL_CHANGE`
- `REAL_PRODUCT_BUG`
- `UNKNOWN`

Evidence examples:

- same test failing on current main,
- trace/log identifying a stale lease,
- branch diff changes selector contract,
- timeout from missing runtime service,
- Argos screenshot intentionally changed.

Do not weaken assertions because CI is inconvenient.

When one unrelated required check blocks multiple PRs, that blocker becomes a high-priority throughput issue and should be fixed narrowly.

---

## 13. PR body template

```markdown
## Problem
What user/system failure exists?

## Root cause / evidence
What proves the cause or task need?

## Approach
What changed and why this approach?

## Product behavior
What does the user now experience?

## Truthfulness / capability status
What is exposed, qualified, withheld?

## OSS / research
What upstream solution was used/evaluated, if relevant?

## Verification
- unit
- integration
- browser/E2E
- real-stack/production where relevant

## Visual evidence
Screenshots/video for UI changes.

## Deployment/config impact
Secrets, deps, migrations, model artifacts, runtime cost.

## Limitations
What is deliberately not claimed/fixed?
```

---

## 14. Product verification notes required in final agent report

Agents must distinguish **implemented** from **observed already working**.

Bad report:

> “Delete clears transport.”

when the PR never touched delete and no browser evidence was recorded.

Good report:

> “Verified existing delete behavior in production: while Original played at 0:21, deleting the active work stopped audio and reset duration/playhead; no code change required.”

---

## 15. Performance / observability

For slow model/job work, use existing OpenTelemetry/Grafana evidence before guessing.

Useful correlation:

- release SHA,
- job ID,
- work/version ID,
- engine,
- stage duration,
- result count,
- fallback/failure.

Do not attach raw audio, secrets, private prompts, or sensitive user content to telemetry.

---

## 16. Database / migrations

Escalate before destructive migrations or irreversible user-data changes.

Otherwise:

- migrations are forward-only,
- test fresh local schema from zero,
- preserve RLS,
- verify real migrations rather than editing production manually,
- keep immutable artifact/version lineage.

---

## 17. Dependency policy

Before adding a dependency, answer:

- can an existing dependency do this?
- license?
- maintenance/activity?
- transitive weight?
- Python/Node compatibility?
- native build requirements?
- deployment target compatibility?
- model/data download behavior?

Do not add a framework for a 20-line deterministic helper.

Do not implement a 500-line MIR detector because adding a well-supported dependency feels inconvenient.

---

## 18. Scope control

Agents should fix related blockers inline but avoid expanding scope indefinitely.

Rule:

- tiny directly-related issue → fix,
- bounded blocker → separate small PR,
- major unrelated issue → GitHub issue, continue.

Do not combine:

- feature,
- architecture rewrite,
- dependency migration,
- unrelated cleanup,
- design-system overhaul

in one PR unless they are inseparable.

---

## 19. Owner escalation criteria

Ask the owner only for:

- credentials or account actions,
- destructive production/data operation,
- paid service choice,
- ambiguous/restrictive licensing decision,
- substantial privacy/security policy change,
- major product fork with different user experiences,
- architecture decision with material long-term cost and no clear safer choice.

Do not escalate:

- naming,
- formatting,
- normal refactors,
- choosing between equivalent implementation details,
- test fixture creation,
- routine PR merges,
- ordinary bug fixes.

---

## 20. Long-session operating loop

Agents should use CI wait time productively.

Example:

```text
PR A CI running
  → start isolated PR B worktree
PR B tests running
  → verify PR A preview
PR A green
  → merge
  → rebase B
  → continue
```

Do not spend twenty minutes polling GitHub Actions.

---

## 21. Product-over-plumbing rule

Infrastructure is a means, not the product.

Prefer:

- useful synchronized representation,
- better evidence engine,
- grounded explanation,
- robust import/playback/analysis,

before:

- another CI abstraction,
- generic refactor,
- new dashboard,
- dependency churn,
- enterprise platform tooling,

unless the plumbing is a demonstrated blocker to product throughput or reliability.

---

## 22. Final report template

```markdown
# Merged PRs
# | SHA | purpose | user impact

# Closed / superseded PRs
# | reason

# Production verification
Exact work/fixture and flow exercised.

# Product state
Library:
Playback:
Representations:
Harmony:
Melody:
Rhythm:
Structure:
Ask:

# Evaluation / evidence
Datasets, metrics, runtime.

# CI / operational failures
Failure → classification → resolution.

# Deferred issues
Only meaningful work with issue IDs.

# Next 3 priorities
Ranked by product value.

# Owner blockers
Only genuine decisions/actions.
```

The report must not substitute for the work itself.
