#!/usr/bin/env bash
set -euo pipefail

PROGRAM="agent-worktree"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/agent-worktree.sh create <task> [slug]
  bash scripts/agent-worktree.sh status
  bash scripts/agent-worktree.sh overlap <path> [path ...]
  bash scripts/agent-worktree.sh cleanup <lane> [--abandon]

Examples:
  bash scripts/agent-worktree.sh create 290 parallel-orchestration
  bash scripts/agent-worktree.sh overlap lib/ backend/domain/job_worker.py
  bash scripts/agent-worktree.sh cleanup 290-parallel-orchestration
EOF
}

die() {
  printf '%s: %s\n' "$PROGRAM" "$*" >&2
  exit 1
}

have() {
  command -v "$1" >/dev/null 2>&1
}

git_primary_root() {
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "run this inside the repository"
  git worktree list --porcelain |
    awk '/^worktree / { sub(/^worktree /, ""); print; exit }'
}

slugify() {
  printf '%s' "$1" |
    tr '[:upper:]' '[:lower:]' |
    tr -cs '[:alnum:]' '-' |
    sed 's/^-//; s/-$//' |
    cut -c1-56
}

repo_slug() {
  local root="$1"
  local remote
  remote="$(git -C "$root" remote get-url origin 2>/dev/null || true)"
  case "$remote" in
    git@github.com:*)
      remote="${remote#git@github.com:}"
      ;;
    https://github.com/*)
      remote="${remote#https://github.com/}"
      ;;
    ssh://git@github.com/*)
      remote="${remote#ssh://git@github.com/}"
      ;;
    *)
      return 1
      ;;
  esac
  remote="${remote%.git}"
  [[ "$remote" == */* ]] || return 1
  printf '%s\n' "$remote"
}

metadata_dir() {
  printf '%s/.worktrees/.agent-meta\n' "$1"
}

worktree_root() {
  local root="$1"
  printf '%s\n' "${HELLO_AI_WORKTREE_ROOT:-$root/.worktrees}"
}

create_lane() {
  [[ $# -ge 1 && $# -le 2 ]] || die "create expects <task> [slug]"
  local task="$1"
  local requested_slug="${2:-}"
  local root
  root="$(git_primary_root)"

  local slug="$requested_slug"
  local repo=""
  if [[ -z "$slug" && "$task" =~ ^[0-9]+$ ]] && have gh; then
    repo="$(repo_slug "$root" || true)"
    if [[ -n "$repo" ]]; then
      slug="$(gh issue view "$task" --repo "$repo" --json title --jq '.title' 2>/dev/null || true)"
    fi
  fi
  [[ -n "$slug" ]] || slug="$task"
  slug="$(slugify "$slug")"
  [[ -n "$slug" ]] || die "task/slug does not contain a usable branch name"

  local lane
  if [[ "$task" =~ ^[0-9]+$ ]]; then
    lane="${task}-${slug}"
  else
    lane="$slug"
  fi
  local branch="agent/$lane"
  local wt_root
  wt_root="$(worktree_root "$root")"
  local path="$wt_root/$lane"

  [[ ! -e "$path" ]] || die "worktree path already exists: $path"
  if git -C "$root" show-ref --verify --quiet "refs/heads/$branch"; then
    die "local branch already exists: $branch"
  fi

  printf 'Fetching protected baseline origin/main...\n'
  git -C "$root" fetch --prune origin main

  # Fetching only main does not populate every refs/remotes/origin/* entry. Ask
  # the remote directly so an agent cannot accidentally recreate a lane that
  # exists on GitHub but has never been fetched into this checkout. Exit code 2
  # means "no matching ref"; transport/auth failures must fail closed instead
  # of being mistaken for branch absence.
  local remote_check_status=0
  if git -C "$root" ls-remote --exit-code --heads origin "refs/heads/$branch" >/dev/null 2>&1; then
    die "remote branch already exists: $branch"
  else
    remote_check_status=$?
    if [[ "$remote_check_status" -ne 2 ]]; then
      die "could not verify remote branch uniqueness for $branch (git ls-remote exit $remote_check_status)"
    fi
  fi

  mkdir -p "$wt_root"
  git -C "$root" worktree add -b "$branch" "$path" origin/main

  local base_sha
  base_sha="$(git -C "$path" rev-parse HEAD)"
  local meta_dir
  meta_dir="$(metadata_dir "$root")"
  mkdir -p "$meta_dir"
  {
    printf 'lane\t%s\n' "$lane"
    printf 'task\t%s\n' "$task"
    printf 'branch\t%s\n' "$branch"
    printf 'path\t%s\n' "$path"
    printf 'base_sha\t%s\n' "$base_sha"
    printf 'created_utc\t%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  } >"$meta_dir/$lane.tsv"

  printf '\nCreated isolated lane:\n'
  printf '  lane:   %s\n' "$lane"
  printf '  branch: %s\n' "$branch"
  printf '  path:   %s\n' "$path"
  printf '  base:   %s\n' "$base_sha"
  if [[ "$task" =~ ^[0-9]+$ ]]; then
    printf '\nBefore editing, read issue #%s and check likely ownership paths:\n' "$task"
  else
    printf '\nBefore editing, check likely ownership paths:\n'
  fi
  printf '  bash scripts/agent-worktree.sh overlap <path> [path ...]\n'
}

status_lanes() {
  local root
  root="$(git_primary_root)"
  printf 'Registered Git worktrees:\n'
  git -C "$root" worktree list

  local meta_dir
  meta_dir="$(metadata_dir "$root")"
  if [[ -d "$meta_dir" ]]; then
    printf '\nAgent lanes:\n'
    local meta
    shopt -s nullglob
    for meta in "$meta_dir"/*.tsv; do
      local lane branch path base
      lane="$(awk -F '\t' '$1=="lane" {print $2}' "$meta")"
      branch="$(awk -F '\t' '$1=="branch" {print $2}' "$meta")"
      path="$(awk -F '\t' '$1=="path" {print $2}' "$meta")"
      base="$(awk -F '\t' '$1=="base_sha" {print $2}' "$meta")"
      local dirty="missing"
      if [[ -d "$path" ]]; then
        if [[ -n "$(git -C "$path" status --porcelain)" ]]; then dirty="dirty"; else dirty="clean"; fi
      fi
      printf '  %-32s %-8s %s (base %s)\n' "$branch" "$dirty" "$path" "${base:0:12}"
    done
    shopt -u nullglob
  fi

  if have gh; then
    local repo
    repo="$(repo_slug "$root" || true)"
    if [[ -n "$repo" ]]; then
      printf '\nOpen PRs from agent/* branches:\n'
      local prs
      prs="$(gh pr list --repo "$repo" --state open --limit 500 \
        --json number,headRefName,title,url \
        --jq '.[] | select(.headRefName | startswith("agent/")) | "#\(.number)\t\(.headRefName)\t\(.title)\t\(.url)"' \
        2>/dev/null || true)"
      if [[ -n "$prs" ]]; then printf '%s\n' "$prs"; else printf '  none\n'; fi
    fi
  fi
}

paths_overlap() {
  [[ $# -ge 1 ]] || die "overlap expects at least one repository path"
  have gh || die "overlap requires the GitHub CLI (gh)"

  local root
  root="$(git_primary_root)"
  local repo
  repo="$(repo_slug "$root" || true)"
  [[ -n "$repo" ]] || die "origin is not a supported GitHub remote"

  local -a targets=()
  local raw target
  for raw in "$@"; do
    target="${raw#./}"
    target="${target%/}"
    [[ -n "$target" ]] || die "empty path is not a valid overlap target"
    targets+=("$target")
  done

  local rows
  rows="$(gh pr list --repo "$repo" --state open --limit 500 \
    --json number,headRefName,title,url \
    --jq '.[] | [.number, .headRefName, .title, .url] | @tsv')"

  local found=0
  local number branch title url
  while IFS=$'\t' read -r number branch title url; do
    [[ -n "$number" ]] || continue
    local files
    if ! files="$(gh pr view "$number" --repo "$repo" --json files --jq '.files[].path' 2>/dev/null)"; then
      die "could not read changed files for open PR #$number; overlap result would be incomplete"
    fi
    [[ -n "$files" ]] || continue

    local -a hits=()
    local file
    while IFS= read -r file; do
      [[ -n "$file" ]] || continue
      for target in "${targets[@]}"; do
        if [[ "$file" == "$target" || "$file" == "$target/"* ]]; then
          hits+=("$file")
          break
        fi
      done
    done <<<"$files"

    if ((${#hits[@]})); then
      found=1
      printf '#%s %s [%s]\n' "$number" "$title" "$branch"
      printf '  %s\n' "$url"
      printf '  %s\n' "${hits[@]}"
    fi
  done <<<"$rows"

  if ((found == 0)); then
    printf 'No open PR currently edits the requested paths.\n'
  fi
}

cleanup_lane() {
  [[ $# -ge 1 && $# -le 2 ]] || die "cleanup expects <lane> [--abandon]"
  local lane="$1"
  local abandon=0
  if [[ "${2:-}" == "--abandon" ]]; then
    abandon=1
  elif [[ $# -eq 2 ]]; then
    die "unknown cleanup flag: $2"
  fi

  local root
  root="$(git_primary_root)"
  local meta_file
  meta_file="$(metadata_dir "$root")/$lane.tsv"
  local path=""
  if [[ -f "$meta_file" ]]; then
    path="$(awk -F '\t' '$1=="path" {print $2}' "$meta_file")"
  fi
  if [[ -z "$path" ]]; then
    local wt_root
    wt_root="$(worktree_root "$root")"
    path="$wt_root/$lane"
  fi
  [[ -d "$path" ]] || die "worktree does not exist: $path"

  # Metadata is local state, not authority. Confirm the resolved path is an
  # actual registered Git worktree before running destructive cleanup.
  local registered=0
  local registered_path
  while IFS= read -r registered_path; do
    if [[ "$registered_path" == "$path" ]]; then
      registered=1
      break
    fi
  done < <(git -C "$root" worktree list --porcelain | awk '/^worktree / { sub(/^worktree /, ""); print }')
  ((registered == 1)) || die "resolved path is not a registered Git worktree: $path"

  local branch
  branch="$(git -C "$path" branch --show-current)"
  [[ -n "$branch" ]] || die "worktree is detached; inspect manually before cleanup"
  [[ -z "$(git -C "$path" status --porcelain)" ]] || die "worktree is dirty; commit/stash/remove changes first"

  local current_head
  current_head="$(git -C "$path" rev-parse HEAD)"
  local repo=""
  local merged_head_proven=0
  if have gh; then
    repo="$(repo_slug "$root" || true)"
    if [[ -n "$repo" ]]; then
      local pr_rows
      pr_rows="$(gh pr list --repo "$repo" --head "$branch" --state all --limit 100 \
        --json number,state,mergedAt \
        --jq '.[] | [.number, .state, (.mergedAt // "")] | @tsv' \
        2>/dev/null || true)"

      local pr_number pr_state merged_at
      while IFS=$'\t' read -r pr_number pr_state merged_at; do
        [[ -n "$pr_number" ]] || continue
        if [[ "$pr_state" == "OPEN" ]]; then
          die "PR #$pr_number is still open; merge or close it before cleanup"
        fi
        if [[ -n "$merged_at" && "$abandon" -ne 1 ]]; then
          local reviewed_head
          reviewed_head="$(gh pr view "$pr_number" --repo "$repo" --json headRefOid --jq '.headRefOid' 2>/dev/null || true)"
          if [[ "$reviewed_head" == "$current_head" ]]; then
            merged_head_proven=1
          fi
        fi
      done <<<"$pr_rows"
    fi
  fi

  if [[ "$abandon" -ne 1 && "$merged_head_proven" -ne 1 ]]; then
    die "current HEAD $current_head is not proven as the reviewed head of a merged PR; pass --abandon only if intentionally discarding the lane"
  fi

  git -C "$root" worktree remove "$path"
  git -C "$root" branch -D "$branch"
  rm -f "$meta_file"
  git -C "$root" worktree prune

  printf 'Removed lane %s (%s).\n' "$lane" "$branch"
  printf 'Remote branch deletion is intentionally manual.\n'
}

main() {
  local command="${1:-}"
  case "$command" in
    create)
      shift
      create_lane "$@"
      ;;
    status)
      shift
      [[ $# -eq 0 ]] || die "status takes no arguments"
      status_lanes
      ;;
    overlap)
      shift
      paths_overlap "$@"
      ;;
    cleanup)
      shift
      cleanup_lane "$@"
      ;;
    -h|--help|help|"")
      usage
      ;;
    *)
      usage >&2
      die "unknown command: $command"
      ;;
  esac
}

main "$@"
