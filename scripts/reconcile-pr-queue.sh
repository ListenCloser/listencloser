#!/usr/bin/env bash
# Drain the open-PR queue against the protected base branch.
#
# This is a repo-owned, agent/human-invoked queue command. It is deliberately
# NOT an Actions workflow and NEVER uses the repository GITHUB_TOKEN. It calls
# GitHub's native `update-branch` and `auto-merge` endpoints so that GitHub's
# native merge queue remains the single merge authority for `main`.
#
# Per non-draft PR targeting BASE_BRANCH this command decides one of:
#   - genuine conflict   -> ensure the `needs-reconcile` label and list the
#                           conflicting files (via local git merge-tree)
#   - just behind base   -> update branch from base (merge via native
#                           update-branch, or rebase with --method rebase)
#   - clean and green    -> enable auto-merge (enters the native merge queue)
#   - otherwise          -> report state; do nothing
#
# The loop re-checks as the base moves. Exit 0 when every PR is either
# reconciled/queued/merged or no further progress is possible this pass.

set -euo pipefail

REPO="${REPO:-$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)}"
BASE_BRANCH="${BASE_BRANCH:-main}"
METHOD="${METHOD:-merge}"            # merge (GitHub update-branch) | rebase
LABEL="${LABEL:-needs-reconcile}"
INTERVAL="${INTERVAL:-120}"          # seconds between passes
MAX_ITERATIONS="${MAX_ITERATIONS:-0}" # 0 = keep looping; --once sets 1
DRY_RUN=false

usage() {
  cat <<'EOF'
Usage: scripts/reconcile-pr-queue.sh [options]

Options:
  --base <branch>      base branch to reconcile against (default: main)
  --method merge|rebase update strategy for behind PRs (default: merge)
  --interval <secs>    seconds between loop passes (default: 120)
  --max-iterations <n> stop after n passes; 0 = until no progress (default: 0)
  --label <name>       conflict label to apply (default: needs-reconcile)
  --dry-run            print intended actions without changing anything
  --once               single pass, then exit
  -h, --help           show this help

Environment: requires `gh` authenticated with a token that has write access to
the repository (a PAT or GitHub App installation token). It must be able to
update PR head branches and enable auto-merge. Run from inside the repository.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --base) BASE_BRANCH="$2"; shift 2 ;;
    --method) METHOD="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --max-iterations) MAX_ITERATIONS="$2"; shift 2 ;;
    --label) LABEL="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --once) MAX_ITERATIONS=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$REPO" ]; then
  echo "error: could not determine the GitHub repository; run from inside the repo or set REPO" >&2
  exit 2
fi
if ! command -v gh >/dev/null 2>&1; then
  echo "error: gh CLI is required" >&2
  exit 2
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "error: gh is not authenticated; use a token with write access to $REPO" >&2
  exit 2
fi

ensure_label() {
  gh label create "$LABEL" --repo "$REPO" \
    --color B60205 \
    --description "Pull request has genuine merge conflicts and requires agent reconciliation." >/dev/null 2>&1 || true
}

# List files that conflict when merging $base_oid into $head_oid, using a local
# 3-way merge-tree simulation. `--name-only` prints the tree OID line, then the
# conflict file list, then informational Auto-merging/CONFLICT messages; only
# the file list is surfaced. Falls back to empty on any git failure (e.g. fork
# PR branches not fetched locally); the label is still applied.
conflicted_files() {
  local base_oid="$1" head_oid="$2"
  git merge-tree --write-tree --name-only "$base_oid" "$head_oid" 2>/dev/null \
    | sed -n '2,/^$/p' \
    | grep -v '^$' || true
}

