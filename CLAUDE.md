# CLAUDE.md

Operating guide for AI agents (Claude Code and others) working on this repository. Read
README.md first for what the system is; this file is about how to run and change it safely.

## The job in one paragraph

The owner runs the *VIP Erdinç Turizm* WhatsApp group (~580 drivers) from a WhatsApp Desktop
account that is a group admin. A pinned poll, "GRUPTA AKTİF MİSİN?", decides who stays: members who
have not voted when it closes are removed. This repo publishes a lookup page
(https://viperdinc.cooltravelistanbul.com) so every driver can check their own status before the
deadline. Data is read from WhatsApp Desktop with Windows UI Automation and shipped as static files.

## Hard rules

1. **Never remove anyone from the group, and never click "Remove".** The scripts here only read.
   Removing members happens after the poll closes, only on the owner's explicit go-ahead, with the
   final non-voter list shown to them first, in small batches.
2. **Never send anything to WhatsApp.** No script presses Enter. Type only after verifying the
   target is the "Search contacts" box, and read the value back (see `windows/search_members.py`).
   If text ever lands in a chat's message box, clear it with Ctrl+A, Backspace and tell the owner.
3. **The computer is shared with the owner.** UI scripts move the real mouse and type real keys.
   Before any UI run, say how long it will take and ask the owner not to type. If the owner is
   using the machine (another window in front, typing in the Claude window), stop and wait.
   The Claude desktop window can jump in front of WhatsApp; keep it on a side of the screen that
   does not overlap WhatsApp.
4. **One UI script at a time.** All `windows/*.py` take `ui.lock` in the dump folder. Do not launch
   them through a tool that retries on timeout (the Windows-MCP PowerShell tool did, and two copies
   fought over the mouse): run them from WSL directly, `"$PY" "$(wslpath -w windows/x.py)" ...`,
   in the background when they are long.
5. **Personal data.** `site/data.json` and `site/a/` hold names, numbers and photos. This repo must
   stay private, the raw dumps stay in `%LOCALAPPDATA%\Temp\cti-wa` (outside git), and nothing from
   them is pasted into issues, PRs or chats beyond what the task needs.
6. **No em dash (U+2014) anywhere** in code, docs, commits or the page. Use "-" or ordinary punctuation.

## How the data is read (WhatsApp Desktop facts that cost time to learn)

- The window title is exactly `WhatsApp`; scripts find it with `FindWindowW(None, 'WhatsApp')`.
- It is a WebView2 app whose UIA tree repeats the document ~79 times. Always query one copy
  (`FindFirst` the Document control) and snapshot it with a cache request
  (`FindAllBuildCache` + Name/ControlType/BoundingRectangle). Per-element property reads across the
  whole window are what made the first version take a minute per member.
- Headings are exposed as text with LocalizedControlType `heading`.
- Elements vanish while WhatsApp re-renders; reading a stale one raises
  `COMError -2147220991`. Catch it per element and carry on.
- Avatars in the member list are unnamed ~61 px squares, present only in the **raw** view
  (`cache.TreeFilter = uia.RawViewCondition`).
- Contact info shows: saved name (big font, may wrap), then the profile's own name (smaller font,
  only for some accounts, mostly business ones), then "About and phone number". Username-only
  accounts hide their number.
- The Contact info photo animates in; crop avatars from the static member list (`photos.py`).
- The poll voter list names people differently from the member list (often `~ profile name +phone`
  vs the saved contact name). `tools/build_data.py` matches by phone, `@username`, exact name, then
  the stored member-search answers in `r_unmatched.json`; `refresh.sh` runs member searches for new
  unmatched voters. A voter matching several members marks all of them `check`.
- Group info layout: header click opens it; "View all (N more)" opens the "Search members" dialog;
  a member row click opens a menu with Make admin / **Remove** / Contact info / Verify / Message.

## Day-to-day commands (from WSL, repo root)

```bash
tools/refresh.sh                 # ~20 s of UI time: votes -> data.json -> publish
NO_PUBLISH=1 tools/refresh.sh    # same without deploying
tools/collect.sh                 # ~1 h, full re-collection (members, contact info, avatars)
python3 tools/build_data.py "$CTI_DUMP" site --closes 2026-10-25T22:23:00+03:00   # rebuild only
python3 -m http.server -d site 8765                                               # preview
```

Settings (Windows Python path, dump folder, poll close time) live in `tools/env.sh`.
Check a page change headless with Playwright (`~/.cti-shots/node_modules/playwright`) at 390x844
in both color schemes before shipping.

## Shipping (two branches)

- Work on `develop`. Commit messages are Turkish ASCII conventional commits
  (`feat(site): ...`, `chore(data): ...`).
- `main` carries only merge commits: `git merge --no-ff develop -m "Merge develop: <ozet>"`, or,
  without leaving develop, `git merge-tree --write-tree origin/main develop` + `git commit-tree`
  (that is what `tools/publish.sh` does). Pushing `main` deploys via `.github/workflows/deploy.yml`.
- `[no-deploy]` in the head commit message skips the deploy.
- Ship code changes only when the owner asks. `tools/publish.sh` (data only) is pre-approved while
  the poll is open, because keeping statuses current is the point of the site.
- There is no `gh` CLI on this machine. Watch a deploy by fetching
  `https://viperdinc.cooltravelistanbul.com/data.json` and comparing `updated`.

## When the poll closes

1. Run a last `tools/refresh.sh`.
2. Show the owner the final `not_voted` list (and the `check` ones separately). Do nothing else.
3. Removal, if the owner asks for it, is a separate, supervised job: small batches with pauses,
   each removal confirmed in WhatsApp's own dialog, admins and `check` members never included.
4. Afterwards, suggest taking the site down (empty `site/` or a "poll closed" page).
