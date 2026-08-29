# Parallel Agent Workflow

This document defines the repository-owned lifecycle for running several coding agents at once.

The correctness contract lives in Git, GitHub, `AGENTS.md`, the PR template, and CI. A session manager may open terminals or supervise agents, but it must not become the source of truth for task ownership, merge readiness, or evidence.

## Principles

1. **Parallelize implementation, not ambiguous ownership.** Independent files/subsystems may move at the same time. Shared contracts such as API/state layers, persistence, temporal coordinates, dependency manifests, CI, and migrations require explicit overlap awareness.
2. **One worktree + branch per logical task.** Do not let multiple agents share one mutable checkout.
3. **One canonical PR per logical result.** Close superseded/replayed PRs promptly.
4. **Issues/docs coordinate; PRs integrate.** Do not keep a non-mergeable PR open indefinitely as the only source of direction.
5. **Green branch-head CI is not enough after `main` moves.** The protected `Build` context requires an up-to-date integration state. Refresh mechanically and rerun the gate.
6. **No merge bypasses.** Do not disable protection, weaken assertions, or add a token-based auto-merger merely to increase throughput. Native GitHub auto-merge is acceptable when it preserves the repository's normal branch-protection and required-check semantics.

## Repository helper

Use the native helper from the primary checkout:

```bash
bash scripts/agent-worktree.sh create 290 parallel-orchestration
```

This:

- fetches `origin/main`;
- creates `agent/290-parallel-orchestration`;
- creates `.worktrees/290-parallel-orchestration`;
- records local, ignored lane metadata under `.worktrees/.agent-meta/`;
- prints the exact baseline SHA.

No secrets or `.env` files are copied. Each lane must obtain whatever local configuration it legitimately needs through the normal developer setup.

If no slug is supplied for a numeric issue and authenticated `gh` is available, the helper uses the current issue title to derive one.

### See active lanes

```bash
bash scripts/agent-worktree.sh status
```

The output includes registered Git worktrees, local clean/dirty state for helper-created lanes, and—when `gh` is available—open PRs whose branches start with `agent/`.

### Check likely ownership overlap

Before editing a shared surface, check the paths you expect to own:

```bash
bash scripts/agent-worktree.sh overlap \
  lib/api-client.ts \
  backend/domain/
```

The command compares those exact files/directories against files changed by current open PRs.

A match does **not** mean all work must stop. Classify it:

- same bug / same logical change → extend or sequence behind the canonical PR;
- stacked dependency → declare the parent and keep the child delta narrow;
- same shared contract with different goals → coordinate contract semantics before editing;
- unrelated leaf files in the same broad subsystem → both lanes may proceed.

The helper intentionally does not “reserve” paths. A stale reservation system would create another coordination database to keep consistent with GitHub.

## Starting an agent

Inside the generated worktree:

```bash
cd .worktrees/290-parallel-orchestration

git status
git branch --show-current
git log -1 --oneline

gh issue view 290
gh pr list --state open
```

Then read the repository contract and the task-specific files. `docs/AGENT_EXECUTION_PLAYBOOK.md` contains the general execution/test ladder.

The task prompt should identify:

- canonical issue;
- intended files/contracts;
- known related PRs;
- acceptance criteria;
- strongest required evidence tier;
- explicit non-goals.

Do not tell an agent it “owns the whole frontend/backend” when the task only needs a bounded slice.

## During implementation

Agents should work independently until a real integration boundary appears.

Good concurrent lanes include:

- separate evaluation experiments;
- unrelated leaf UI components;
- frontend cache correctness vs worker lease correctness;
- docs/research alongside production code when they do not redefine the same contract.

High-contention lanes include:

- `AGENTS.md` / `.github/**` / merge-policy scripts;
- dependency/runtime manifests;
- database migrations;
- central API/state/cache contracts;
- shared temporal/representation semantics;
- broad styling entry points.

