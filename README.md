# Nas (ناس): Policy Simulator for Jordan's Public Services

*Every policy leaves someone out. Nas shows you who, why, and how to fix it before you launch.*

AI Quest @ Al Hussein Technical University. A synthetic population of 1,000 Amman residents, AI-voiced,
run through ID renewal under any policy. The deterministic engine decides and searches; the AI translates,
explains and proposes; the engine verifies everything the AI proposes. See [CLAUDE.md](CLAUDE.md) for the full spec.

> Synthetic population, demo data, not real people.

## Run it

One server runs both the API and the UI:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- Open **http://localhost:8000** for the app (the static UI in [nas-frontend/](nas-frontend/) is served by FastAPI).
- http://localhost:8000/docs for the interactive API docs.
- Copy `.env.example` to `.env` (repo root) and add your own free Gemini and Groq keys (an OpenAI key is optional: set `OPENAI_MODEL_*` too).
- `pytest -q` runs the offline test suite (no AI calls).
- `DEMO_OFFLINE=1` in `.env`: cache + templates only, never a network call. `?offline=1` in the URL draws no map tiles.
- The UI still loads Leaflet, icons and fonts from CDNs, so vendor those before a fully offline demo.

## API (for the frontend)

Contract: [backend/app/models.py](backend/app/models.py). The frontend reads it only through [nas-frontend/api.js](nas-frontend/api.js).

| Method | Path | Body → Response |
|---|---|---|
| GET | `/population` | → `Citizen[]` (1,000) |
| GET | `/scenarios` | → `Scenario[]` (baseline = the 7 real CSPD offices, consolidate, digital_first, online_only, consolidate_digital_first = demo path, marked `demo: true`) |
| GET | `/sites`, `/areas` | → `Site[]`, `Area[]` |
| GET | `/assumptions` | → rows `{name, value, unit, tag, rationale, label_ar, label_en, rationale_ar, ...}` |
| GET | `/heroes` | → `Hero[]` `{id, note_ar, note_en, profile}`: hero citizens for the demo path |
| GET | `/llm/status` | → model chains, calls per model, which models are cooling down (rate limits) |
| POST | `/simulate` | `{policy}` → `SimResult` |
| POST | `/compare` | `{baseline, scenario}` → `CompareResult` (~50 ms) |
| POST | `/fixgrid` | `{baseline, scenario}` → `FixCandidate[]` top 3, engine only (~0.3 s) |
| POST | `/sensitivity` | `{baseline, scenario, fix?}` → `SensitivityResult` (~0.5 s, cached). Without `fix`, only the ranking is checked (`fix_checked: false`) |
| POST | `/policy/parse` | `{text, current_policy, lang}` → `ParseResult` (AI, 3-8 s) |
| POST | `/citizen/voice` | `{citizen_id, outcome}` → `{text_ar, summary_en, source}` (AI, ~5 s, cached) |
| POST | `/report` | `{compare_result, sensitivity}` → `{summary_ar, summary_en, source}` (AI) |
| POST | `/fixes` | `{baseline, scenario}` → `{fixes, source, ai_proposal}` (AI explanations + verified AI fix) |

Invalid policies (unknown site/area, bad hours, discounts outside 0-100) return **422** with a readable message.

**Group protections** (Policy fields, per citizen by tags): `appointment_exempt_groups`, `fee_discounts`, `home_visits`
`{groups, slots}`, `transport_vouchers` `[{groups, amount_jd}]`, `hybrid_pickup`. Home-visit outcomes have
`channel: "home_visit"`, `mode: "home"`; `kpis.n_home_visits` counts them.

## Data

| File | What | Source |
|---|---|---|
| `backend/app/data/population.json` | 1,000 synthetic citizens (Jordanian nationals 16+) across 22 GAM districts | `seed_census.py`, seed 42, quotas from *Amman in a Box*; targets vs results in `data/census/VALIDATION.md` |
| `backend/app/data/home_points.json` | residential street points (optional, places homes on real streets) | OpenStreetMap via Overpass, `fetch_map_data.py homes` |
| `backend/app/data/travel_matrix.json` | road km + car time, every citizen to every site and area centre | OSRM (OpenStreetMap), fetched once by `fetch_map_data.py` |
| `backend/app/data/anchors.json` | public figures with their status (ANCHORED / TEAM_CONFIRMED / CITED_UNVERIFIED) | desk research; checked sources only |
| `backend/app/data/sites.json` | the 7 real CSPD offices + 8 generic snap sites | cspd.gov.jo office list, located with OSM Nominatim |

Map data © OpenStreetMap contributors, ODbL.

## Scripts (run from `backend/`)

```bash
python -m app.data.fetch_map_data homes  # optional: OSM residential streets for home placement
python -m app.data.seed_census --install  # census-anchored population.json (1,000; --n to change)
python -m app.data.fetch_map_data matrix # re-fetch OSRM times after the population changes
python -m scripts.pick_heroes            # choose hero citizens -> scenarios/heroes.json
python -m scripts.find_ai_fix            # search for a verified AI fix for the demo path
python -m scripts.warm_cache             # warm the AI cache (online, after final scenario work; --parse-only for requests)
```
