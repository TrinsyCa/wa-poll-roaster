#!/bin/bash
# Ship the current site data: commit on develop, merge into main, push both (main deploys).
# Does nothing when only the "updated" timestamp changed. Never touches other files.
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$REPO"
[ "$(git rev-parse --abbrev-ref HEAD)" = develop ] || { echo "publish runs from develop"; exit 1; }

strip() { python3 -c 'import json,sys; d=json.load(sys.stdin); d.pop("updated",None); print(json.dumps(d,sort_keys=True))'; }
changed=0
if ! git diff --quiet HEAD -- site/a || [ -n "$(git ls-files --others --exclude-standard site/a)" ]; then changed=1; fi
if [ "$(git show HEAD:site/data.json 2>/dev/null | strip)" != "$(strip < site/data.json)" ]; then changed=1; fi
[ "$changed" = 1 ] || { echo "no vote changes, nothing to publish"; exit 0; }

voted=$(python3 -c 'import json; d=json.load(open("site/data.json")); print(f"{d[\"voted\"]}/{d[\"total\"]}")')
stamp=$(date +%H:%M)
git add site/data.json site/a
git commit -q -m "chore(data): oy durumu $voted ($stamp)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push -q origin develop
# main only carries merge commits; build the merge without leaving develop
git fetch -q origin main
tree=$(git merge-tree --write-tree origin/main develop)
sha=$(git commit-tree "$tree" -p origin/main -p develop -m "Merge develop: oy durumu $voted ($stamp)")
git push -q origin "$sha:refs/heads/main"
echo "published $voted at $stamp"
