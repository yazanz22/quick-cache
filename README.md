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
| GET | `/roads` | → `Road[]` `{id, name_ar, name_en, km, osm_ways, lines}`: the 18 closable major roads with map geometry |
| POST | `/daily` | `{closed_roads}` → `DailyResult`: every citizen's everyday trip (work, university, hospital) with the roads closed vs open: per person, group, purpose |
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

Invalid policies (unknown site/area/road, bad hours, discounts outside 0-100) return **422** with a readable message.

**Group protections** (Policy fields, per citizen by tags): `appointment_exempt_groups`, `fee_discounts`, `home_visits`
`{groups, slots}`, `transport_vouchers` `[{groups, amount_jd}]`, `hybrid_pickup`. Home-visit outcomes have
`channel: "home_visit"`, `mode: "home"`; `kpis.n_home_visits` counts them.

**Road closures:** `Policy.closed_roads` lists road ids from `/roads`. Trips that used a closed road take its detour
on top of the OSRM time and distance; every outcome carries `detour_minutes` / `detour_road`, and `kpis` carry
`n_detour` (citizens whose trip got longer) and `avg_detour_min`. With several roads closed a trip takes the largest
single-road detour (a lower bound: closing more roads can never make a trip faster). Detours are calibrated per road
against TomTom's measured road speeds (`road_calibration.json`); TomTom has no traffic data for Amman, so congestion
on the alternative roads is not modelled and the delays are minimums.
Every AI endpoint always answers within ~17 s (`LLM_TOTAL_BUDGET_S`, under the frontend's 20 s timeout): AI text, or a template with `source: "fallback"`.
Call `/fixgrid` first and render immediately, then `/fixes` to fill explanations and maybe add the AI fix.
`ai_proposal.status` says what happened to the AI's own idea ("shown", "hidden_not_better", ...), for an honest UI line.

## Data

| File | What | Source |
|---|---|---|
| `backend/app/data/population.json` | 1,000 synthetic citizens (Jordanian nationals 16+) across 22 GAM districts | `seed_census.py`, seed 42, quotas from *Amman in a Box*; targets vs results in `data/census/VALIDATION.md` |
| `backend/app/data/home_points.json` | residential street points (optional, places homes on real streets) | OpenStreetMap via Overpass, `fetch_map_data.py homes` |
| `backend/app/data/travel_matrix.json` | road km + car time, every citizen to every site and area centre | OSRM (OpenStreetMap), fetched once by `fetch_map_data.py` |
| `backend/app/data/roads.json` | 18 closable major roads (Arabic/English names, OSM names, simplified geometry) | OpenStreetMap via Overpass, `fetch_roads.py` |
| `backend/app/data/road_deltas.json` | extra seconds/metres per citizen-destination trip when each road is closed | our own routing on the OSM road network, `fetch_roads.py build` |
| `backend/app/data/road_calibration.json` | per-road factor on detour time (TomTom detour / ours on 15 sampled trips) | TomTom Routing API, `scripts/calibrate_roads.py` |
| `backend/app/data/hubs.json` | 25 everyday-trip destinations: job areas, universities, public hospitals (weights = ASSUMPTION) | OSM Nominatim |
| `backend/app/data/daily_trips.json` | one regular trip per citizen (SYNTHETIC) | `seed_daily.py`, seed 42 |
| `backend/app/data/hub_matrix.json` | road km + car time, every citizen to every hub | OSRM, `fetch_map_data.py hubs` |
| `backend/app/data/anchors.json` | public figures with their status (ANCHORED / TEAM_CONFIRMED / CITED_UNVERIFIED) | desk research; checked sources only |
| `backend/app/data/sites.json` | the 7 real CSPD offices + 8 generic snap sites | cspd.gov.jo office list, located with OSM Nominatim |

Map data © OpenStreetMap contributors, ODbL.

## Scripts (run from `backend/`)

```bash
python -m app.data.fetch_map_data homes  # optional: OSM residential streets for home placement
python -m app.data.seed_census --install  # census-anchored population.json (1,000; --n to change)
python -m app.data.fetch_map_data matrix # re-fetch OSRM times after the population changes
python -m app.data.seed_daily           # everyday trips -> daily_trips.json (re-run after the population changes)
python -m app.data.fetch_map_data hubs   # OSRM times to the everyday-trip hubs
python -m app.data.fetch_roads network   # one-time OSM road network download (~28 MB, gitignored)
python -m app.data.fetch_roads build     # roads.json + road_deltas.json (~40 s; re-run after the population changes)
python -m scripts.road_impact            # per-road closure impact on baseline / consolidate / demo path
python -m scripts.calibrate_roads        # TomTom calibration of detours (needs TOMTOM_API_KEY; ~500 calls, cached)
python -m scripts.pick_heroes            # choose hero citizens -> scenarios/heroes.json
python -m scripts.find_ai_fix            # search for a verified AI fix for the demo path
python -m scripts.warm_cache             # warm the AI cache (online, after final scenario work; --parse-only for requests)
```
