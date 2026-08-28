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
  unresolved="$(git diff --name-only --diff-filter=U | sort)"
  echo "Unresolved paths:"
  echo "$unresolved"

  while IFS= read -r path; do
    case "$path" in
      app/layout.tsx|components/workspace/RepresentationStack.tsx|lib/representations.tsx) ;;
      *) echo "Unexpected conflict: $path"; exit 1 ;;
    esac
  done <<< "$unresolved"

  # V6 does not intentionally change the representation registry. The conflict
  # is inherited from its pre-merge V5 base, so main is authoritative here.
  if grep -qx 'lib/representations.tsx' <<< "$unresolved"; then
    git checkout --theirs lib/representations.tsx
    git add lib/representations.tsx
  fi

  # Main owns mounted-view caching; V6 only replaces the tab interaction shell.
  if grep -qx 'components/workspace/RepresentationStack.tsx' <<< "$unresolved"; then
    git checkout --theirs components/workspace/RepresentationStack.tsx
    python3 - <<'PY'
from pathlib import Path

p = Path("components/workspace/RepresentationStack.tsx")
s = p.read_text()

anchor = 'import { availableRepresentations, type RepresentationId } from "@/lib/representations";\n'
if anchor not in s:
    raise SystemExit("representation import anchor not found")
if 'import TabStrip from "@/components/ui/TabStrip";' not in s:
    s = s.replace(anchor, 'import TabStrip from "@/components/ui/TabStrip";\n' + anchor, 1)

old = '''        <nav className="piece-view-tabs piece-view-tabs-v3" role="tablist" aria-label="Music representation">
          {available.map((def) => (
            <button
              key={def.id}
              type="button"
              role="tab"
              aria-selected={activeView === def.id}
              className={activeView === def.id ? "active" : ""}
              onClick={() => setActiveRepresentation(def.id)}
            >
              {def.title}
            </button>
          ))}
        </nav>'''
new = '''        <TabStrip
          className="piece-view-tabs piece-view-tabs-v3"
          label="Music representation"
          items={available.map((def) => ({ id: def.id, label: def.title }))}
          value={activeView}
          onChange={setActiveRepresentation}
        />'''
if old not in s:
    raise SystemExit("representation tab block not found")
s = s.replace(old, new, 1)
p.write_text(s)
PY
    git add components/workspace/RepresentationStack.tsx
  fi

  if grep -qx 'app/layout.tsx' <<< "$unresolved"; then
    git checkout --theirs app/layout.tsx
    python3 - <<'PY'
from pathlib import Path
p = Path("app/layout.tsx")
s = p.read_text()
needle = 'import "./visual-language-v5.css";\n'
if needle not in s:
    raise SystemExit("V5 visual import not found")
if 'import "./visual-language-v6.css";' not in s:
    s = s.replace(needle, needle + 'import "./visual-language-v6.css";\n', 1)
p.write_text(s)
PY
    git add app/layout.tsx
  fi
fi

git rm .github/scripts/resolve-v6-main.sh .github/workflows/resolve-v6-main.yml
git add -A
git diff --cached --check
git commit --no-edit || git commit -m "merge: reconcile V6 with merged V5 baseline"
git push origin HEAD:design/v6-reference-led-system
