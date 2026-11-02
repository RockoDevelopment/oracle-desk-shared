# oracle-desk-shared
THE ORACLE desk, shared copy for other owners (no personal data)

## Files
- `oracle-desk-for-others.html` – the Oracle desk page (save as `oracle-desk.html` and `index.html`)
- `oracle-desk-lite.html` – the Oracle Lite page
- `update_prices.py` – live price refresh (CoinGecko, by `cg_id`)
- `fetch_logos.py` – fetches missing token logos into `logos/` (needs Pillow: `python3 -m pip install Pillow`)

## Token logos (do this or the desk shows white squares with an initial)
Every watchlist item and every `digest.top3` entry must have `logo` pointing at a published file in `logos/`
(`logos/<slug>.png`, slug = lowercase name with dashes, e.g. Quip Network -> `logos/quip-network.png`, 128x128 PNG).
1. At setup, and whenever a project joins the watchlist, run `python3 fetch_logos.py` in the folder that holds
   `oracle-feed.json`. It uses CoinGecko by `cg_id`, else the official website's icon, sets `logo`, and lists what it skipped.
2. For skipped items, save the project's verified official X profile image by hand. Never an impostor's, never a made-up logo.
3. Your publish script must include the `logos/` folder.
4. After publishing, open one logo URL (`https://<user>.github.io/<repo>/logos/<slug>.png`) and confirm it returns HTTP 200.
The page shows the initial only when no logo file exists (with no `logo` set it also tries `logos/<slug>.png` itself).