# GitHub's native "Update branch" merges the base into the head (202/204) or
# reports a conflict (409). gh pr rebase force-pushes and is only used when
# explicitly requested with --method rebase.
update_branch() {
  local n="$1" head_sha="$2"
  if "$DRY_RUN"; then
    echo "  [dry-run] would update branch of PR #$n from $BASE_BRANCH"
    return 0
  fi
  if [ "$METHOD" = rebase ]; then
    gh pr rebase "$n" --repo "$REPO" --force 2>&1 | sed 's/^/    /'
    return $?
  fi
  gh api -X PUT "repos/$REPO/pulls/$n/update-branch" \
    -f expected_head_sha="$head_sha" >/dev/null 2>&1
}

check_state() {
  local n="$1"
  gh pr view "$n" --repo "$REPO" --json \
    number,title,isDraft,mergeable,mergeStateStatus,headRefName,headRefOid,headRepositoryOwner,baseRefName,labels,statusCheckRollup \
    --jq '{n: .number, title: .title, draft: .isDraft, mergeable: .mergeable, state: .mergeStateStatus, head: .headRefName, head_oid: .headRefOid, head_owner: .headRepositoryOwner.login, labels: [.labels[].name], build: ([.statusCheckRollup[] | select(.name == "build") | {status, conclusion}][0] // null)}'
}

build_ok() {
  python3 -c '
import json, sys
d = json.loads(sys.argv[1])
b = d.get("build")
raise SystemExit(0 if b and b.get("status") == "COMPLETED" and b.get("conclusion") == "SUCCESS" else 1)
' "$1"
}

has_label() {
  python3 -c '
import json, sys
d = json.loads(sys.argv[1])
raise SystemExit(0 if sys.argv[2] in d.get("labels", []) else 1)
' "$1" "$LABEL"
}

# Returns 0 if the most recent merge-group full validation for this PR failed.
# The merge group ref is gh-readonly-queue/main/pr-<n>-<sha>; a failed run means
# the expensive whole-system proofs failed on the composed SHA even though the
# PR's own fast-admission `build` is green. Re-enqueueing would only loop.
merge_group_failed() {
  local n="$1" conclusion
  conclusion="$(
    gh run list --repo "$REPO" --workflow=build.yml --event merge_group --limit 15 \
      --json headBranch,conclusion \
      --jq ".[] | select(.headBranch | startswith(\"gh-readonly-queue/main/pr-$n-\")) | .conclusion" \
      | head -n 1
  )"
  case "$conclusion" in
    failure|timed_out|startup_failure) return 0 ;;
    *) return 1 ;;
  esac
}

