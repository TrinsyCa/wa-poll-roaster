#!/bin/bash
# One refresh: re-read the poll's voters in WhatsApp Desktop, resolve new voters the lists cannot
# match (member search), rebuild site/data.json, then publish (tools/publish.sh) unless NO_PUBLISH=1.
# The UI scripts move the mouse inside WhatsApp Desktop for about 20 seconds.
set -uo pipefail
source "$(dirname "$0")/env.sh"
cd "$REPO"

"$PY" "$(win windows/refresh_votes.py)" "$(win "$DUMP")\\voters.new.jsonl" || { echo "refresh_votes failed, keeping the last data"; exit 1; }
# votes never disappear mid-poll: a shorter dump means the read was cut short
new=$(wc -l < "$DUMP/voters.new.jsonl"); old=$(wc -l < "$DUMP/voters.jsonl" 2>/dev/null || echo 0)
if [ "$new" -lt "$old" ]; then echo "new dump has $new rows, last had $old: ignored"; exit 1; fi
mv "$DUMP/voters.new.jsonl" "$DUMP/voters.jsonl"

rm -f "$DUMP/q_unresolved.json"
python3 tools/build_data.py "$DUMP" site --closes "$CLOSES"
if [ -s "$DUMP/q_unresolved.json" ]; then
  "$PY" "$(win windows/search_members.py)" "$(win "$DUMP")\\q_unresolved.json" "$(win "$DUMP")\\r_new.json" open
  python3 - "$DUMP" <<'PY'
import json, sys, os
d = sys.argv[1]
path = os.path.join(d, 'r_unmatched.json')
old = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
new = json.load(open(os.path.join(d, 'r_new.json'), encoding='utf-8'))
old.update(new)
json.dump(old, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('resolved by member search:', {q: (v if isinstance(v, list) else v.get('rows')) for q, v in new.items()})
PY
  python3 tools/build_data.py "$DUMP" site --closes "$CLOSES"
fi
cp -n "$DUMP"/a/*.webp site/a/ 2>/dev/null || true
[ "${NO_PUBLISH:-0}" = 1 ] || tools/publish.sh
echo "refreshed at $(date +%H:%M:%S)"