For those surfaces, prefer one canonical active implementation PR at a time **for that contract**, not one PR for the entire repository.

## PR handoff

A PR should carry enough metadata that another agent can integrate it without conversational history.

At minimum state:

```text
Kind:
Depends on:
Supersedes:
Known overlap:
Shared contracts/control-plane touched:
Exact verification:
```

Keep the PR delta limited to the task. If a second bug is real but separable, file or use its canonical issue and continue in another lane.

## When `main` moves

Do not restart development merely because another PR merged.

Finish the bounded implementation/evidence first. Before final merge:

```bash
git fetch origin
git merge origin/main
```

Resolve only real overlap. If the update is disjoint, it should be a mechanical integration refresh.

Then verify:

```bash
git diff origin/main...HEAD
```

The final PR diff must still contain only the intended logical change.

Push and let required CI rerun. Never reuse a green result from a prior integration state as proof that the current merge state is safe.

## CI waiting

Do not serialize productive work around hosted CI:

```text
PR A checks running
  -> begin independent lane B
PR A becomes current + green
  -> merge A
  -> refresh B onto new main when B reaches merge-ready state
```

Do not continuously rebase every active development branch after each merge. Only merge-ready branches need the final current-base cycle.

## Strict-branch integration slot

This repository's protected `main` requires the merge candidate to be up to date. On a busy branch, two independent PRs can both be correct and green yet repeatedly invalidate one another's final evidence when either one lands.

That is an **integration** serialization problem, not a reason to serialize development or ordinary CI.

Until the repository has a GitHub merge queue, use one active integration slot:

1. agents continue implementing and testing independent PRs in parallel;
2. choose one merge-ready PR as the active integration candidate;
3. read the authoritative `refs/heads/main` Git ref immediately before refresh rather than relying on possibly stale cached PR/branch metadata;
4. refresh the candidate mechanically onto that exact base, preserving only its reviewed logical delta;
5. enable native GitHub auto-merge as soon as the refreshed head is pushed;
6. let required checks run normally; GitHub should merge immediately when the current-base requirements are satisfied;
7. only after that merge, refresh the next merge-ready PR into the integration slot.

If `main` moves before the candidate finishes, repeat the current-base refresh. Do not weaken the up-to-date requirement merely to break the race.

Native GitHub auto-merge is useful here because it removes the polling gap between the final required check becoming green and the merge request being sent. It is not a custom merge bot and must not bypass normal required checks, reviews, or branch protection.

A true GitHub merge queue would be preferable because it tests queued changes against the moving target branch without requiring every PR author to keep rebasing. If repository ownership/plan later makes merge queues available, replace this integration-slot convention with the native queue rather than maintaining a bespoke queue service.

## Cleanup

After a PR is merged:

```bash
bash scripts/agent-worktree.sh cleanup 290-parallel-orchestration
```

Cleanup fails if:

- the worktree is dirty;
- an associated PR is still open;
- no merged PR can be proven.

For an intentionally discarded lane, close any open PR first and then explicitly opt into destructive local cleanup:

```bash
bash scripts/agent-worktree.sh cleanup 290-parallel-orchestration --abandon
```

Remote branch deletion is deliberately manual.

## Session managers

Tools such as tmux wrappers, OpenCode launchers, or dedicated multi-agent session managers are optional ergonomics.

They may:

- launch an agent inside a helper-created worktree;
- name/supervise terminal sessions;
- restart an interrupted CLI;
- surface GitHub/CI status.

They must not:

- silently share one checkout across agents;
- maintain a separate authoritative task/merge database;
- bypass the protected `Build` gate;
- auto-merge with credentials that suppress normal repository workflows;
- copy secrets into every worktree as a default hook;
- make cleanup destructive without Git/PR-state checks.

This keeps the workflow portable across OpenCode, Codex, Gemini, aider, or another agent CLI without changing repository correctness semantics.
