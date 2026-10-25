"""Save every member's avatar from WhatsApp Desktop's "Search members" list as a 40x40 WebP.

usage: photos.py <photos.json> <photo dir>
The member list must be reachable (group info open, or the list already open). Read-only: it
clicks "View all" to open the list, otherwise it only moves the mouse and turns the wheel.
"""
import sys, os, json, time, ctypes, hashlib, msvcrt
import comtypes, comtypes.client
comtypes.client.GetModule('UIAutomationCore.dll')
from comtypes.gen import UIAutomationClient as U
from PIL import ImageGrab, Image

HWND = ctypes.windll.user32.FindWindowW(None, 'WhatsApp') or sys.exit('WhatsApp Desktop window not found')
out_path, photo_dir = sys.argv[1], sys.argv[2]
os.makedirs(photo_dir, exist_ok=True)
_lock = open(os.path.join(os.path.dirname(out_path), 'ui.lock'), 'w')
try:
    msvcrt.locking(_lock.fileno(), msvcrt.LK_NBLCK, 1)
except OSError:
    print('another UI script is running, exiting'); sys.exit(4)
uia = comtypes.client.CreateObject(U.CUIAutomation._reg_clsid_, interface=U.IUIAutomation)
win = uia.ElementFromHandle(HWND)
user32 = ctypes.windll.user32
_cr = uia.CreateCacheRequest()
for _pid in (U.UIA_NamePropertyId, U.UIA_ControlTypePropertyId, U.UIA_BoundingRectanglePropertyId):
    _cr.AddProperty(_pid)
_raw = uia.CreateCacheRequest()  # the avatar box is unnamed, so it only exists in the raw view
_raw.AddProperty(U.UIA_BoundingRectanglePropertyId)
_raw.TreeFilter = uia.RawViewCondition


def doc():
    return win.FindFirst(U.TreeScope_Descendants, uia.CreatePropertyCondition(U.UIA_ControlTypePropertyId, U.UIA_DocumentControlTypeId))


def snap(root=None):
    a = (root or doc()).FindAllBuildCache(U.TreeScope_Descendants, uia.CreateTrueCondition(), _cr)
    out, seen = [], set()
    for i in range(a.Length):
        e = a.GetElement(i)
        try:
            r = e.CachedBoundingRectangle
            k = (e.CachedName, e.CachedControlType, r.left, r.top, r.right, r.bottom)
            if r.right > r.left and r.bottom > r.top and k not in seen:
                seen.add(k); out.append((e, e.CachedName or '', e.CachedControlType, r.left, r.top, r.right, r.bottom))
        except comtypes.COMError:
            continue
    return out


def click(x, y):
    user32.SetCursorPos(x, y); user32.mouse_event(2, 0, 0, 0, 0); user32.mouse_event(4, 0, 0, 0, 0)


