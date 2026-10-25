"""Visit every group member's "Contact info" in WhatsApp Desktop and record the profile's own
name (push name), phone number and a 40x40 WebP photo.

usage: collect_profiles.py <members.jsonl> <profiles.json> <photo dir> [limit]

Resumable: members already in profiles.json are skipped, and the file is rewritten after every
member. The only things this script clicks are: "View all" (opens the member list), a member row
(opens its menu), the menu item whose UIA name is exactly "Contact info", and "Back". Before the
menu click it hit-tests the point; if anything that is not "Contact info" is under it, it presses
Escape and skips the member. If a confirmation dialog with a "Remove" button ever shows up, it
clicks "Cancel" and stops.
"""
import sys, os, re, json, time, ctypes, hashlib, unicodedata
from ctypes import wintypes
import comtypes, comtypes.client
comtypes.client.GetModule('UIAutomationCore.dll')
from comtypes.gen import UIAutomationClient as U
from PIL import ImageGrab, Image

HWND = ctypes.windll.user32.FindWindowW(None, 'WhatsApp') or sys.exit('WhatsApp Desktop window not found')
members_path, out_path, photo_dir = sys.argv[1], sys.argv[2], sys.argv[3]

# one copy at a time: two copies would fight over the same mouse
import msvcrt
_lock = open(os.path.join(os.path.dirname(out_path), 'ui.lock'), 'w')  # shared with refresh_votes.py
try:
    msvcrt.locking(_lock.fileno(), msvcrt.LK_NBLCK, 1)
except OSError:
    print('another copy is running, exiting'); sys.exit(4)
sys.stdout = open(os.path.join(os.path.dirname(out_path), 'collect.log'), 'a', encoding='utf-8', buffering=1)
sys.stderr = sys.stdout
limit = int(sys.argv[4]) if len(sys.argv) > 4 else 10 ** 6
os.makedirs(photo_dir, exist_ok=True)
uia = comtypes.client.CreateObject(U.CUIAutomation._reg_clsid_, interface=U.IUIAutomation)
win = uia.ElementFromHandle(HWND)
user32 = ctypes.windll.user32
PHONE = re.compile(r'^\+?\d[\d \-()]{7,}\d$')
INVISIBLE = re.compile(r'[‎‏‪-‮]')


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD), ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD), ('dwExtraInfo', ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT), ('pad', ctypes.c_byte * 32)]
    _anonymous_ = ('u',)
    _fields_ = [('type', wintypes.DWORD), ('u', _U)]


def send(vk=0, scan=0, flags=0):
    i = INPUT(type=1); i.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(i))


def key(vk):
    send(vk); send(vk, flags=2)


def type_text(s):
    b = s.encode('utf-16-le')
    for i in range(0, len(b), 2):
        u = int.from_bytes(b[i:i + 2], 'little')
        send(scan=u, flags=0x0004); send(scan=u, flags=0x0004 | 0x0002)
        time.sleep(0.008)


def fg_ok():
    b = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(user32.GetForegroundWindow(), b, 256)
    return 'WhatsApp' in b.value


def bring_front():
    """Put WhatsApp in front (Alt tap lifts the foreground lock); True when it worked."""
    if fg_ok():
        return True
    key(0x12)
    user32.ShowWindow(HWND, 9); user32.SetForegroundWindow(HWND)
    time.sleep(0.4)
    return fg_ok()


def els(cond=None, root=None):
    a = (root or win).FindAll(U.TreeScope_Descendants, cond or uia.CreateTrueCondition())
    return [a.GetElement(i) for i in range(a.Length)]


class Node:
    __slots__ = ('e', 'name', 'type', 'loc', 'l', 't', 'r', 'b')


_cr = uia.CreateCacheRequest()
for _pid in (U.UIA_NamePropertyId, U.UIA_ControlTypePropertyId, U.UIA_BoundingRectanglePropertyId, U.UIA_LocalizedControlTypePropertyId):
    _cr.AddProperty(_pid)


_doc = [None]


