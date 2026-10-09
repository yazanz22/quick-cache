# HANDOFF: Nas (ناس), state of the project

Read this first in a new context window, then `CLAUDE.md` (the full spec). Last updated 2026-10-09 (evening, Amman).

## 1. What Nas is (one paragraph)
A "wind tunnel" for public services in Amman, built for AI Quest @ Al Hussein Technical University.
1,000 **synthetic citizens, AI-voiced** (never say "1,000 AI citizens") go through **ID renewal** under any policy.
The **deterministic engine** decides every outcome and number, searches a grid of fixes, and runs a ±20%
robustness check. The **AI** only translates (free text → policy), voices citizens (in فصحى), writes the report,
and explains/proposes fixes. **The engine verifies everything the AI proposes.** Every AI task has a template fallback.

## 2. Where things run
| What | Where |
|---|---|
| Repo | https://github.com/yazanz22/quick-cache (branch `main`; push directly to main) |
| Local app (UI + API, one server) | from `backend/`: `.venv/Scripts/python -m uvicorn app.main:app --port 8000` → **http://localhost:8000** (API docs at `/docs`) |
| Production | **https://nas-rbo5.onrender.com** (Render free web service from `render.yaml`, auto-deploys on push to `main`) |
| Tests | from `backend/`: `.venv/Scripts/python -m pytest -q` → 53 passing, all offline (no AI calls) |
| Python | local venv is Python 3.14 (`backend/.venv`); Render uses 3.12.7 |

Render notes: the free plan sleeps after ~15 min idle; the first visit takes ~30-60 s to wake (the UI shows
"can't reach the engine" → press Retry). At start-up the server pre-computes the demo path (`sim/warmup.py`)
so the first real request is fast. Secrets (GEMINI/GROQ/OPENAI keys) are set in the Render dashboard
(Environment tab), never in the repo. New AI answers generated on Render are lost on restart; the committed cache persists.

## 3. Hard rules (from the user and CLAUDE.md)
- **Never add a co-author / "Co-Authored-By" line** to commits or PRs. Small, focused commits pushed to `main`.
- **Freeze rule:** never change values in `backend/app/sim/assumptions.py` to make a story appear. Change scenarios instead.
  (Assumptions were committed as frozen in `6feaa3c` *before* any scenario ran; that commit is the proof.)
- **Frontend computes nothing.** Backend shapes are adapted only in `nas-frontend/api.js`; UI strings live in `nas-frontend/i18n.js`;
  edit `app.js` / `index.html` only for real UI bugs.
- **`backend/app/models.py` is the API contract.** If you change it, check `nas-frontend/api.js` in the same commit.
- Every AI call goes through `llm/client.py` + `llm/cache.py` + `llm/checks.py`, with a template in `llm/fallbacks.py`.
- **Auto mode blocks running code a teammate wrote** (e.g. `seed_census.py`), even with the user's approval. Ask the user to run it in their terminal.
- Never paste API keys in chat; the user edits `.env` (repo root, gitignored) themselves.
- Synthetic data only; never present synthetic numbers as real statistics.
- Don't loop AI calls during development (free-tier quotas, see §8).

## 4. Repository layout (what matters)
```
CLAUDE.md, README.md, HANDOFF.md, render.yaml, .env.example
"Amman in a Box_ A Verified Statistical Blueprint for Policy Simulation.md"   # teammate's desk research (source for seed_census)
backend/
  app/main.py            # FastAPI: routers, CORS (only for :3000), serves nas-frontend/ at /, start-up warm-up
  app/config.py          # loads repo-root .env (LLM_*, MODEL_*, DEMO_OFFLINE ...)
  app/models.py          # all Pydantic schemas (contract)
  app/routes/sim_routes.py  # /population /scenarios /sites /areas /roads /daily /heroes /assumptions /simulate /compare /fixgrid /sensitivity
  app/routes/llm_routes.py  # /policy/parse /citizen/voice /report /fixes /llm/status
  app/sim/   assumptions.py (frozen), assumption_labels.py (ar/en text only), travel.py, engine.py, compare.py,
             fixgrid.py, sensitivity.py, validate.py, warmup.py, world.py
  app/llm/   client.py, prompts.py, cache.py, fallbacks.py, checks.py, tasks.py
  app/data/  population.json (1,000), travel_matrix.json (OSRM), home_points.json (OSM streets), sites.json (15),
             areas.json (8), anchors.json, seed_census.py (+ census/ outputs), seed.py (shared helpers),
             fetch_map_data.py, fetch_roads.py, roads.json (18 roads), road_deltas.json, road_calibration.json,
             hubs.json, seed_daily.py, daily_trips.json, hub_matrix.json (everyday trips),
             _raw/ (gitignored OSM road network), scenarios/*.json (+ heroes.json, demo_requests.json)
  scripts/   pick_heroes.py, find_ai_fix.py, warm_cache.py, road_impact.py, calibrate_roads.py
  cache/     committed AI cache: parse 17, voice 10, report 3, fixes 2
  tests/     test_engine.py, test_fixgrid.py, test_llm.py, test_roads.py
nas-frontend/  index.html, config.js, api.js, i18n.js, app.js, README.md   # static, no build step
```

