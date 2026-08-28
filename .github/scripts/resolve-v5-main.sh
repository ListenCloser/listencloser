#!/usr/bin/env bash
set -euo pipefail

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git fetch origin main

set +e
git merge origin/main --no-edit
status=$?
set -e

if [ "$status" -ne 0 ]; then
  unresolved="$(git diff --name-only --diff-filter=U)"
  if [ "$unresolved" != "lib/representations.tsx" ]; then
    echo "Unexpected conflicts: $unresolved"
    exit 1
  fi

  git checkout --theirs lib/representations.tsx

  python3 - <<'PY'
from pathlib import Path

p = Path("lib/representations.tsx")
s = p.read_text()

old = '''  const { transport, seek } = useTransport();
  const entry = workspace.representations.find((item) => item.kind === "score");
  const measureStarts = entry?.measureStarts ?? [];
  const scoreDuration = entry?.audioUrl ? transport.duration : null;'''
new = '''  const { transport, seek, setActiveSource } = useTransport();
  const entry = workspace.representations.find((item) => item.kind === "score");
  const measureStarts = entry?.measureStarts ?? [];
  const scoreSource = transport.sources.find((source) => source.role === "score") ?? null;
  const finalMeasureSpan = measureStarts.length > 1
    ? measureStarts[measureStarts.length - 1] - measureStarts[measureStarts.length - 2]
    : 2;
  const scoreDuration = measureStarts.length > 0
    ? Math.max(transport.duration || 0, measureStarts[measureStarts.length - 1] + Math.max(finalMeasureSpan, 0.25))
    : (transport.duration || null);'''
if old not in s:
    raise SystemExit("score setup not found")
s = s.replace(old, new, 1)

old = '''    <div className="representation-body">
      <SheetMusic
        musicXml={entry?.musicxml ?? ""}'''
new = '''    <div className="representation-body">
      <div className="score-playback-strip">
        {scoreSource ? (
          transport.activeSource?.role === "score" ? (
            <span className="score-playback-state">Hearing score</span>
          ) : (
            <button type="button" className="score-playback-action" onClick={() => setActiveSource(scoreSource)}>Hear score</button>
          )
        ) : (
          <span className="score-playback-state score-playback-state-muted">Notation audio is unavailable for this saved version.</span>
        )}
      </div>
      <SheetMusic
        musicXml={entry?.musicxml ?? ""}'''
if old not in s:
    raise SystemExit("score render insertion not found")
s = s.replace(old, new, 1)

old = '''        isScoreActive={active && transport.activeSource?.role === "score"}
        hasScorePlayback={transport.sources.some((source) => source.role === "score")}'''
new = '''        isScoreActive={active}
        hasScorePlayback={Boolean(scoreSource)}'''
if old not in s:
    raise SystemExit("score playback props not found")
s = s.replace(old, new, 1)

p.write_text(s)
PY

  git add lib/representations.tsx
fi

# One-shot support files must not survive in the PR diff.
git rm .github/scripts/resolve-v5-main.sh .github/workflows/resolve-v5-main-v3.yml
git add -A
git diff --cached --check

git commit --no-edit || git commit -m "merge: reconcile V5 with current main"
git push origin HEAD:design/v5-visual-language-cleanup
