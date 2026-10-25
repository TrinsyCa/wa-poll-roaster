#!/bin/bash
# Full collection, needed once (or after many members joined or left): the member list, every
# member's Contact info (own profile name + number), then every avatar. Takes about an hour,
# during which the computer must not be used. Resumable: rerun to continue.
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$REPO"
mkdir -p "$DUMP/a"
echo '[]' > "$DUMP/q_none.json"
D="$(win "$DUMP")"

"$PY" "$(win windows/search_members.py)" "$D\\q_none.json" "$D\\r_none.json" keep open   # opens "Search members"
"$PY" "$(win windows/dump_list.py)" 0 0 "$D\\members.jsonl" 0 7
echo "members: $(grep -c . "$DUMP/members.jsonl") rows (A-Z headers included)"
"$PY" "$(win windows/collect_profiles.py)" "$D\\members.jsonl" "$D\\profiles.json" "$D\\a"
tail -1 "$DUMP/collect.log"
"$PY" "$(win windows/search_members.py)" "$D\\q_none.json" "$D\\r_none.json" keep open
"$PY" "$(win windows/photos.py)" "$D\\photos.json" "$D\\a"
rm -f site/a/*.webp && cp "$DUMP"/a/*.webp site/a/
NO_PUBLISH=1 tools/refresh.sh
