# Vendored front-end files

Local copies of everything the UI used to load from CDNs, so the demo runs with no internet
(together with `DEMO_OFFLINE=1` in `.env` and `?offline=1` in the URL for the map tiles).

| Folder | What | Source | Licence |
|---|---|---|---|
| `leaflet/` | Leaflet 1.9.4: `leaflet.js`, `leaflet.css`, `images/` | unpkg.com/leaflet@1.9.4/dist | BSD-2-Clause (`leaflet/LICENSE`) |
| `phosphor/` | Phosphor Icons 2.1.1, the two weights the UI uses: `regular/` (`ph`) and `fill/` (`ph-fill`), woff2 only | unpkg.com/@phosphor-icons/web@2.1.1/src | MIT (`phosphor/LICENSE`) |
| `fonts/` | IBM Plex Sans + IBM Plex Sans Arabic, weights 400-700, `arabic`, `latin` and `latin-ext` subsets only | Google Fonts CSS2 API | SIL OFL 1.1 (`fonts/OFL.txt`) |

To use another icon weight (e.g. `ph-bold`), copy `src/bold/style.css` and its `.woff2` from the same package
and add a `<link>` in `index.html`. Map tiles are not vendored (the OpenStreetMap tile policy forbids bulk downloads).