drain_once() {
  local base_oid prs
  base_oid="$(git fetch origin "$BASE_BRANCH" >/dev/null 2>&1 && git rev-parse "origin/$BASE_BRANCH")" || {
    echo "  could not fetch $BASE_BRANCH; skipping pass" >&2
    return 1
  }

  echo "── Reconcile pass against $BASE_BRANCH @ ${base_oid:0:12} ($REPO) ──"

  prs="$(gh pr list --repo "$REPO" --state open --base "$BASE_BRANCH" \
    --json number,isDraft --jq '[.[] | select(.isDraft == false) | .number] | .[]')"
  if [ -z "$prs" ]; then
    echo "  no non-draft open PRs"
    return 0
  fi

  local progressed=false
  local n state title head head_oid mergeable state_val files

  for n in $prs; do
    state="$(check_state "$n" || true)"
    if [ -z "$state" ]; then
      echo "  #$n: could not read state; skipping"
      continue
    fi

    title="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["title"])' "$state")"
    head="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["head"])' "$state")"
    head_oid="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["head_oid"])' "$state")"
    head_owner="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["head_owner"])' "$state")"
    mergeable="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["mergeable"])' "$state")"
    state_val="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["state"])' "$state")"

    echo "  #$n ($head): $title"

    # Fork PRs have heads we cannot update through the same-repo API; report
    # state but take no branch/merge action.
    if [ "$head_owner" != "${REPO%%/*}" ]; then
      echo "    fork PR; reconciler takes no action (owner $head_owner)"
      continue
    fi

    # GitHub reports a non-boolean mergeable enum (CONFLICTING / MERGEABLE /
    # UNKNOWN). mergeStateStatus is the authoritative signal:
    #   DIRTY     -> genuine conflict (mergeable == CONFLICTING)
    #   BEHIND    -> just stale, can be refreshed
    #   CLEAN     -> mergeable, checks green
    #   UNSTABLE  -> mergeable but checks pending/failing
    #   BLOCKED   -> blocked by policy/required checks
    #   UNKNOWN   -> GitHub still computing

    if [ "$mergeable" = "UNKNOWN" ] || [ "$state_val" = "UNKNOWN" ]; then
      echo "    GitHub still computing mergeability; leave for the next pass"
      continue
    fi

    # DIRTY merge state is a genuine conflict, not a stale branch. Only these
    # go to reconciliation agents.
    if [ "$state_val" = "DIRTY" ]; then
      echo "    CONFLICT -> needs-reconcile"
      if "$DRY_RUN"; then
        echo "    [dry-run] would label #$n $LABEL"
      elif ! has_label "$state"; then
        gh pr edit "$n" --repo "$REPO" --add-label "$LABEL" >/dev/null 2>&1 || true
      fi
      git fetch origin "$head" >/dev/null 2>&1 || true
      files="$(conflicted_files "$base_oid" "$head_oid")"
      if [ -n "$files" ]; then
        echo "    conflicting files:"
        while IFS= read -r file; do
          [ -n "$file" ] && echo "      $file"
        done <<< "$files"
      fi
      progressed=true
      continue
    fi

    # Behind the base but still mergeable in principle: refresh from base.
    if [ "$state_val" = "BEHIND" ]; then
      echo "    behind $BASE_BRANCH -> updating branch"
      if update_branch "$n" "$head_oid"; then
        echo "    update accepted; CI will re-run on the refreshed head"
        progressed=true
      else
        echo "    update conflicted -> needs-reconcile"
        if ! "$DRY_RUN" && ! has_label "$state"; then
          gh pr edit "$n" --repo "$REPO" --add-label "$LABEL" >/dev/null 2>&1 || true
        elif "$DRY_RUN"; then
          echo "    [dry-run] would label #$n $LABEL"
        fi
        progressed=true
      fi
      continue
    fi

    # Clean/stable and green: hand to the native merge queue via auto-merge.
    if [ "$state_val" = "CLEAN" ] || [ "$state_val" = "UNSTABLE" ]; then
      if build_ok "$state"; then
        if merge_group_failed "$n"; then
          echo "    build green on PR head but merge_group full validation FAILED -> needs-reconcile"
          if "$DRY_RUN"; then
            echo "    [dry-run] would label #$n $LABEL"
          elif ! has_label "$state"; then
            gh pr edit "$n" --repo "$REPO" --add-label "$LABEL" >/dev/null 2>&1 || true
          fi
          progressed=true
          continue
        fi
        echo "    build green -> enabling auto-merge (enters native merge queue)"
        if "$DRY_RUN"; then
          echo "    [dry-run] would run: gh pr merge $n --auto --squash"
        elif gh pr merge "$n" --repo "$REPO" --auto --squash >/dev/null 2>&1; then
          echo "    auto-merge enabled for #$n"
        else
          echo "    auto-merge could not be enabled (branch policy?); inspect #$n"
        fi
        progressed=true
      else
        echo "    build pending/failing; waiting"
      fi
      continue
    fi

    case "$state_val" in
      DRAFT) echo "    draft; skipped" ;;
      BLOCKED) echo "    blocked by policy/required review; left for the queue" ;;
      *) echo "    state=$state_val; no action this pass" ;;
    esac
  done

  "$progressed"
}

ensure_label

iteration=0
while :; do
  iteration=$((iteration + 1))
  drain_once || true
  if [ "$MAX_ITERATIONS" -gt 0 ] && [ "$iteration" -ge "$MAX_ITERATIONS" ]; then
    break
  fi
  echo "  ── sleeping ${INTERVAL}s before the next pass ──"
  sleep "$INTERVAL"
done

echo "reconcile-pr-queue: done"