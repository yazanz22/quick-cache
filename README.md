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
- `pytest -q` runs the offline test suite (no AI calls). `tests/test_demo.py` pins the demo numbers: if it fails, update HANDOFF §6, re-pick heroes and re-warm the cache.
- `DEMO_OFFLINE=1` in `.env`: cache + templates only, never a network call. `?offline=1` in the URL draws no map tiles.
- Leaflet, icons and fonts are vendored in `nas-frontend/vendor/`, so with both switches on the demo needs no internet.
- Production: https://nas-rbo5.onrender.com (Render free plan from `render.yaml`; sleeps when idle, ~30-60 s to wake).
  Deploy from the Render dashboard (Manual Deploy → latest commit) if a push doesn't trigger one.

## What an official can change

Offices (open, close or move one at any of 15 sites, hours per day, late Thursday, wheelchair access), online on/off/only,
appointments, mobile units (area, day, hours), the fee, the number of visits, and **protections for groups**: walk-in without
an appointment, fee exemptions or discounts, transport vouchers, capped home visits, and "apply online, collect in person".
All of it from the policy panel or in Arabic/English free text. Anything else (e.g. extra staff, road closures) gets an
honest "not supported yet" with the closest supported change.

## API (for the frontend)

Contract: [backend/app/models.py](backend/app/models.py). The frontend reads it only through [nas-frontend/api.js](nas-frontend/api.js).

| Method | Path | Body → Response |
|---|---|---|
| GET | `/population` | → `Citizen[]` (1,000) |
| GET | `/scenarios` | → `Scenario[]` (baseline = the 7 real CSPD offices, consolidate, digital_first, online_only, consolidate_digital_first = demo path, marked `demo: true`) |
| GET | `/sites`, `/areas` | → `Site[]`, `Area[]` |
| GET | `/assumptions` | → rows `{name, value, unit, tag, rationale, source, label_ar, label_en, rationale_ar, source_ar, perturbed_in_robustness_check}` (all 26 tagged ASSUMPTION; `source` = short context note or null) |
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

**Group protections** (Policy fields, per citizen by tags; groups = `elderly, disabled, no_car, offline, low_income, worker,
student`): `appointment_exempt_groups`, `fee_discounts` `{group: %}`, `home_visits` `{groups, slots}`, `transport_vouchers`
`[{groups, amount_jd}]`, `hybrid_pickup`. Home-visit outcomes have `channel: "home_visit"`, `mode: "home"`;
`kpis.n_home_visits` counts them. They are manual levers only, not part of the `/fixgrid` search.

## Data

| File | What | Source |
|---|---|---|
| `backend/app/data/population.json` | 1,000 synthetic citizens (Jordanian nationals 16+) across 22 GAM districts | `seed_census.py`, seed 42, quotas from *Amman in a Box*; targets vs results in `data/census/VALIDATION.md` |
| `backend/app/data/home_points.json` | residential street points (optional, places homes on real streets) | OpenStreetMap via Overpass, `fetch_map_data.py homes` |
| `backend/app/data/travel_matrix.json` | road km + car time, every citizen to every site and area centre | OSRM (OpenStreetMap), fetched once by `fetch_map_data.py` |
| `backend/app/data/anchors.json` | public figures with their status (ANCHORED / TEAM_CONFIRMED / CITED_UNVERIFIED) | desk research, each figure with its verification status (documentation; not read at runtime) |
| `backend/app/data/sites.json` | the 7 real CSPD offices + 8 generic snap sites | cspd.gov.jo office list, located with OSM Nominatim |

Map data © OpenStreetMap contributors, ODbL.

## What is real and what is assumed

One page, slide-ready. Status words as in `anchors.json`: **ANCHORED** = the team opened the source and checked it;
**TEAM_CONFIRMED** = confirmed by the team, link not recorded yet; **CITED** = quoted by our AI-assisted desk research
(*Amman in a Box*), not verified by us.

**Real (public data)**
- The **7 CSPD offices in Amman** with their addresses (cspd.gov.jo office list, ANCHORED), placed with OpenStreetMap Nominatim: `sites.json`.
- **Road distances and car times** from OSRM on OpenStreetMap data (`travel_matrix.json`); homes sit on real OSM residential streets.
- **MoDEE 2024 ICT survey** (ANCHORED): 95.6% of individuals in Jordan use the internet, 99% of Amman households have a smartphone, 38.1% have used an e-government service.
- The **JD 2 ID-renewal fee** and the **08:30-15:30 Sun-Thu office hours** (TEAM_CONFIRMED).

**Quoted, not verified (CITED)**
- **2015 census district shares** (22 GAM districts): they decide where the 1,000 synthetic citizens live.
- Sex ratio, disability rates, labour force and unemployment, informality, the 8.3% poverty rate, the 14% public-transport share, digital skills, household size (targets vs results in `data/census/VALIDATION.md`).

**Assumed (labelled, frozen before any scenario ran)**
- **All 26 engine constants** in `sim/assumptions.py` (service time, bus speed and waits, taxi fares, hardship threshold, ...). Three of them (`SERVICE_MINUTES`, `BUS_WAIT_PLUS_TRANSFER_MIN`, `HARDSHIP_THRESHOLD`) are moved by ±20% in the robustness check: the worst-group ranking holds 6/6.
- The **65+ share** (~6.5% of adults), the **wheelchair share** (11 of 1,000), **income bands** (low = bottom 30% of synthetic per-capita income), **who has a helper** and when they are free (16:00 on workdays), and **bus transfers** (0 within an area, 1 across areas, 2 between east and west Amman).

On stage: *"Where we found published figures, we used them and say so; everything else is a labelled assumption, frozen before we ran any scenario."*

### What the groups mean

The engine groups are tags derived from each synthetic citizen (`seed.derive_tags`), not census categories:

| Group | Means | People (of 1,000) |
|---|---|---|
| `elderly` | aged 65+ | 65 |
| `disabled` | limited mobility or a wheelchair user (mobility only: **not** the 10.4% Washington Group rate, which also counts seeing, hearing, memory...) | 69 (58 limited, 11 wheelchair) |
| `low_income` | bottom 30% of synthetic per-capita income (**not** the 8.3% below the poverty line) | 300 |
| `offline` | no smartphone, or low digital skills | 204 |
| `no_car` | does not drive their own car | 534 |
| `worker` | employed, works Sun-Thu shifts | 320 |
| `student` | aged 18-24 and not working | 164 |

On-stage line: *"'Disabled' here means someone who can't easily walk to a bus stop, and 'low income' means the poorest 30% of our synthetic residents. These are simulation groups, not official statistics."*
(Arabic: «ذوو الإعاقة هنا هم من لديهم صعوبة في الحركة أو يستخدمون كرسياً متحركاً، ومحدودو الدخل هم أفقر 30% من سكاننا الافتراضيين. هذه فئات للمحاكاة، وليست إحصاءات رسمية.»)

## Scripts (run from `backend/`)

```bash
python -m app.data.fetch_map_data homes  # optional: OSM residential streets for home placement
python -m app.data.seed_census --install  # census-anchored population.json (1,000; --n to change)
python -m app.data.fetch_map_data matrix # re-fetch OSRM times after the population changes
python -m scripts.pick_heroes            # choose hero citizens -> scenarios/heroes.json
python -m scripts.find_ai_fix            # search for a verified AI fix for the demo path
python -m scripts.warm_cache             # warm the AI cache (online, after final scenario work; --parse-only for requests)
pytest -q                                # offline tests, incl. the demo guard (test_demo.py)
```

Project state and decisions for the next person (or AI session): [HANDOFF.md](HANDOFF.md).