## 5. Data (what is real and what is assumed)
- **Population** (`population.json`): 1,000 synthetic Jordanian nationals aged 16+ across 22 GAM districts, generated by the
  teammate's `seed_census.py --install` (quotas from the research doc; targets vs results in `data/census/VALIDATION.md`).
  Each citizen maps to one of 8 engine areas (`areas.json`: downtown, abdali, jabal_al_hussein, marka, wehdat, tabarbour, sweileh, khalda).
  Homes sit on real OSM residential streets (`home_points.json`). The user ran the generator by hand (auto mode blocked it).
- **Travel times** (`travel_matrix.json`): real road distances/free-flow car times from the public OSRM server, fetched once,
  citizen → each of 15 sites and 8 area centres. `TRAFFIC_FACTOR` 1.6 (assumption) converts free-flow to daytime.
  Re-fetch after any population change: `python -m app.data.fetch_map_data matrix`.
- **Sites** (`sites.json`): the **7 real CSPD offices in Amman** (Tabarbour head office, Jabal Amman, Marka, Sweileh,
  Jabal Al-Hussein, Tla' Al-Ali, Wadi Al-Seer; addresses from cspd.gov.jo, located with OSM Nominatim, precision recorded, `real: true`)
  + 8 generic snap sites, one per area.
- **Hours** 08:30-15:30 Sun-Thu (CSPD's published hours; a Fri/Sat 10-14 line is not modelled: may be contact-centre hours).
- **Fee** JD 2: confirmed by the team (`anchors.json` status TEAM_CONFIRMED). The research's "JD 1" is for a different CSPD service.
- **anchors.json**: only MoDEE 2024 internet use (95.6%) and e-gov use (38.1%) are verified (ANCHORED); other research figures
  are CITED_UNVERIFIED. On stage say "anchored to published figures from our desk research", not "verified official statistics".
- OSM bus stops were tested and dropped (coverage too uneven: would unfairly penalise east Amman). Bus walk time stays an assumption.

## 6. Scenarios and demo numbers
Presets in `backend/app/data/scenarios/` (the demo one has `"demo": true`; scripts/tests find it by that flag):
| id | policy | served / hardship / left out | worse off |
|---|---|---|---|
| `baseline` | 7 real offices, 08:30-15:30 Sun-Thu, walk-in, online on | 88.4 / 11.5 / 0.1 | – |
| `consolidate` | keep only Tabarbour + Jabal Amman | 85.0 / 14.4 / 0.6 | 36 |
| `digital_first` | all 7 close 13:00 + online appointments | 79.6 / 20.0 / 0.4 | 91 |
| `online_only` | online only | 79.6 / 12.1 / 8.3 | 128 |
| **`consolidate_digital_first`** (demo) | consolidate + digital first | **79.6 / 19.5 / 0.9** | **93** |

Demo path facts: elderly hardship 40% → 85%, offline 56% → 96%; worst groups **elderly, offline**; robustness **6/6** (elderly stable top),
also shown *before* fixes (ranking-only). Engine top fix: Saturday vans Sweileh + Downtown (−0.8 left out, −10.5 hardship).
**Verified AI fix** (cached): Saturday vans in Sweileh, Wehdat and Downtown (−0.8 / −11.9), max 3 changes enforced.
Applying it: served 92.3%, 130 citizens better off.
The demo is mostly **yellow (hardship)**, not red; only `online_only` makes red spread. Adjust the CLAUDE.md §13 wording if needed.

**Heroes** (`heroes.json`, made by `scripts/pick_heroes.py`, factual `profile` per hero; all four get worse under the demo and recover with the top fix):
c_0028 Dana (71f, no car/smartphone, son helps), c_0031 Mohammad (67m, wheelchair, son helps),
c_0837 Bilal (38m, 07:00-16:00 shift, no helper), c_0020 Amina (63f, low digital literacy, no helper).

**Rehearsed requests** (`demo_requests.json`, all cached): the on-stage sentence
"خلّوا الكاونترات تسكر الساعة 1 الظهر، وما حدا يراجع المكتب إلا بموعد مسبق أونلاين" applied to `consolidate` parses to exactly
`consolidate_digital_first`; plus close offices on Thursday (ar/en), close/reopen Marka, online-only + Saturday van in Wehdat,
double the fee, two visits, and two unsupported ones (free for over-65s, ar/en).

## 7. Engine decisions worth knowing (deviations from CLAUDE.md, all deliberate)
- Option choice ranks **best status first** (served > hardship), then burden. Otherwise a citizen with a car would be pushed
  into "a relative did it online". (The teammate's frontend prompt called this a "known issue": it is already fixed.)
- `SensitivityResult` has `stable_top2` and `fix_checked`; `/sensitivity` accepts no fix (ranking-only), so the badge works before fixes.
  With a fix that doesn't move left-out, it is judged on left-out + hardship.
- AI fix proposals are capped at 3 changes (`count_changes`) so they stay comparable to grid pairs.
- Office ids need not be unique (the UI renames a dragged office `office_<area>`, and two real offices share area `khalda`).
- Performance: simulate ~50 ms, fix grid ~0.3 s locally (~5 s on Render), robustness ~0.5 s locally (~3.5 s on Render, cached after).

## 8. AI layer
- Providers: Gemini (primary) → Groq → OpenAI (`LLM_FALLBACK_PROVIDER=groq,openai`), then templates. Providers without a key are skipped.
- **Gemini free tier = ~20 requests/day per model**, so each slot is a comma-separated **model chain** in `.env`:
  `MODEL_FAST` (voices) = gemini-3.8/3.7/3.6/3.5-flash (no lite: its Arabic had typos), `MODEL_SMART` = 3.6/3.7/3.5-flash + 3.5/3.1-flash-lite,
  `GROQ_MODEL_FAST` empty on purpose (Groq Arabic is weak), `GROQ_MODEL_SMART` = gpt-oss-120b/20b, qwen3.8-27b,
  `OPENAI_MODEL_*` = gpt-4.1-mini, gpt-5.4-mini (**the OpenAI key has no credits**; it's benched automatically).
- Limited models go on cooldown (daily limit → until ~08:00 UTC; per-minute/overload → 30-65 s). `GET /llm/status` shows them.
- All attempts for one request share **17 s** (`LLM_TOTAL_BUDGET_S`), under the frontend's 20 s timeout.
- **Voices are in فصحى (Modern Standard Arabic)**, a team decision (CLAUDE.md updated). Helper words are stored in dialect in the
  population and mapped to فصحى (بنتي→ابنتي, أخوي→أخي, أبوي→أبي, صاحبي→صديقي). Voice checks reject numbers not in the facts,
  people other than the helper, "ليرة", a helper word missing its possessive, and known misspellings.
- Cache key = sha256(task + inputs), no provider/model; voice inputs include `"register": "msa"`. `DEMO_OFFLINE=1` = cache + templates only
  (verified: the whole demo path works offline).
- Gemini daily quota resets ~10:00 Amman time. Don't burn it in loops.

## 9. Frontend ↔ backend
- FastAPI serves `nas-frontend/` at `/` (mounted after the API routes; a test checks routes still win). `config.js` uses the page's
  own origin as the API (falls back to http://localhost:8000 when opened on :3000). `?api=<url>` and `?offline=1` (no map tiles) work.
- `api.js` adaptations: `/sensitivity` sends the fix's `policy`; backend `details[]` → UI `detail[]` rows.
- Verified end to end, locally and on Render, in Arabic and English: presets, map recolour + rings, hero cards with AI voices, fixes +
  AI fix + apply, robustness badge/table, free-text parse (demo sentence matches the preset exactly; unsupported message), report,
  backend-down error screen + Retry, `?offline=1`, dragging an office pin.

## 10. Open items / known caveats
1. **3 voices still use the template**: Bilal (c_0837) and Amina (c_0020) *after the engine's top grid fix* (the demo applies the
   AI fix, so they rarely show), and the road-closure voice (Maher c_0213, Queen Rania St closed; the template already names the
   road and the extra minutes). After the Gemini reset: from `backend/`, `.venv/Scripts/python -m scripts.warm_cache`, then commit `backend/cache/`.
2. **Fully offline demo**: the UI still loads Leaflet, Phosphor icons and Google Fonts from CDNs. Vendor them into `nas-frontend/` before a no-wifi demo.
3. **Native-speaker review** of the cached voices: the user said leave it.
4. Staff / operating-cost readout: **ruled out of scope** by the user (on stage: "operating cost is the next module").
5. `app.js` has its own *dialect* voice template (`fallbackVoiceAr`), used only if `/citizen/voice` fails outright. Our backend
   always answers within 17 s (AI or فصحى template), so it should never show; left as is (frontend rules).
6. The public URL can spend the free AI quota; share it only with judges/team.

## 11. Road closures + everyday trips (DONE, 2026-10-09)
A policy lever `Policy.closed_roads` (ids from `GET /roads`): 18 major roads, all verified in OSM by their Arabic `name`:
Airport Rd (to the airport), Zahran, Queen Rania, Mecca, Medina, Wasfi Al-Tal (Gardens), Prince Hashem, Al-Quds, Army,
Al-Hurriya, King Abdullah II, Jordan St, Al-Istiqlal, Al-Shaheed, Amman-Zarqa Hwy, Al-Salt St, Yajouz, Prince Al-Hasan.
(Cairo St was dropped by the user: not a major road.)
- **Routing:** `app/data/fetch_roads.py network` downloads the drivable OSM network once (gitignored `_raw/`); `build` routes
  every citizen to the 23 service destinations and to their own everyday-trip hub twice (pure-Python Dijkstra): all roads
  open, and with the road's ways removed. The difference goes in `road_deltas.json`; the engine adds it on top of the OSRM
  time/distance, so open-road numbers never change. Same-named streets in Zarqa and south of Amman are excluded.
  Several closures = the largest single-road detour per trip (a lower bound). Homes that only open onto the road keep access.
- **Calibration (TomTom):** our default class speeds made detours too short (the parallel service roads looked free).
  `scripts/calibrate_roads.py` rebuilds 15 sampled trips per road on TomTom (supportingPoints = our open and detour paths)
  and sets factor = TomTom detour / ours (1.2-3.9, e.g. Airport Rd 2.41: 6.1 → 14.7 min). 483 calls, cached in
  `_raw/tomtom/`; key `TOMTOM_API_KEY` in `.env` (free, Routing API). **TomTom has no traffic data for Amman** (no-traffic =
  historic = live at 03:00 and 08:00; Dubai varies), so congestion from diverted traffic is NOT modelled: delays are minimums.
  The only API with Amman traffic we know is Google (needs a billing account; can't avoid a road, but could time our detour
  paths through via-waypoints). Not done: the user's call.
- **Everyday trips (what the user asked for: "how closures affect x person going to work"):** `hubs.json` = 25 OSM-located
  destinations (14 job areas incl. Sahab and the airport, 7 universities incl. Petra/Zaytoonah/Isra on Airport Rd, 4 public
  hospitals; weights = ASSUMPTION). `seed_daily.py` (seed 42) gives each citizen one regular trip: 320 workers → job hub and
  164 students → university (Sun-Thu, gravity draw), 464 other adults 25+ → nearest hospital weekly; under-18s walk to school.
  `sim/daily.py` + `POST /daily {closed_roads}`: per person one-way minutes open/closed, extra hours and JD a week, level
  (none / minor 1-5 / moderate 5-15 / severe 15+ min); totals by group and purpose. Mode from the profile (car, else bus,
  wheelchair: helper's car or taxi). Bus detours use distance only, so calibration doesn't change them.
- **Numbers (calibrated):** everyday trips: Prince Al-Hasan 158 people longer (24 severe), Queen Rania 115 (38 severe, avg +11
  min, worst +50), King Abdullah II 92, Medina 77, Airport Rd 38 (8 severe: airport workers, Isra/Zaytoonah students, worst
  +55 min). ID renewal (`scripts/road_impact.py`): baseline + Queen Rania 7 citizens to hardship; demo path + Prince Al-Hasan
  2 more left out. Single closures move few ID outcomes; everyday trips are where the story is.
- **UI:** road chips in the policy panel, closed roads red on the map, a "trips made longer" line under the KPIs, an
  "Everyday trips" section in the Impact panel, a map mode toggle "ID renewal | Daily trips" (dots by delay), the daily trip
  and the detour on the citizen card. Voices mention a closure only when it lengthened the ID trip (`closed_road_ar`).
- **Rehearsed parses** (`demo_requests.json`, cached): "سكّروا شارع الملكة رانيا", "Close Queen Rania Street",
  "سكّروا شارع زهران وشارع المدينة المنورة", "Close Prince Al-Hasan Street", unsupported "سكّروا شارع الرينبو" and
  "Close Zahran Street on Fridays only". The parser gets a deterministic `roads_named_in_text` hint.
- **Rebuild order after a population change:** `seed_daily` → `fetch_map_data hubs` → `fetch_roads build` →
  `scripts.calibrate_roads` (cached calls are free) → `scripts.road_impact` to re-check.

## 11b. Group protections + opening offices (DONE, 2026-10-09)
Five new Policy levers (models.py, engine.py), all per citizen by their tags, deterministic, manual/free-text only (NOT in
the fix grid, so the demo path, heroes and cached AI fix are unchanged):
1. `appointment_exempt_groups`: those groups walk in without the online appointment. Demo + elderly/disabled: served 79.6 → 81.6.
2. `fee_discounts {group: %}`: largest discount applies. On its own it moves no statuses on the demo path (hardship there is
   helpers/appointments, not cost), but lowers avg cost; "free for over-65s" is now SUPPORTED (old cached "unsupported" removed).
3. `home_visits {groups, slots}`: a clerk renews at home; slots go to eligible citizens worst off first (left out, then heaviest
   hardship). New assumption HOME_VISIT_MINUTES = 120 (2-h visit window), committed in 0387862 before use. Demo + 20 slots:
   left out 0.9 → 0.5. KPI `n_home_visits`; voice template "جاء موظف الأحوال المدنية إلى بيتي".
4. `transport_vouchers [{groups, amount_jd}]`: bus/taxi fares paid up to X per round trip; taxis become affordable.
5. `hybrid_pickup`: an extra option (never forced): apply online (self or helper = hardship), then a PICKUP_MINUTES = 15 visit.
   Matters when full online renewal is off (baseline without online: served 48.9 → 55.6).
Plus the UI can open an office in any area ("افتح مكتباً", picks the real CSPD site there if any) and close any office.
UI: "حماية الفئات" section in the policy panel (group chips + steppers), home visits used under the KPIs. Parser knows all
levers; rehearsed (cached): walk-in for elderly+disabled, 30 home visits for wheelchair users, 3 JD taxi voucher for low
income, apply-online-and-pick-up, open an office in Marka; unsupported rehearsal is now "Add more staff at the Marka office".
Tests: tests/test_levers.py (53 tests total).

## 12. Useful commands (from `backend/`)
```bash
.venv/Scripts/python -m uvicorn app.main:app --port 8000        # app at http://localhost:8000
.venv/Scripts/python -m pytest -q                                # 31 offline tests
.venv/Scripts/python -m app.data.seed_census --install           # regenerate population (user must run it: auto mode blocks it)
.venv/Scripts/python -m app.data.fetch_map_data matrix           # re-fetch OSRM times after a population change
.venv/Scripts/python -m scripts.pick_heroes                      # re-pick heroes for the demo scenario
.venv/Scripts/python -m scripts.find_ai_fix                      # search for a verified AI fix (uses AI quota)
.venv/Scripts/python -m scripts.warm_cache                       # warm the AI cache (uses AI quota; only misses are requested)
```
On Windows/Git Bash, set `PYTHONIOENCODING=utf-8` when printing Arabic to the console.

## 13. Timeline (git, newest first, abridged)
`a0a1745` start-up warm-up · `865f005` Render blueprint · `7913c13` one server for UI + API · `70c33b9`/`d289820`/`238bec0` clean-up,
seamless connection, docs · `5a946fc`/`979e22b` frontend connected and fixed · `5234425` real 7-office baseline + consolidation demo ·
`c635152` فصحى voices · `a34adff` model chains · `75d42cb` census population · `923ee74` engine API + AI layer · `6feaa3c` assumptions frozen.