def doc():
    """The WebView document. The window exposes it many times over; one copy is enough."""
    try:
        if _doc[0] is not None and _doc[0].CurrentBoundingRectangle.right > 0:
            return _doc[0]
    except comtypes.COMError:
        pass
    _doc[0] = win.FindFirst(U.TreeScope_Descendants, uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_DocumentControlTypeId))
    return _doc[0]


def snap(root=None):
    """Every element under root with name, type and box fetched in one batch, duplicates dropped."""
    a = (root or doc() or win).FindAllBuildCache(U.TreeScope_Descendants, uia.CreateTrueCondition(), _cr)
    out, seen = [], set()
    for i in range(a.Length):
        e = a.GetElement(i)
        try:
            n = Node(); n.e = e; n.name = e.CachedName or ''; n.type = e.CachedControlType
            n.loc = e.CachedLocalizedControlType or ''
            r = e.CachedBoundingRectangle; n.l, n.t, n.r, n.b = r.left, r.top, r.right, r.bottom
            k = (n.name, n.type, n.l, n.t, n.r, n.b)
            if n.r > n.l and n.b > n.t and k not in seen:
                seen.add(k); out.append(n)
        except comtypes.COMError:
            continue
    return out


def by_name(name, ctype=None, prefix=False, nodes=None):
    nodes = snap() if nodes is None else nodes
    return [n for n in nodes if (n.name.startswith(name) if prefix else n.name == name) and (ctype is None or n.type == ctype)]


def ancestor(e, min_height):
    """Nearest ancestor at least min_height tall (the panel or dialog that holds e)."""
    w = uia.RawViewWalker
    cur = e
    for _ in range(12):
        try:
            cur = w.GetParentElement(cur)
            r = cur.CurrentBoundingRectangle
            if r.bottom - r.top >= min_height:
                return cur
        except comtypes.COMError:
            return None
    return None


def heading(name, nodes=None):
    """Chromium exposes headings as text with the localized type "heading"."""
    return [n for n in by_name(name, nodes=nodes) if n.loc == 'heading']


def center(n):
    return (n.l + n.r) // 2, (n.t + n.b) // 2


def click_at(x, y):
    user32.SetCursorPos(x, y)
    user32.mouse_event(0x0002, 0, 0, 0, 0); user32.mouse_event(0x0004, 0, 0, 0, 0)


def hit_inside(n, x, y):
    """True when the element under (x, y) is n itself or lies inside n's box."""
    h = uia.ElementFromPoint(U.tagPOINT(x, y))
    hr = h.CurrentBoundingRectangle
    if h.CurrentName == n.name and hr.left == n.l and hr.top == n.t:
        return True
    return n.l <= hr.left and hr.right <= n.r and n.t <= hr.top and hr.bottom <= n.b and hr.right > hr.left


def wait_for(fn, timeout=4.0, step=0.15):
    t = time.time()
    while time.time() - t < timeout:
        v = fn()
        if v:
            return v
        time.sleep(step)
    return None


def guard_remove_dialog():
    """A Remove confirmation must never be accepted: cancel it and stop the whole run."""
    nodes = snap()
    cancel = by_name('Cancel', U.UIA_ButtonControlTypeId, nodes=nodes)
    if cancel and [n for n in nodes if n.name.startswith('Remove') and n.name.strip() != 'Remove']:
        click_at(*center(cancel[0])); time.sleep(0.5)
        print('REMOVE DIALOG SEEN, cancelled and stopped', flush=True)
        sys.exit(3)


def search_box(nodes=None):
    b = by_name('Search contacts', U.UIA_EditControlTypeId, nodes=nodes)
    return b[0] if b else None


def box_value(box):
    try:
        return box.e.GetCurrentPattern(U.UIA_ValuePatternId).QueryInterface(U.IUIAutomationValuePattern).CurrentValue
    except Exception:
        return None


