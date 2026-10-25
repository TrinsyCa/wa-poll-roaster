"""Build site/data.json from the WhatsApp Desktop dumps.

usage: build_data.py <dump dir> <site dir> [--closes 2026-10-25T22:23:00+03:00]

Inputs in <dump dir>:
  members.jsonl      every row of the group's "Search members" list
  voters.jsonl       every row of the poll's voter list
  r_unmatched.json   member-search results for voters the lists could not match (query -> rows)
  profiles.json      optional, per member row: {"push": ..., "phone": ...} read from Contact info
  photos.json        optional, per member row: "a/<hash>.webp" (or null for the default avatar)
  clean_names.json   optional, per member row: the saved contact name cut down to first + last name
"""
import json, os, re, sys, unicodedata
from datetime import datetime, timezone

PHONE = re.compile(r'\+\d[\d \-()]{7,}\d')
HANDLE = re.compile(r'@[\w.]+')
TIME = re.compile(r'(Today|Yesterday|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|\d{1,2}/\d{1,2}/\d{4}) at \d{1,2}:\d{2}')
INVISIBLE = re.compile(r'[‎‏‪-‮]')


def load(path):
    rows = [json.loads(l) for l in open(path, encoding='utf-8')]
    return [r for r in rows if len(r['name'].strip()) > 2]  # drop the A-Z section headers


def norm(s):
    s = unicodedata.normalize('NFKC', s).casefold()
    return ''.join(c for c in s if c.isalnum())


def digits(p):
    return re.sub(r'\D', '', p)


def parse(r):
    """phones, handles, normalised name, display name, is_push (shown as ~name, i.e. the profile's own name)"""
    texts = [r['name']] + [k[1] for k in r['kids']]
    blob = ' '.join(TIME.sub('', t) for t in texts)
    phones = [p.strip() for p in PHONE.findall(blob)]
    handles = {h.lower() for h in HANDLE.findall(blob)}
    kid = {}
    for t, v in r['kids']:
        kid.setdefault(t, v)
    name = kid.get('group') or kid.get('item') or r['name']
    name = TIME.sub('', name)
    is_push = name.startswith('Maybe ') or r['name'].startswith('~')
    name = re.sub(r'^Maybe ', '', name)
    name = INVISIBLE.sub('', PHONE.sub('', HANDLE.sub('', name))).strip()
    return {'phones': {digits(p) for p in phones}, 'phone_text': phones[0] if phones else '',
            'handles': handles, 'key': norm(name), 'name': name, 'is_push': is_push}


def main():
    dump, site = sys.argv[1], sys.argv[2]
    closes = sys.argv[sys.argv.index('--closes') + 1] if '--closes' in sys.argv else None
    members = load(os.path.join(dump, 'members.jsonl'))
    voters = load(os.path.join(dump, 'voters.jsonl'))
    search = json.load(open(os.path.join(dump, 'r_unmatched.json'), encoding='utf-8')) if os.path.exists(os.path.join(dump, 'r_unmatched.json')) else {}
    profiles = json.load(open(os.path.join(dump, 'profiles.json'), encoding='utf-8')) if os.path.exists(os.path.join(dump, 'profiles.json')) else {}
    photos = json.load(open(os.path.join(dump, 'photos.json'), encoding='utf-8')) if os.path.exists(os.path.join(dump, 'photos.json')) else {}
    # saved contact names trimmed to first + last name (the admin's notes like "Adore İşini Yaptırdım" removed)
    clean = json.load(open(os.path.join(dump, 'clean_names.json'), encoding='utf-8')) if os.path.exists(os.path.join(dump, 'clean_names.json')) else {}

    mp = [parse(m) for m in members]
    vp = [parse(v) for v in voters]
    by_phone, by_handle, by_key = {}, {}, {}
    for i, p in enumerate(mp):
        prof_phone = (profiles.get(members[i]['name']) or {}).get('phone')
        if prof_phone:  # numbers read from Contact info cover the saved contacts too
            p['phones'] = p['phones'] | {digits(prof_phone)}
        for d in p['phones']: by_phone.setdefault(d, set()).add(i)
        for h in p['handles']: by_handle.setdefault(h, set()).add(i)
        by_key.setdefault(p['key'], set()).add(i)
    row_index = {m['name']: i for i, m in enumerate(members)}

    voted, ambiguous, push_from_poll, phone_from_poll = set(), set(), {}, {}
    unresolved = []
    for v, p in zip(voters, vp):
        hits = set()
        for d in p['phones']: hits |= by_phone.get(d, set())
        for h in p['handles']: hits |= by_handle.get(h, set())
        if not hits and not p['phones'] and not p['handles']:
            hits = set(by_key.get(p['key'], set()))
        if not hits:
            q = next(iter(p['phones']), None)
            q = (q[2:] if q and q.startswith('90') else q) or p['name']
            rows = search.get(q)
            rows = rows if isinstance(rows, list) else (rows or {}).get('rows', [])
            hits = {row_index[r] for r in rows if r in row_index}
            if not rows and q not in search:
                unresolved.append(q)
        if len(hits) == 1:
            i = next(iter(hits))
            voted.add(i)
            if p['is_push']: push_from_poll[i] = p['name']
            if p['phone_text']: phone_from_poll[i] = p['phone_text']
        elif len(hits) > 1:
            ambiguous |= hits

    out = []
    for i, (m, p) in enumerate(zip(members, mp)):
        prof = profiles.get(m['name'], {})
        admin = 'group admin' in m['name'].lower()
        you = m['name'].startswith('You')
        push = prof.get('push') or (p['name'] if p['is_push'] else None) or push_from_poll.get(i)
        if push and not any(c.isalnum() for c in push):
            push = None  # an emoji-only profile name cannot be searched; use the saved name instead
        handle = next(iter(HANDLE.findall(m['name'])), '')
        phone = prof.get('phone') or p['phone_text'] or phone_from_poll.get(i, '')
        status = 'voted' if i in voted else ('check' if i in ambiguous else 'not_voted')
        out.append({
            'id': i,
            # profile's own name, else the saved contact name, else just the number
            'name': push or clean.get(m['name']) or re.sub(r'\s*Group admin.*$', '', p['name']) or handle or INVISIBLE.sub('', phone),
            'own': bool(push),            # False: the name is still the admin's saved contact name
            'phone': INVISIBLE.sub('', phone),
            'photo': photos.get(m['name']) or prof.get('photo'),
            'status': status,
            'admin': admin or you,
        })
    data = {
        'updated': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'closes': closes,
        'poll': 'GRUPTA AKTİF MİSİN?',
        'group': 'Vip Erdinç Turizm',
        'total': len(out),
        'voted': sum(1 for x in out if x['status'] == 'voted'),
        'members': sorted(out, key=lambda x: (x['name'][:1] in '+@', norm(x['name']))),  # bare numbers and handles last
    }
    tmp = os.path.join(site, 'data.json.tmp')
    json.dump(data, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    os.replace(tmp, os.path.join(site, 'data.json'))
    print(f"members={len(out)} voted={data['voted']} check={sum(1 for x in out if x['status']=='check')} "
          f"not_voted={sum(1 for x in out if x['status']=='not_voted')} own_name={sum(1 for x in out if x['own'])} "
          f"phone={sum(1 for x in out if x['phone'])} photo={sum(1 for x in out if x['photo'])} unresolved_voters={len(unresolved)}")
    if unresolved:
        json.dump(unresolved, open(os.path.join(dump, 'q_unresolved.json'), 'w', encoding='utf-8'), ensure_ascii=False)


if __name__ == '__main__':
    main()
