#!/usr/bin/env python3
"""Fetch missing token logos for the Oracle desk.

For every watchlist item and digest.top3 entry in oracle-feed.json that has no logo file yet, this saves a
128x128 PNG as logos/<slug>.png (slug = lowercase name with dashes, e.g. "Quip Network" -> quip-network) and sets
"logo": "logos/<slug>.png" on the item. Sources, in order:
  1. CoinGecko by the item's "cg_id" (coins/<id> image.large). If the item also has "website", the CoinGecko
     homepage must be on the same domain, otherwise the item is skipped as unverified.
  2. The item's official "website": its apple-touch-icon / icon links (PNG/JPG/ICO, at least 64 px), then /apple-touch-icon.png.
Items with no verified source are skipped and listed at the end: save their verified official X profile image by hand.
Never guesses, never uses search results. Idempotent: existing logo files are kept. No secrets, no account needed.
Usage:  python3 fetch_logos.py [path/to/oracle-feed.json]     (default: oracle-feed.json next to this script)
Needs Pillow (pip install Pillow). Then publish the folder INCLUDING logos/.
"""
import json, os, sys, re, io, urllib.request, urllib.parse, html.parser
try:
    from PIL import Image
except ImportError:
    sys.exit('fetch_logos.py needs Pillow to resize logos. Install it with:  python3 -m pip install Pillow   then run again.')

D = os.path.dirname(os.path.abspath(__file__))
F = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(D, 'oracle-feed.json')
BASE = os.path.dirname(F)
LOGOS = os.path.join(BASE, 'logos')
UA = {'User-Agent': 'Mozilla/5.0 (oracle-desk fetch_logos)'}
SIZE, MIN_PX = 128, 64

def slug(n): return re.sub(r'^-+|-+$', '', re.sub(r'[^a-z0-9]+', '-', str(n or '').lower()))
def get(u, limit=5_000_000):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=25) as r:
        return r.read(limit), r.geturl()
def host(u):
    h = urllib.parse.urlparse(u if '//' in u else '//' + u).netloc.lower().split(':')[0]
    return h[4:] if h.startswith('www.') else h
def same_site(a, b):
    a, b = host(a), host(b)
    return bool(a and b) and (a == b or a.endswith('.' + b) or b.endswith('.' + a))