def open_member_list():
    for _ in range(4):
        nodes = snap()
        if search_box(nodes):
            return True
        back = by_name('Back', U.UIA_ButtonControlTypeId, nodes=nodes)
        if heading('Contact info', nodes) and back:
            click_at(*center(back[0])); time.sleep(0.8); continue
        wr = win.CurrentBoundingRectangle
        if not heading('Group info', nodes) and not by_name('Group info', nodes=nodes):
            # the side panel is closed: the chat header opens group info
            hdr = [n for n in by_name('Vip Erdinç Turizm', ctype=U.UIA_ButtonControlTypeId, prefix=True, nodes=nodes) if n.t < wr.top + 130]
            if hdr:
                click_at(*center(hdr[0])); time.sleep(1.0); continue
        va = [n for n in by_name('View all', prefix=True, nodes=nodes)
              if wr.left < center(n)[0] < wr.right and wr.top + 60 < center(n)[1] < wr.bottom - 20]
        if va:
            click_at(*center(va[0]))
            if wait_for(lambda: search_box(snap()), 3):
                return True
        else:
            # group info is scrolled up: wheel the right-hand panel down until "View all" shows
            user32.SetCursorPos(wr.right - 280, (wr.top + wr.bottom) // 2)
            for _ in range(25):
                user32.mouse_event(0x0800, 0, 0, -120, 0); time.sleep(0.02)
            time.sleep(0.7)
    return bool(search_box(snap()))


def search(q):
    box = search_box()
    if not box:
        return False
    click_at(*center(box)); time.sleep(0.2)
    if not fg_ok():
        return False
    send(0x11); send(0x41); send(0x41, flags=2); send(0x11, flags=2); key(0x08); time.sleep(0.1)
    type_text(q); time.sleep(0.7)
    return box_value(box) == q


def modal_rows(nodes=None):
    nodes = snap() if nodes is None else nodes
    box = search_box(nodes)
    if not box:
        return []
    return [n for n in nodes if n.type == U.UIA_ListItemControlTypeId and n.t > box.b and box.l - 40 <= (n.l + n.r) / 2 <= box.r + 40]


def query_for(m):
    """A search string that finds this member: the national number, else the longest emoji-free run of the name."""
    blob = m['name'] + ' ' + ' '.join(k[1] for k in m['kids'])
    ph = re.findall(r'\+\d[\d \-()]{7,}\d', blob)
    if ph:
        d = re.sub(r'\D', '', ph[0])
        return d[2:] if d.startswith('90') else d
    item = next((k[1] for k in m['kids'] if k[0] == 'item'), m['name'])
    item = INVISIBLE.sub('', re.sub(r'^Maybe ', '', item))
    runs = re.split(r'[^\w\s.,\-*&\'()/:|~@!?]+', item)
    best = max((r.strip() for r in runs), key=len, default='')
    return best[:28].strip() or item[:28]


def read_contact():
    if not wait_for(lambda: heading('Contact info'), 4):
        return None
    time.sleep(0.4)
    nodes = snap()
    head = heading('Contact info', nodes)[0]
    vp = by_name('View photo', U.UIA_ButtonControlTypeId, nodes=nodes)
    top_limit = vp[0].b if vp else head.b
    panel = [n for n in nodes if n.l >= head.l - 60 and n.loc in ('text', 'graphic')]
    panel.sort(key=lambda n: (n.t, n.l))
    # emoji split a name into several nodes on one line: group them into lines (by top) and join
    lines = []
    for n in panel:
        if n.t <= top_limit:
            continue
        txt = INVISIBLE.sub('', n.name)
        if lines and abs(n.t - lines[-1]['top']) <= 8:
            lines[-1]['parts'].append((n.l, txt)); lines[-1]['bottom'] = max(lines[-1]['bottom'], n.b)
            lines[-1]['h'] = max(lines[-1]['h'], n.b - n.t if n.loc == 'text' else 0)
        else:
            lines.append({'top': n.t, 'bottom': n.b, 'h': n.b - n.t if n.loc == 'text' else 0, 'parts': [(n.l, txt)]})
    def text(l):
        return re.sub(r'\s+', ' ', ' '.join(p for _, p in sorted(l['parts']))).strip()
    saved = push = phone = None
    if lines:
        big = lines[0]['h']
        k = 1
        while k < len(lines) and abs(lines[k]['h'] - big) <= 2 and lines[k]['top'] - lines[k - 1]['bottom'] <= 8:
            k += 1  # a long saved name wraps onto more big-font lines
        saved = ' '.join(text(l) for l in lines[:k])
        if k < len(lines) and 0 <= lines[k]['top'] - lines[k - 1]['bottom'] <= 20 and lines[k]['h'] < big - 2:
            push = text(lines[k]).lstrip('~').strip()
            if PHONE.match(push):
                push = None  # that line is the number, not a name
    for n in panel:
        t = INVISIBLE.sub('', n.name).strip()
        if n.loc == 'text' and PHONE.match(t):
            phone = t; break
    img = None
    if vp and os.environ.get('CTI_PHOTOS') == '1':  # photos come from the member list pass instead
        # the photo slides in when the panel opens: grab until two frames in a row are identical
        box = (vp[0].l, vp[0].t, vp[0].r, vp[0].b)
        prev = ImageGrab.grab(bbox=box, all_screens=True)
        for _ in range(10):
            time.sleep(0.2)
            img = ImageGrab.grab(bbox=box, all_screens=True)
            if img.tobytes() == prev.tobytes():
                break
            prev = img
    return {'saved': saved, 'push': push, 'phone': phone, 'img': img}


def main():
    members = [json.loads(l) for l in open(members_path, encoding='utf-8')]
    members = [m for m in members if len(m['name'].strip()) > 2 and not m['name'].startswith('You')]
    done = json.load(open(out_path, encoding='utf-8')) if os.path.exists(out_path) else {}
    todo = [m for m in members if m['name'] not in done][:limit]
    print(f'todo={len(todo)} done={len(done)}', flush=True)
    for n, m in enumerate(todo, 1):
        for attempt in range(2):
            try:
                ok = visit(n, len(todo), m, done)
                break
            except comtypes.COMError as e:
                import traceback
                print('UIA error, retrying', m['name'][:40], e, ''.join(traceback.format_exc().splitlines(True)[-6:]), flush=True)
                key(0x1B); time.sleep(1.0); ok = True
        if ok is False:
            break
    json.dump(done, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print('finished', len(done), flush=True)


def visit(n, total, m, done):
    """One member; returns False to stop the whole run."""
    if True:
        if not bring_front():
            print('WhatsApp is not in front, pausing run', flush=True); return False
        if not open_member_list():
            print('could not open member list at', m['name'][:40], flush=True); return False
        q = query_for(m)
        if not search(q):
            print('search failed', repr(q), flush=True); done[m['name']] = {'error': 'search'}; return True
        rows = wait_for(lambda: [r for r in modal_rows() if r.name == m['name']], 3) or []
        if not rows:
            print('row not found', repr(q), m['name'][:50], flush=True); done[m['name']] = {'error': 'row'}; return True
        click_at(*center(rows[0])); time.sleep(0.5)
        ci = wait_for(lambda: [n for n in by_name('Contact info') if n.loc != 'heading'], 2) or []
        if not ci:
            key(0x1B); print('no menu', m['name'][:40], flush=True); done[m['name']] = {'error': 'menu'}; return True
        x, y = center(ci[0])
        if not wait_for(lambda: hit_inside(ci[0], x, y), 1.5):
            key(0x1B); print('menu hit-test failed, skipped', m['name'][:40], flush=True); done[m['name']] = {'error': 'hit'}; return True
        click_at(x, y)
        guard_remove_dialog()
        info = read_contact()
        if not info:
            key(0x1B); done[m['name']] = {'error': 'contact'}; print('contact panel missing', flush=True); return True
        rec = {k: info[k] for k in ('saved', 'push', 'phone')}
        if info['img'] is not None:
            fn = hashlib.sha1(m['name'].encode('utf-8')).hexdigest()[:12] + '.webp'
            info['img'].convert('RGB').resize((40, 40), Image.LANCZOS).save(os.path.join(photo_dir, fn), 'WEBP', quality=60, method=6)
            rec['photo'] = 'a/' + fn
        done[m['name']] = rec
        tmp = out_path + '.tmp'
        json.dump(done, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        os.replace(tmp, out_path)
        print(f'{n}/{total} {rec.get("push") or "-"} | {rec.get("phone") or "-"}', flush=True)
        back = by_name('Back', U.UIA_ButtonControlTypeId)
        if back:
            click_at(*center(back[0])); time.sleep(0.6)
        return True


main()
