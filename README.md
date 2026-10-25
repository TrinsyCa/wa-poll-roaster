# VIP Erdinç Turizm: poll lookup

A one-page site at **https://viperdinc.cooltravelistanbul.com** where the drivers in the
*VIP Erdinç Turizm* WhatsApp group (about 580 members) can look themselves up and see whether
they have voted in the pinned poll **"GRUPTA AKTİF MİSİN?"** ("Are you active in the group?").

When the poll closes, members who did not vote are removed from the group. The site gives
every driver a few hours' notice: search your name or phone number, see "Oy verdi" (voted) or
"Oy vermedi" (not voted), and go vote if needed. The list refreshes itself while the poll is open.

## What is on the page

- Every member with their **own WhatsApp profile name** where WhatsApp exposes it (otherwise the
  group admin's saved contact name), full phone number and a 40x40 WebP profile photo.
- Vote status per member, a voted / total counter and a countdown to the poll's close.
- Search by name or number. Turkish letters and fancy Unicode fonts fold to plain letters, and
  `0535 ...`, `+90 535 ...` and `535 ...` all find the same person.
- `site/data.json` is re-fetched every minute, so a driver who votes sees the change without reloading.

## How it works

WhatsApp has no API for polls or for groups the business did not create through the Cloud API
(the Cloud API Groups API caps groups at 8 participants and returns no poll votes). Everything is
therefore read from **WhatsApp Desktop on Windows** through **UI Automation**, the accessibility
interface Windows exposes for every app. Nothing is sent to WhatsApp and no unofficial client
library is used, so the account carries no ban risk beyond normal manual use.

```
WhatsApp Desktop (Windows)
   │  UI Automation (comtypes), mouse wheel, screen crops (Pillow)
   ▼
windows/*.py ───────────► raw dumps in %LOCALAPPDATA%\Temp\cti-wa  (never committed)
   members.jsonl   the group's "Search members" list
   profiles.json   each member's Contact info: own profile name + number
   photos.json     avatars, saved as a/<hash>.webp
   voters.jsonl    the poll's voter list
   │
   ▼
tools/build_data.py ─────► site/data.json   (matching voters to members)
   │
   ▼
tools/publish.sh ────────► publishes the updated site/
```

### Matching voters to members

The poll's voter list and the member list do not name people the same way: the poll often shows
`~ profile name +90 ...` while the member list shows the admin's saved contact name. Voters are
matched to members by phone number, then by `@username`, then by exact name, and anything still
unmatched is looked up with WhatsApp's own member search (by number, or by name). A voter that
fits several members is shown as "Kontrol ediliyor" (being checked) on all of them rather than
guessed.

### Lessons from building it

- WhatsApp Desktop is a WebView2 app. The window exposes its document tree about 79 times over,
  so every query is scoped to one copy of the document and done with a UIA **cache request**
  (one cross-process call per snapshot). That took a member visit from ~60 s to ~5 s.
- Avatars are unnamed boxes that only exist in the **raw** UIA view.
- The Contact info photo animates in, so photos are cropped from the static member list instead.
- Typing is only done after the target box is verified, and the typed value is read back; the
  scripts never press Enter, so nothing can be sent to a chat.

## Repository layout

```
site/                 the published page (index.html, data.json, a/*.webp, logo, .htaccess, robots.txt)
tools/build_data.py   dumps -> site/data.json
tools/refresh.sh      re-read votes, rebuild, publish (about 20 s of UI time)
tools/loop.sh         run refresh.sh every 15 minutes until the poll closes
tools/publish.sh      publish the updated data
tools/collect.sh      full collection: members, contact info, avatars (about an hour)
tools/env.sh          paths and settings shared by the scripts
windows/              UI Automation scripts, run with a Windows Python (comtypes + Pillow)
CLAUDE.md             operating guide for AI agents working on this repo
```

## Running it

Requirements: Windows with WSL, WhatsApp Desktop signed in to a group admin account and open on
the group, and a Windows Python with `comtypes` and `Pillow` (set `CTI_WIN_PYTHON` in
`tools/env.sh` or the environment). Keep the WhatsApp window unobstructed while a script runs and
do not use the keyboard or mouse: the scripts move the mouse inside WhatsApp.

```bash
tools/collect.sh                 # once: members, contact info, avatars, first data.json
tools/refresh.sh                 # every ~15 minutes until the poll closes
NO_PUBLISH=1 tools/refresh.sh    # rebuild locally without publishing
python3 -m http.server -d site 8765   # preview at http://127.0.0.1:8765
```

## Privacy

`site/data.json` lists members' names, phone numbers and photos, and anyone with the URL can read
it. The site is kept out of search engines (`X-Robots-Tag: noindex`, `robots.txt`), and this
repository must stay **private**. Take the site down once the poll is over and the group has been
cleaned up.
