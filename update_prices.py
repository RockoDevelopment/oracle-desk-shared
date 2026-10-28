#!/usr/bin/env python3
"""Refresh live-token prices in oracle-feed.json (CoinGecko public API). Run every 15 minutes, then publish."""
import json, sys, urllib.request, urllib.parse, datetime, os, fcntl, zoneinfo
D = os.path.dirname(os.path.abspath(__file__))
lock = open(os.path.join(D, '.prices.lock'), 'w'); fcntl.flock(lock, fcntl.LOCK_EX)
F = os.path.join(D, 'oracle-feed.json')
feed = json.load(open(F))
# Auto-flip: items with "cg_watch": true and no cg_id are checked on CoinGecko every run. When a coin with the same symbol
# lists AND its official homepage matches the item's own website domain, cg_id is set and live prices take over (the manual price stays until then).
def _get(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'oracle-desk'}), timeout=30))
def _host(u):
    h = urllib.parse.urlparse(u if '//' in u else '//' + u).netloc.lower()
    return h[4:] if h.startswith('www.') else h
for w in feed.get('watchlist', []):
    if not w.get('cg_watch') or w.get('cg_id') or not w.get('website') or not w.get('ticker'): continue
    try:
        want = _host(w['website']); found = None
        for c in _get('https://api.coingecko.com/api/v3/search?query=' + urllib.parse.quote(w['ticker'])).get('coins', []):
            if c.get('symbol', '').lower() != w['ticker'].lower(): continue
            d = _get('https://api.coingecko.com/api/v3/coins/' + c['id'] + '?localization=false&tickers=false&market_data=false&community_data=false&developer_data=false')
            if any(_host(h) == want or _host(h).endswith('.' + want) for h in d.get('links', {}).get('homepage', []) if h):
                found = c['id']; break
        if found:
            w['cg_id'] = found; w.pop('cg_watch', None)
            print('CoinGecko listing found for', w['name'], '->', found)
    except Exception as e:
        print('cg_watch check failed for', w.get('name'), e)
live = [w for w in feed.get('watchlist', []) if w.get('cg_id') and w.get('price') is not None]
if not live: print('no live tokens'); sys.exit(0)
ids = ','.join(sorted({w['cg_id'] for w in live}))
req = urllib.request.Request('https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&per_page=100&ids=' + ids, headers={'User-Agent': 'oracle-desk'})
data = {c['id']: c for c in json.load(urllib.request.urlopen(req, timeout=30))}
now = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()  # machine's local zone
n = 0
for w in live:
    c = data.get(w['cg_id'])
    if not c or c.get('current_price') is None: continue
    w['price'] = c['current_price']
    if c.get('market_cap'): w['market_cap'] = c['market_cap']
    if c.get('total_volume') is not None: w['volume_24h'] = c['total_volume']
    w['price_updated'] = now; w['last_update'] = now; n += 1
feed['prices_updated'] = now
feed = json.loads(json.dumps(feed))
tmp = F + '.tmp'; json.dump(feed, open(tmp, 'w'), indent=1, ensure_ascii=False); os.replace(tmp, F)
print('updated', n, 'tokens at', now)
