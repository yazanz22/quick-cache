# Nas frontend (UI only)

A static, bilingual (Arabic RTL / English) frontend for the Nas policy simulator. No build step, no framework.
**It computes nothing.** Every number, outcome, fix and sentence comes from the backend described in `CLAUDE.md` §5 and §7.

```
nas-frontend/
├── index.html   # layout + all CSS (light/dark tokens, RTL, responsive)
├── config.js    # backend URL, timeouts, offline map, fallback areas/heroes  <- edit this
├── api.js       # the ONLY file that knows routes and JSON shapes            <- adapt this if the backend differs
├── i18n.js      # every UI string, ar + en
└── app.js       # UI logic: rendering, map, events, request ordering
```

## Run it

The backend serves this folder itself: start it (`uvicorn app.main:app --port 8000` from `backend/`) and open
**http://localhost:8000**. `config.js` then uses the page's own origin as the API.

To work on the UI separately, `python -m http.server 3000 --directory nas-frontend` also works (the backend's
CORS allows port 3000, and `config.js` falls back to http://localhost:8000). To point at another backend without
editing anything: `?api=http://192.168.1.20:8000`.

If the backend is down, the page shows a "can't reach the engine" screen with the URL it tried and a Retry button.

## What the UI calls

All bodies are JSON. Field names follow `backend/app/models.py` (CLAUDE.md §5).

| When | Call | Body | UI expects back |
|---|---|---|---|
| Page load | `GET /population` | | `Citizen[]` (or `{citizens: [...]}`). `tags` optional; derived if missing |
| Page load | `GET /sites` | | `[{id, name_ar, name_en, lat, lng, area}]` (or a dict keyed by id) |
| Page load | `GET /scenarios` | | `[{id, name_ar?, name_en?, description_ar?, description_en?, policy}]`, or a dict `{id: {...}}`, or `{id: Policy}`. The one with `id: "baseline"` is the baseline |
| Page load | `GET /assumptions` | | `[{name, value, tag, rationale, source, label_ar?, label_en?}]` or a dict `{NAME: {value, tag, rationale, source}}` |
| Page load, optional | `GET /areas` | | `[{id, name_ar, name_en, lat, lng}]`. 404 → uses `config.js` AREAS |
| Page load, optional | `GET /heroes` | | `[{id, note_ar, note_en}]` or `["c_0262", ...]`. 404 → uses `config.js` HERO_IDS |
| Any policy edit, pin drop (300 ms debounce) | `POST /compare` | `{baseline, scenario}` | `CompareResult` |
| A fix is applied (for the green "got better" rings) | `POST /compare` | `{baseline: <policy before fix>, scenario: <fix policy>}` | `CompareResult` |
| "Suggest fixes" | `POST /fixgrid` | `{baseline, scenario}` | `FixCandidate[]` (or `{fixes: [...]}`). Shown immediately |
| Right after `/fixgrid` | `POST /simulate` × each fix | `{policy}` | `SimResult`. Only `kpis` is used, for the before/after bars. Failure just hides the bars |
| Right after `/fixgrid` | `POST /fixes` | `{baseline, scenario}` | `{fixes: FixCandidate[], source?}`. Explanations are matched to grid fixes **by `id`**; one with `source: "ai_proposed"` becomes the AI card |
| After compare, and again once fixes exist | `POST /sensitivity` | `{baseline, scenario, fix}` | `SensitivityResult`. `fix` is `null` until fixes exist: the backend then checks the ranking only (`fix_checked: false`), so the badge shows "held X/6" before fixes too. `api.js` sends the fix's `policy` and maps the backend's `details[]` to `detail: [{key, factor, top2, fixHelps}]` for the per-run table |
| "Read it" (free text) | `POST /policy/parse` | `{text, current_policy, lang}` | `ParseResult` |
| Click a citizen | `POST /citizen/voice` | `{citizen_id, outcome}` (the engine's own `CitizenOutcome`, sent back untouched) | `{text_ar, source: "ai" \| "fallback"}`. On failure the UI shows a local template tagged "template" |
| "Write report" | `POST /report` | `{compare_result, sensitivity}` | `{summary_ar, summary_en, source}`. Newlines become paragraphs |

### Shapes the UI relies on

- `SimResult.kpis`: `pct_served`, `pct_hardship`, `pct_left_out` (0-100; 0-1 fractions are auto-scaled), `avg_hours_lost`, `avg_cost_jd`.
- `SimResult.by_group`: `{tag: {served, hardship, left_out}}` in percent. Any tag is shown; known ones get translated labels (`elderly, disabled, no_car, offline, low_income, worker, student`).
- `SimResult.outcomes[]`: `citizen_id, status, channel, channel_name_ar, channel_name_en, mode, bus_transfers, visit_day, travel_minutes, cost_jd, hours_lost, work_hours_missed, reasons[]`.
- `CompareResult`: `baseline`, `scenario`, `flipped_worse[]`, `flipped_better[]`, `worst_groups[]`. Deltas are recomputed in the UI from the two `kpis`.
- `FixCandidate`: `id, title_ar, title_en, policy, source, left_out_drop, hardship_drop` (percentage points), `explanation_ar/_en` (may be null). Optional `explanation_source: "ai" | "fallback"` per fix; otherwise the `/fixes` response's `source` is used for the tag.
- `ParseResult`: `status: "ok" | "unsupported"`, `policy`, `changes_ar[]`, `changes_en[]`, `message_ar`, `message_en`.
- Reason codes and modes are the enums from §5; their labels live in `i18n.js` (`r_TOO_FAR`, `m_bus`, ...).

### What the UI sends as a Policy

Exactly §5's `Policy`. When an office pin is dragged it snaps to the nearest site and sets `site_id`, `id = "office_<area>"`, `name_ar`, `name_en` from `/sites`. Mobile units are `{area, day, open, close}`. Days are `sat..fri`, times `HH:MM`.

## If the backend's shapes differ

Change `api.js` only. Each endpoint function returns the normalised shape above; `app.js` never touches raw responses except to pass `outcome` and `compare_result` back to the AI routes unchanged.

## Notes

- Requests that come back out of order are ignored (only the latest `/compare` wins).
- Language and theme are remembered in `localStorage` (wrapped in try/catch).
- Needs internet for map tiles (OpenStreetMap), fonts (Google Fonts), Leaflet and icons (unpkg). For the venue: set `OFFLINE_MAP: true` (or open with `?offline=1`) to draw areas without tiles, and vendor the three CDN files if wifi is unreliable.
