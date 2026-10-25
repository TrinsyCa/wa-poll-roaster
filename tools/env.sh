# Shared settings for the tools/*.sh scripts. Override any of them in the environment.
# Windows Python that has comtypes + Pillow (the Windows-MCP extension's venv has both).
PY="${CTI_WIN_PYTHON:-/mnt/c/Users/User/AppData/Local/Claude-Data/claude_pzs8sxrjxfjjc/Claude Extensions/ant.dir.cursortouch.windows-mcp/.venv/Scripts/python.exe}"
# Raw WhatsApp dumps (members.jsonl, voters.jsonl, profiles.json, photos.json, avatars). Never committed.
DUMP="${CTI_DUMP:-/mnt/c/Users/User/AppData/Local/Temp/cti-wa}"
# When the poll closes (ISO 8601 with offset); drives the countdown on the page.
CLOSES="${CTI_CLOSES:-2026-10-25T22:23:00+03:00}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONIOENCODING=utf-8
win() { wslpath -w "$1"; }
