"""Re-read the poll's voter list in WhatsApp Desktop and write voters.jsonl (read-only).

usage: refresh_votes.py <voters.jsonl>

Clicks only: the pinned-message banner (jumps to the poll), "View votes", "See all (...)", and
the panel's close button at the end. Then wheels the voter list and records every row.
"""
import sys, os, json, time, ctypes, msvcrt
import comtypes, comtypes.client
comtypes.client.GetModule('UIAutomationCore.dll')
from comtypes.gen import UIAutomationClient as U

HWND = ctypes.windll.user32.FindWindowW(None, 'WhatsApp') or sys.exit('WhatsApp Desktop window not found')
out_path = sys.argv[1]
_lock = open(os.path.join(os.path.dirname(out_path), 'ui.lock'), 'w')
try:
    msvcrt.locking(_lock.fileno(), msvcrt.LK_NBLCK, 1)
except OSError:
    print('another UI script is running, exiting'); sys.exit(4)
uia = comtypes.client.CreateObject(U.CUIAutomation._reg_clsid_, interface=U.IUIAutomation)
win = uia.ElementFromHandle(HWND)
user32 = ctypes.windll.user32
_cr = uia.CreateCacheRequest()
for _pid in (U.UIA_NamePropertyId, U.UIA_ControlTypePropertyId, U.UIA_BoundingRectanglePropertyId, U.UIA_LocalizedControlTypePropertyId):
    _cr.AddProperty(_pid)


class Node:
    __slots__ = ('e', 'name', 'type', 'loc', 'l', 't', 'r', 'b')


def doc():
    return win.FindFirst(U.TreeScope_Descendants, uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_DocumentControlTypeId))


def snap(root=None):
    a = (root or doc() or win).FindAllBuildCache(U.TreeScope_Descendants, uia.CreateTrueCondition(), _cr)
    out, seen = [], set()
    for i in range(a.Length):
        e = a.GetElement(i)
        try:
            n = Node(); n.e = e; n.name = e.CachedName or ''; n.type = e.CachedControlType; n.loc = e.CachedLocalizedControlType or ''
            r = e.CachedBoundingRectangle; n.l, n.t, n.r, n.b = r.left, r.top, r.right, r.bottom
            k = (n.name, n.type, n.l, n.t, n.r, n.b)
            if n.r > n.l and n.b > n.t and k not in seen:
                seen.add(k); out.append(n)
        except comtypes.COMError:
            continue
    return out


def find(nodes, name, prefix=False, ctype=None):
    return [n for n in nodes if (n.name.startswith(name) if prefix else n.name == name) and (ctype is None or n.type == ctype)]


def center(n):
    return (n.l + n.r) // 2, (n.t + n.b) // 2


def click(n):
    x, y = center(n)
    user32.SetCursorPos(x, y); user32.mouse_event(2, 0, 0, 0, 0); user32.mouse_event(4, 0, 0, 0, 0)


def wait(fn, timeout=4.0):
    t = time.time()
    while time.time() - t < timeout:
        v = fn()
        if v:
            return v
        time.sleep(0.2)
    return None


def fg_ok():
    b = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(user32.GetForegroundWindow(), b, 256)
    return 'WhatsApp' in b.value


def bring_front():
    if fg_ok():
        return True
    user32.keybd_event(0x12, 0, 0, 0); user32.keybd_event(0x12, 0, 2, 0)
    user32.ShowWindow(HWND, 9); user32.SetForegroundWindow(HWND); time.sleep(0.4)
    return fg_ok()


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [('cbSize', ctypes.c_uint), ('dwTime', ctypes.c_uint)]


def idle_seconds():
    li = LASTINPUTINFO(); li.cbSize = ctypes.sizeof(li)
    user32.GetLastInputInfo(ctypes.byref(li))
    return (ctypes.windll.kernel32.GetTickCount() - li.dwTime) / 1000.0


def wait_for_idle(need=20, max_wait=600):
    """The owner works on this machine: start only after `need` seconds without keyboard/mouse input."""
    t = time.time()
    while idle_seconds() < need:
        if time.time() - t > max_wait:
            print(f'owner active for {max_wait}s, round skipped'); sys.exit(5)
        time.sleep(5)


def fail(msg):
    try:
        from PIL import ImageGrab
        ImageGrab.grab(all_screens=True).save(os.path.join(os.path.dirname(out_path), 'refresh_fail.png'))
    except Exception:
        pass
    print(msg); sys.exit(2)


def main():
    wait_for_idle()
    prev_fg = user32.GetForegroundWindow()
    was_min = bool(user32.IsIconic(HWND))
    try:
        run()
    finally:
        # hand the screen back the way it was
        if was_min:
            user32.ShowWindow(HWND, 6)
        if prev_fg and prev_fg != HWND:
            user32.keybd_event(0x12, 0, 0, 0); user32.keybd_event(0x12, 0, 2, 0)
            user32.SetForegroundWindow(prev_fg)


