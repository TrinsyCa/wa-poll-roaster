"""Dump every row of a scrollable WhatsApp Desktop list via UI Automation (comtypes) to JSON lines.

usage: dump_list.py <minX> <maxX> <out.jsonl> [hwnd|0] [wheels per step] [wheel y]
(minX = maxX = 0 reads the open "Search members" list.)
Rows are the ListItems whose bounding-box centre X lies in [minX, maxX]; the list is scrolled
with the mouse wheel at ((minX+maxX)/2, wheel y).
"""
import sys, json, time, ctypes
import comtypes.client
comtypes.client.GetModule('UIAutomationCore.dll')
from comtypes.gen import UIAutomationClient as U

min_x, max_x, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
hwnd = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4] != '0' else ctypes.windll.user32.FindWindowW(None, 'WhatsApp')
wheels = int(sys.argv[5]) if len(sys.argv) > 5 else 7
wx, wy = (min_x + max_x) // 2, int(sys.argv[6]) if len(sys.argv) > 6 else 800
uia = comtypes.client.CreateObject(U.CUIAutomation._reg_clsid_, interface=U.IUIAutomation)
win = uia.ElementFromHandle(hwnd)
if min_x == 0 and max_x == 0:
    # 0 0: take the columns of the open "Search members" list
    box = win.FindFirst(U.TreeScope_Descendants, uia.CreatePropertyCondition(U.UIA_NamePropertyId, 'Search contacts'))
    if not box:
        print('open the member list first'); sys.exit(2)
    br = box.CurrentBoundingRectangle
    min_x, max_x = br.left - 40, br.right + 40
    wx, wy = (min_x + max_x) // 2, br.bottom + 400
li_cond = uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_ListItemControlTypeId)
true_cond = uia.CreateTrueCondition()

def arr(a):
    return [a.GetElement(i) for i in range(a.Length)]

def wheel(n):
    ctypes.windll.user32.SetCursorPos(wx, wy)
    for _ in range(abs(n)):
        ctypes.windll.user32.mouse_event(0x0800, 0, 0, -120 if n > 0 else 120, 0)
        time.sleep(0.02)

wheel(-300); time.sleep(0.8)  # back to the top
seen, rows, idle = set(), [], 0
for loop in range(400):
    new = 0
    for li in arr(win.FindAll(U.TreeScope_Descendants, li_cond)):
        r = li.CurrentBoundingRectangle
        if not (min_x <= (r.left + r.right) / 2 <= max_x):
            continue
        n = li.CurrentName
        if not n or n in seen:
            continue
        seen.add(n); new += 1
        kids = [[k.CurrentLocalizedControlType, k.CurrentName] for k in arr(li.FindAll(U.TreeScope_Descendants, true_cond)) if k.CurrentName]
        rows.append({'name': n, 'kids': kids})
    idle = 0 if new else idle + 1
    if idle >= 4:
        break
    wheel(wheels)
    time.sleep(0.5)
with open(out, 'w', encoding='utf-8') as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + '\n')
print(f'rows={len(rows)} loops={loop}')
