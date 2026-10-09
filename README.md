# Nas (ناس): Policy Simulator for Jordan's Public Services

*Every policy leaves someone out. Nas shows you who, why, and how to fix it before you launch.*

AI Quest @ Al Hussein Technical University. A synthetic population of 1,000 Amman residents, AI-voiced,
run through ID renewal under any policy. The deterministic engine decides and searches; the AI translates,
explains and proposes; the engine verifies everything the AI proposes. See [CLAUDE.md](CLAUDE.md) for the full spec.

> Synthetic population, demo data, not real people.

## Run the backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- Copy `.env.example` to `.env` (repo root) and add your own free Gemini and Groq keys (an OpenAI key is optional: set `OPENAI_MODEL_*` too).
- Open http://localhost:8000/ for the **debug page** (map, KPIs, fixes, robustness, voices, parse).
- Open http://localhost:8000/docs for the interactive API docs.
- `pytest -q` runs 25 offline tests (no AI calls).
- `DEMO_OFFLINE=1` in `.env`: cache + templates only, never a network call.

## Run the frontend

The UI is a static app in [nas-frontend/](nas-frontend/) (no build step; see its README). With the backend running:

```bash
python -m http.server 3000 --directory nas-frontend
```

Open http://localhost:3000 (`?api=http://<host>:8000` for another backend, `?offline=1` for no map tiles).
It still loads Leaflet, icons and fonts from CDNs, so vendor those before an offline demo.

## API (for the frontend)

Types: [frontend/lib/types.ts](frontend/lib/types.ts) mirrors [backend/app/models.py](backend/app/models.py).

| Method | Path | Body → Response |
|---|---|---|
| GET | `/population` | → `Citizen[]` (1,000) |
| GET | `/scenarios` | → `Scenario[]` (baseline = the 7 real CSPD offices, consolidate, digital_first, online_only, consolidate_digital_first = demo path, marked `demo: true`) |
| GET | `/sites`, `/areas` | → `Site[]`, `Area[]` |
| GET | `/sites/nearest?lat=&lng=` | → `Site` (snap a dragged office pin) |
| GET | `/assumptions` | → `AssumptionRow[]` (for AssumptionsTable) |
| GET | `/heroes` | → `[{id, note_ar, note_en, profile}]` hero citizens for the demo path |
| GET | `/labels` | → Arabic/English labels for reasons, groups, modes, statuses, days |
| GET | `/llm/status` | → model chains, calls per model, which models are cooling down (rate limits) |
| POST | `/simulate` | `{policy}` → `SimResult` |
| POST | `/compare` | `{baseline, scenario}` → `CompareResult` (~50 ms) |
| POST | `/fixgrid` | `{baseline, scenario}` → `FixCandidate[]` top 3, engine only (~0.3 s) |
| POST | `/sensitivity` | `{baseline, scenario, fix}` → `SensitivityResult` (~0.5 s, cached) |
| POST | `/policy/parse` | `{text, current_policy, lang}` → `ParseResult` (AI, 3-8 s) |
| POST | `/citizen/voice` | `{citizen_id, outcome}` → `{text_ar, summary_en, source}` (AI, ~5 s, cached) |
| POST | `/report` | `{compare_result, sensitivity}` → `{summary_ar, summary_en, source}` (AI) |
| POST | `/fixes` | `{baseline, scenario}` → `{fixes, source, ai_proposal}` (AI explanations + verified AI fix) |

Invalid policies (unknown site/area, bad hours) return **422** with a readable message.
Every AI endpoint always answers: AI text, or a template with `source: "fallback"`. Show a small "template" tag then.
Call `/fixgrid` first and render immediately, then `/fixes` to fill explanations and maybe add the AI fix.
`ai_proposal.status` says what happened to the AI's own idea ("shown", "hidden_not_better", ...), for an honest UI line.

## Data

| File | What | Source |
|---|---|---|
| `backend/app/data/population.json` | 1,000 synthetic citizens (Jordanian nationals 16+) across 22 GAM districts | `seed_census.py`, seed 42, quotas from *Amman in a Box*; targets vs results in `data/census/VALIDATION.md` |
| `backend/app/data/home_points.json` | residential street points (optional, places homes on real streets) | OpenStreetMap via Overpass, `fetch_map_data.py homes` |
| `backend/app/data/travel_matrix.json` | road km + car time, every citizen to every site and area centre | OSRM (OpenStreetMap), fetched once by `fetch_map_data.py` |
| `backend/app/data/bus_stops.json` | 131 mapped bus stops (map layer only) | OpenStreetMap via Overpass. Not used by the engine: coverage is too uneven. |
| `backend/app/data/anchors.json` | public statistics used by the seed | pending research; only entries with a real URL are used |

Map data © OpenStreetMap contributors, ODbL.

## Scripts (run from `backend/`)

```bash
python -m app.data.fetch_map_data homes  # optional: OSM residential streets for home placement
python -m app.data.seed_census --install  # census-anchored population.json (1,000; --n to change)
python -m app.data.seed                  # old 8-area generator (superseded)
python -m app.data.fetch_map_data matrix # re-fetch OSRM times after the population changes
python -m scripts.pick_heroes            # choose hero citizens -> scenarios/heroes.json
python -m scripts.find_ai_fix            # search for a verified AI fix for the demo path
python -m scripts.warm_cache             # warm the AI cache (online, after final scenario work)
```