def run():
    if not bring_front():
        print('WhatsApp is not in front, giving up'); sys.exit(2)
    time.sleep(0.6)
    wr = win.CurrentBoundingRectangle
    nodes = snap()
    if find(nodes, 'Search contacts', ctype=U.UIA_EditControlTypeId):
        user32.keybd_event(0x1B, 0, 0, 0); user32.keybd_event(0x1B, 0, 2, 0)  # Esc closes the member list
        time.sleep(0.8); nodes = snap()
    # the owner may have switched chats: make sure the group's own chat is the open one
    sb = find(nodes, 'Search or start a new chat', ctype=U.UIA_EditControlTypeId)
    list_right = sb[0].r if sb else wr.left + (wr.right - wr.left) // 3

    def group_open(ns):
        return [n for n in find(ns, 'Vip Erdinç Turizm', prefix=True, ctype=U.UIA_ButtonControlTypeId) if n.t < wr.top + 130 and n.l > list_right]

    if not group_open(nodes):
        rows = [n for n in find(nodes, 'Vip Erdinç Turizm', prefix=True) if n.t > wr.top + 130 and n.r <= list_right + 20]
        if not rows:
            fail('group chat not found in the chat list')
        click(rows[0]); time.sleep(1.5); nodes = snap()
        if not group_open(nodes):
            fail('group chat did not open')
    sa = find(nodes, 'See all', prefix=True)
    if sa:
        click(sa[0]); time.sleep(1.0)  # the poll summary is open: expand it to every voter
    elif not find(nodes, 'Poll results'):
        vv = [n for n in find(nodes, 'View votes', ctype=U.UIA_ButtonControlTypeId) if wr.top + 100 < n.t < wr.bottom - 80]
        if not vv:
            pin = [n for n in find(nodes, 'Pinned message', prefix=True, ctype=U.UIA_ButtonControlTypeId) if 'AKTİF' in n.name]
            if not pin:
                fail('pinned poll banner not found')
            click(pin[0]); time.sleep(1.2)
            vv = wait(lambda: [n for n in find(snap(), 'View votes', ctype=U.UIA_ButtonControlTypeId) if wr.top + 100 < n.t < wr.bottom - 80], 4)
            if not vv:
                # the poll may sit near an edge of the chat: accept any on-screen "View votes"
                vv = [n for n in find(snap(), 'View votes', ctype=U.UIA_ButtonControlTypeId) if wr.top + 60 < (n.t + n.b) / 2 < wr.bottom - 10]
            if not vv:
                fail('View votes not found')
        click(vv[0]); time.sleep(1.0)
        sa = wait(lambda: find(snap(), 'See all', prefix=True), 4)
        if sa:
            click(sa[0]); time.sleep(1.0)
    head = wait(lambda: find(snap(), 'Poll results') or find(snap(), 'Poll details'), 4)
    if not head:
        fail('poll panel did not open')
    px = (head[0].l + wr.right) // 2
    total = None
    for n in snap():
        if n.name.endswith(' votes') and n.name.split(' ')[0].isdigit() and (n.l + n.r) / 2 > head[0].l:
            total = int(n.name.split(' ')[0]); break
    rows, idle = {}, 0
    user32.SetCursorPos(px, (wr.top + wr.bottom) // 2)
    for _ in range(60):
        user32.mouse_event(0x0800, 0, 0, 120, 0); time.sleep(0.01)  # to the top
    time.sleep(0.6)
    for loop in range(200):
        new = 0
        for li in [n for n in snap() if n.type == U.UIA_ListItemControlTypeId and (n.l + n.r) / 2 > head[0].l]:
            if li.name in rows:
                continue
            kids = []
            try:
                a = li.e.FindAllBuildCache(U.TreeScope_Descendants, uia.CreateTrueCondition(), _cr)
                for i in range(a.Length):
                    k = a.GetElement(i)
                    if k.CachedName:
                        kids.append([k.CachedLocalizedControlType, k.CachedName])
            except comtypes.COMError:
                pass
            rows[li.name] = kids; new += 1
        idle = 0 if new else idle + 1
        if idle >= 3:
            break
        user32.SetCursorPos(px, (wr.top + wr.bottom) // 2)
        for _ in range(7):
            user32.mouse_event(0x0800, 0, 0, -120, 0); time.sleep(0.02)
        time.sleep(0.5)
    tmp = out_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        for name, kids in rows.items():
            f.write(json.dumps({'name': name, 'kids': kids}, ensure_ascii=False) + '\n')
    os.replace(tmp, out_path)
    print(f'voters={len(rows)} total_shown={total}')
    if total is not None and len(rows) != total:
        print('WARNING: row count differs from the vote total')


main()
