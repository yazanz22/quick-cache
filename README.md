# Nas (ناس): Policy Simulator for Jordan's Public Services

*Every policy leaves someone out. Nas shows you who, why, and how to fix it before you launch.*

AI Quest @ Al Hussein Technical University. A synthetic population of 800 Amman residents, AI-voiced,
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

- Copy `.env.example` to `.env` (repo root) and add your own free Gemini and Groq keys.
- Open http://localhost:8000/ for the **debug page** (map, KPIs, fixes, robustness, voices, parse).
- Open http://localhost:8000/docs for the interactive API docs.
- `pytest -q` runs 22 offline tests (no AI calls).
- `DEMO_OFFLINE=1` in `.env`: cache + templates only, never a network call.

## API (for the frontend)

Types: [frontend/lib/types.ts](frontend/lib/types.ts) mirrors [backend/app/models.py](backend/app/models.py).

| Method | Path | Body → Response |
|---|---|---|
| GET | `/population` | → `Citizen[]` (800) |
| GET | `/scenarios` | → `Scenario[]` (baseline, move_to_abdali, digital_first, online_only, abdali_digital_first) |
| GET | `/sites`, `/areas` | → `Site[]`, `Area[]` |
| GET | `/sites/nearest?lat=&lng=` | → `Site` (snap a dragged office pin) |
| GET | `/assumptions` | → `AssumptionRow[]` (for AssumptionsTable) |
| GET | `/labels` | → Arabic/English labels for reasons, groups, modes, statuses, days |
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
| `backend/app/data/population.json` | 800 synthetic citizens | `seed.py`, seed 42, labelled assumptions + `anchors.json` |
| `backend/app/data/travel_matrix.json` | road km + car time, every citizen to every site and area centre | OSRM (OpenStreetMap), fetched once by `fetch_map_data.py` |
| `backend/app/data/bus_stops.json` | 131 mapped bus stops (map layer only) | OpenStreetMap via Overpass. Not used by the engine: coverage is too uneven. |
| `backend/app/data/anchors.json` | public statistics used by the seed | pending research; only entries with a real URL are used |

Map data © OpenStreetMap contributors, ODbL.

## Scripts (run from `backend/`)

```bash
python -m app.data.seed                  # regenerate population.json
python -m app.data.fetch_map_data matrix # re-fetch OSRM times after the population changes
python -m scripts.pick_heroes            # choose hero citizens -> scenarios/heroes.json
python -m scripts.find_ai_fix            # search for a verified AI fix for the demo path
python -m scripts.warm_cache             # warm the AI cache (online, after final scenario work)
```
