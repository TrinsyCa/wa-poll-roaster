"""Type each query into WhatsApp's "Search members" box and record the member rows it returns.

usage: search_members.py <queries.json> <out.json> [keep] [open]   (keep = leave the last query in the box, open = open the member list first)
Typing only happens while the focused element is the "Search contacts" edit box; otherwise the
script stops, so nothing can land in a chat's message box.
"""
import sys, json, time, ctypes
from ctypes import wintypes
import comtypes.client
comtypes.client.GetModule('UIAutomationCore.dll')
from comtypes.gen import UIAutomationClient as U

queries = json.load(open(sys.argv[1], encoding='utf-8'))
import msvcrt, os
_lock = open(os.path.join(os.path.dirname(os.path.abspath(sys.argv[2])), 'ui.lock'), 'w')
try:
    msvcrt.locking(_lock.fileno(), msvcrt.LK_NBLCK, 1)  # one UI script at a time
except OSError:
    print('another UI script is running, exiting'); sys.exit(4)
uia = comtypes.client.CreateObject(U.CUIAutomation._reg_clsid_, interface=U.IUIAutomation)
win = uia.ElementFromHandle(ctypes.windll.user32.FindWindowW(None, 'WhatsApp'))

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]
class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT), ('pad', ctypes.c_byte * 32)]
    _anonymous_ = ('u',)
    _fields_ = [('type', wintypes.DWORD), ('u', _U)]

def send(vk=0, scan=0, flags=0):
    i = INPUT(type=1); i.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    ctypes.windll.user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(i))

def type_text(s):
    b = s.encode('utf-16-le')
    for i in range(0, len(b), 2):  # one UTF-16 unit at a time, so astral characters go as surrogate pairs
        u = int.from_bytes(b[i:i + 2], 'little')
        send(scan=u, flags=0x0004); send(scan=u, flags=0x0004 | 0x0002)
        time.sleep(0.01)

def clear():
    send(0x11); send(0x41); send(0x41, flags=2); send(0x11, flags=2)  # ctrl+a
    send(0x08); send(0x08, flags=2)  # backspace

def search_box():
    c = uia.CreateAndCondition(uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_EditControlTypeId),
                               uia.CreatePropertyCondition(U.UIA_NamePropertyId, 'Search contacts'))
    return win.FindFirst(U.TreeScope_Descendants, c)

def is_box(e):
    return e is not None and e.CurrentName == 'Search contacts' and e.CurrentControlType == U.UIA_EditControlTypeId

def fg_title():
    b = ctypes.create_unicode_buffer(256)
    ctypes.windll.user32.GetWindowTextW(ctypes.windll.user32.GetForegroundWindow(), b, 256)
    return b.value

def box_value(box):
    try:
        return box.GetCurrentPattern(U.UIA_ValuePatternId).QueryInterface(U.IUIAutomationValuePattern).CurrentValue
    except Exception:
        return None

def focused_is_box():
    # WebView2 reports the host pane as focused, so check the foreground window instead
    return 'WhatsApp' in fg_title()

def click_box(box):
    r = box.CurrentBoundingRectangle
    x, y = (r.left + r.right) // 2, (r.top + r.bottom) // 2
    pt = U.tagPOINT(x, y)
    hit = uia.ElementFromPoint(pt)
    hr = hit.CurrentBoundingRectangle
    inside = r.left <= hr.left and hr.right <= r.right and r.top <= hr.top and hr.bottom <= r.bottom
    # the hit test sometimes only resolves to the WebView document; the box value check after typing still guards us
    coarse = hit.CurrentControlType == U.UIA_DocumentControlTypeId and 'WhatsApp' in (hit.CurrentName or '')
    if not (is_box(hit) or inside or coarse):
        print('hit:', hit.CurrentLocalizedControlType, repr(hit.CurrentName), hr.left, hr.top, hr.right, hr.bottom, '| box:', r.left, r.top, r.right, r.bottom)
        return False
    ctypes.windll.user32.SetCursorPos(x, y)
    ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0); ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.3)
    return True

def rows():
    c = uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_ListItemControlTypeId)
    a = win.FindAll(U.TreeScope_Descendants, c)
    out = []
    for i in range(a.Length):
        e = a.GetElement(i); r = e.CurrentBoundingRectangle
        n = e.CurrentName
        if 1000 <= (r.left + r.right) / 2 <= 1600 and n and len(n.strip()) > 2 and n not in out:
            out.append(n)
    return out

def open_list():
    """From whatever the side panel shows, get to the "Search members" list."""
    def find_name(prefix, ctype=None):
        c = uia.CreatePropertyConditionEx(U.UIA_NamePropertyId, prefix, 2)
        if ctype is not None:
            c = uia.CreateAndCondition(c, uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, ctype))
        d = win.FindFirst(U.TreeScope_Descendants, uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_DocumentControlTypeId))
        a = d.FindAll(U.TreeScope_Descendants, c)
        return [a.GetElement(i) for i in range(a.Length) if (a.GetElement(i).CurrentName or '').startswith(prefix)]
    def click_el(e):
        r = e.CurrentBoundingRectangle
        x, y = (r.left + r.right) // 2, (r.top + r.bottom) // 2
        ctypes.windll.user32.SetCursorPos(x, y)
        ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0); ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
    wr = win.CurrentBoundingRectangle
    for _ in range(5):
        if search_box():
            return True
        va = [e for e in find_name('View all') if wr.top + 60 < (e.CurrentBoundingRectangle.top + e.CurrentBoundingRectangle.bottom) // 2 < wr.bottom - 20]
        if va:
            click_el(va[0]); time.sleep(1.2); continue
        if find_name('Group info'):
            ctypes.windll.user32.SetCursorPos(wr.right - 280, (wr.top + wr.bottom) // 2)
            for _ in range(25):
                ctypes.windll.user32.mouse_event(0x0800, 0, 0, -120, 0); time.sleep(0.02)
            time.sleep(0.7); continue
        hdr = [e for e in find_name('Vip Erdinç Turizm', U.UIA_ButtonControlTypeId) if e.CurrentBoundingRectangle.top < wr.top + 130]
        if hdr:
            click_el(hdr[0]); time.sleep(1.2); continue
        return False
    return bool(search_box())


if 'open' in sys.argv[3:] and not search_box():
    open_list()
box = search_box()
if not box:
    print('search box not found'); sys.exit(1)
if not click_box(box):
    print('search box not under the cursor point'); sys.exit(1)
results = {}
for q in queries:
    if not focused_is_box():
        if not click_box(box) or not focused_is_box():
            f = uia.GetFocusedElement(); print('focus lost, stopping at', q, '| focused:', f.CurrentLocalizedControlType, repr(f.CurrentName), '| fg:', fg_title()); break
    clear(); time.sleep(0.2)
    if not focused_is_box():
        print('focus lost, stopping at', q); break
    type_text(q); time.sleep(1.0)
    v = box_value(box)
    if v != q:
        print('typed text did not reach the search box, stopping at', q, '| box value:', repr(v))
        if not (v or '').strip():  # nothing reached the box: the keys went somewhere else
            break
        results[q] = {'value': v, 'rows': rows()}
        continue
    results[q] = rows()
if focused_is_box() and 'keep' not in sys.argv[3:]:
    clear()
json.dump(results, open(sys.argv[2], 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('done', len(results))