def to_png(data):
    im = Image.open(io.BytesIO(data))
    if getattr(im, 'n_frames', 1) > 1 or im.format == 'ICO':
        try: im.size = max(im.info.get('sizes', [im.size]))  # largest ICO frame
        except Exception: pass
    im.load(); im = im.convert('RGBA')
    if min(im.size) < MIN_PX: raise ValueError(f'image too small ({im.size[0]}x{im.size[1]})')
    im.thumbnail((SIZE, SIZE), Image.LANCZOS)            # keep aspect ratio, never stretch
    out = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    out.paste(im, ((SIZE - im.size[0]) // 2, (SIZE - im.size[1]) // 2), im)
    b = io.BytesIO(); out.save(b, 'PNG', optimize=True); return b.getvalue()

def from_coingecko(cg_id, website):
    d = json.loads(get('https://api.coingecko.com/api/v3/coins/' + urllib.parse.quote(cg_id) +
        '?localization=false&tickers=false&market_data=false&community_data=false&developer_data=false')[0])
    homes = [h for h in (d.get('links') or {}).get('homepage', []) if h]
    if website and homes and not any(same_site(h, website) for h in homes):
        raise ValueError(f'CoinGecko {cg_id} homepage {homes[0]} does not match website {website}')
    url = (d.get('image') or {}).get('large')
    if not url or 'missing' in url: raise ValueError(f'CoinGecko {cg_id} has no image')
    return to_png(get(url)[0]), f'CoinGecko image.large ({cg_id})'

class Icons(html.parser.HTMLParser):
    def __init__(s): super().__init__(); s.found = []
    def handle_starttag(s, tag, a):
        a = dict(a)
        if tag == 'link' and a.get('href') and re.search(r'(^|\s)(apple-touch-icon(-precomposed)?|icon)(\s|$)', (a.get('rel') or '').lower()):
            m = re.findall(r'(\d+)x\d+', a.get('sizes') or ''); px = max(map(int, m)) if m else (180 if 'apple' in a['rel'].lower() else 0)
            s.found.append((px, a['href']))

def from_website(site):
    if not site.startswith('http'): site = 'https://' + site
    page, final = get(site, 2_000_000)
    p = Icons(); p.feed(page.decode('utf-8', 'replace'))
    cands = [urllib.parse.urljoin(final, h) for _, h in sorted(p.found, key=lambda x: -x[0]) if not h.lower().split('?')[0].endswith('.svg')]
    cands += [urllib.parse.urljoin(final, '/apple-touch-icon.png')]
    errs = []
    for u in dict.fromkeys(cands):
        if not u.startswith('https://'): continue
        try: return to_png(get(u)[0]), f'website icon {u}'
        except Exception as e: errs.append(f'{u}: {e}')
    raise ValueError('no usable icon on ' + site + (' (' + '; '.join(errs[:3]) + ')' if errs else ''))

def main():
    feed = json.load(open(F, encoding='utf-8'))
    wl = feed.get('watchlist') or []
    top = (feed.get('digest') or {}).get('top3') or []
    by_name = {str(w.get('name', '')).lower(): w for w in wl}
    os.makedirs(LOGOS, exist_ok=True)
    changed, saved, kept, skipped = False, [], [], []
    done = {}
    for it in wl + top:
        name = it.get('name')
        if not name: continue
        w = by_name.get(str(name).lower(), {})
        cur = it.get('logo') or ''
        if cur.startswith('https://') or (cur and os.path.isfile(os.path.join(BASE, cur))):
            kept.append(name); continue
        rel = 'logos/' + slug(name) + '.png'; path = os.path.join(BASE, rel)
        if not os.path.isfile(path) and name.lower() not in done:
            cg = it.get('cg_id') or w.get('cg_id'); site = it.get('website') or w.get('website') or it.get('url') or ''
            png = src = None; why = []
            if cg:
                try: png, src = from_coingecko(cg, site)
                except Exception as e: why.append(str(e))
            if png is None and site:
                try: png, src = from_website(site)
                except Exception as e: why.append(str(e))
            if png is None:
                done[name.lower()] = False
                skipped.append(f'{name}: ' + ('; '.join(why) if why else 'no cg_id or website, so no verified source') +
                               ' -> save its verified official X profile image as ' + rel); continue
            open(path, 'wb').write(png); saved.append(f'{name} -> {rel} ({src})')
            done[name.lower()] = True
        if os.path.isfile(path):
            if it.get('logo') != rel: it['logo'] = rel; changed = True
            if it is not w and w and not w.get('logo'): w['logo'] = rel
    if changed:
        try:
            import fcntl; lock = open(os.path.join(BASE, '.prices.lock'), 'w'); fcntl.flock(lock, fcntl.LOCK_EX)  # same lock as update_prices.py
            fresh = json.load(open(F, encoding='utf-8'))  # re-read so a price update in between is not lost
            logos = {str(i.get('name', '')).lower(): i.get('logo') for i in wl + top if i.get('logo')}
            for i in (fresh.get('watchlist') or []) + ((fresh.get('digest') or {}).get('top3') or []):
                l = logos.get(str(i.get('name', '')).lower())
                if l and not i.get('logo') or (l and i.get('logo') and not i['logo'].startswith('https://') and not os.path.isfile(os.path.join(BASE, i['logo']))): i['logo'] = l
            feed = fresh
        except ImportError: pass
        tmp = F + '.tmp'; json.dump(feed, open(tmp, 'w', encoding='utf-8'), indent=1, ensure_ascii=False); os.replace(tmp, F)
    for s in saved: print('saved  ', s)
    print(f'{len(saved)} saved, {len(kept)} already had a logo, {len(skipped)} skipped' + (', feed updated' if changed else ''))
    for s in skipped: print('SKIPPED', s)
    if saved or changed: print('Now publish the folder, including logos/, and check one logo URL loads (HTTP 200).')

if __name__ == '__main__': main()