def main():
    done = json.load(open(out_path, encoding='utf-8')) if os.path.exists(out_path) else {}
    nodes = snap()
    box = [n for n in nodes if n[1] == 'Search contacts' and n[2] == U.UIA_EditControlTypeId]
    if not box:
        wr = win.CurrentBoundingRectangle
        va = [n for n in nodes if n[1].startswith('View all') and wr.top + 60 < (n[4] + n[6]) // 2 < wr.bottom - 20]
        if not va:
            print('open group info and scroll to "View all" first'); sys.exit(2)
        click((va[0][3] + va[0][5]) // 2, (va[0][4] + va[0][6]) // 2); time.sleep(1.2)
        nodes = snap()
        box = [n for n in nodes if n[1] == 'Search contacts' and n[2] == U.UIA_EditControlTypeId]
        if not box:
            print('member list did not open'); sys.exit(2)
    _, _, _, bl, bt, br, bb = box[0]
    title = [n for n in nodes if n[1] == 'Search members']
    park = ((title[0][3] + title[0][5]) // 2, (title[0][4] + title[0][6]) // 2) if title else (bl, bt - 40)
    wheel_at = ((bl + br) // 2, bb + 400)
    view_top, view_bottom = bb + 4, None
    user32.SetCursorPos(*wheel_at)
    for _ in range(300):
        user32.mouse_event(0x0800, 0, 0, 120, 0); time.sleep(0.003)
    time.sleep(0.8)
    idle, stuck, last_sig = 0, 0, None
    for loop in range(600):
        user32.SetCursorPos(*park); time.sleep(0.5)  # no hover tint on the rows we photograph
        nodes = snap()
        rows = [n for n in nodes if n[2] == U.UIA_ListItemControlTypeId and bl - 40 <= (n[3] + n[5]) / 2 <= br + 40 and n[4] > bb]
        if view_bottom is None:
            # the visible list ends where the dialog ends, not where the (virtualised) rows end
            cur, dlg_bottom = box[0][0], None
            for _ in range(12):
                try:
                    cur = uia.RawViewWalker.GetParentElement(cur)
                    rr = cur.CurrentBoundingRectangle
                except comtypes.COMError:
                    break
                if rr.bottom - rr.top >= 600:
                    dlg_bottom = rr.bottom; break
            view_bottom = min(dlg_bottom or (bb + 600), win.CurrentBoundingRectangle.bottom - 10) - 4
        new = 0
        pending = sum(1 for n in rows if len(n[1].strip()) > 2 and n[1] not in done and n[4] >= view_top and n[6] <= view_bottom)
        for e, name, _, l, t, r, b in rows:
            if len(name.strip()) <= 2 or name in done or t < view_top or b > view_bottom:
                continue
            # the avatar: the square image near the row's left edge
            imgs = []
            try:
                # WhatsApp renders the avatar as an unnamed ~61px square group at the row's left
                a = e.FindAllBuildCache(U.TreeScope_Descendants, uia.CreateTrueCondition(), _raw)
                for i in range(a.Length):
                    rr = a.GetElement(i).CachedBoundingRectangle
                    w, h = rr.right - rr.left, rr.bottom - rr.top
                    if 45 <= w <= 80 and abs(w - h) <= 4 and rr.left - l < 60:
                        imgs.append((rr.left, rr.top, rr.right, rr.bottom))
            except comtypes.COMError:
                pass
            if not imgs:
                done[name] = None; new += 1  # default avatar, no photo
                continue
            bbox = imgs[0]
            a1 = ImageGrab.grab(bbox=bbox, all_screens=True); time.sleep(0.15)
            a2 = ImageGrab.grab(bbox=bbox, all_screens=True)
            if a1.tobytes() != a2.tobytes():
                continue  # still loading; next round
            fn = hashlib.sha1(name.encode('utf-8')).hexdigest()[:12] + '.webp'
            a2.convert('RGB').resize((40, 40), Image.LANCZOS).save(os.path.join(photo_dir, fn), 'WEBP', quality=60, method=6)
            done[name] = 'a/' + fn; new += 1
        json.dump(done, open(out_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        # the end of the list is when scrolling no longer changes which rows are on screen
        sig = tuple(n[1] for n in rows if n[4] >= view_top and n[6] <= view_bottom)
        idle = idle + 1 if (sig == last_sig and not new and not pending) else 0
        last_sig = sig
        if idle >= 3:
            break
        if pending and not new:
            stuck += 1
            if stuck < 8:
                time.sleep(0.6)  # avatars still loading on this screen: wait instead of scrolling past them
                continue
        stuck = 0
        user32.SetCursorPos(*wheel_at)
        for _ in range(5):
            user32.mouse_event(0x0800, 0, 0, -120, 0); time.sleep(0.02)
        time.sleep(0.4)
    print(f'photos: {sum(1 for v in done.values() if v)} with photo, {sum(1 for v in done.values() if not v)} default, rows {len(done)}')


main()
