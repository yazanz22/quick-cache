# HANDOFF: Nas (ناس), state of the project

Read this first in a new context window, then `CLAUDE.md` (the full spec). Last updated 2026-10-09 (late evening, Amman),
after the group protections were added and the road-closures experiment was removed.

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
| Production | **https://nas-rbo5.onrender.com** (Render free web service from `render.yaml`). **Auto-deploy did not fire on push on 2026-10-09: the user deploys by hand** in the Render dashboard (Manual Deploy → latest commit). After a deploy the old build keeps serving for ~1 min. |
| Tests | from `backend/`: `.venv/Scripts/python -m pytest -q` → **39 passing**, all offline (no AI calls) |
| Python | local venv is Python 3.14 (`backend/.venv`); Render uses 3.12.7 |

Render notes: the free plan sleeps after ~15 min idle; the first visit takes ~30-60 s to wake (the UI shows
"can't reach the engine" → press Retry). At start-up the server pre-computes the demo path (`sim/warmup.py`)
so the first real request is fast. Secrets (GEMINI/GROQ/OPENAI keys) are set in the Render dashboard
(Environment tab), never in the repo. New AI answers generated on Render are lost on restart; the committed cache persists.

## 3. Hard rules (from the user and CLAUDE.md)
- **Never add a co-author / "Co-Authored-By" line** to commits or PRs. Small, focused commits pushed to `main`.
- **Freeze rule:** never change values in `backend/app/sim/assumptions.py` to make a story appear. Change scenarios instead.
  (Assumptions were committed as frozen in `6feaa3c` *before* any scenario ran; the two constants added later for new
  levers, `HOME_VISIT_MINUTES` and `PICKUP_MINUTES`, were committed in `0387862` before any code used them.)
- **Frontend computes nothing.** Backend shapes are adapted only in `nas-frontend/api.js`; UI strings live in `nas-frontend/i18n.js`.
- **`backend/app/models.py` is the API contract.** If you change it, check `nas-frontend/api.js` in the same commit.
- Every AI call goes through `llm/client.py` + `llm/cache.py` + `llm/checks.py`, with a template in `llm/fallbacks.py`.
- **Auto mode blocks running code a teammate wrote** (e.g. `seed_census.py`), even with the user's approval. Ask the user to run it in their terminal.
- Never paste API keys in chat; the user edits `.env` (repo root, gitignored) themselves.
- Synthetic data only; never present synthetic numbers as real statistics.
- Don't loop AI calls during development (free-tier quotas, see §8).
- **Road closures were tried and removed at the user's request** (§11). Don't reintroduce them unless asked.

## 4. Repository layout (what matters)
```
CLAUDE.md, README.md, HANDOFF.md, render.yaml, .env.example
"Amman in a Box_ A Verified Statistical Blueprint for Policy Simulation.md"   # teammate's desk research (source for seed_census)
backend/
  app/main.py            # FastAPI: routers, CORS (only for :3000), serves nas-frontend/ at /, start-up warm-up
  app/config.py          # loads repo-root .env (LLM_*, MODEL_*, DEMO_OFFLINE ...)
  app/models.py          # all Pydantic schemas (contract), incl. the group protections (HomeVisits, TransportVoucher)
  app/routes/sim_routes.py  # /population /scenarios /sites /areas /heroes /assumptions /simulate /compare /fixgrid /sensitivity
  app/routes/llm_routes.py  # /policy/parse /citizen/voice /report /fixes /llm/status
  app/sim/   assumptions.py (frozen), assumption_labels.py (ar/en text only), travel.py, engine.py, compare.py,
             fixgrid.py, sensitivity.py, validate.py, warmup.py, world.py
  app/llm/   client.py, prompts.py, cache.py, fallbacks.py, checks.py, tasks.py
  app/data/  population.json (1,000), travel_matrix.json (OSRM), home_points.json (OSM streets), sites.json (15),
             areas.json (8), anchors.json, seed_census.py (+ census/ outputs), seed.py (shared helpers),
             fetch_map_data.py, scenarios/*.json (+ heroes.json, demo_requests.json)
  scripts/   pick_heroes.py, find_ai_fix.py, warm_cache.py
  cache/     committed AI cache: parse 17, voice 10, report 3, fixes 1
  tests/     test_engine.py, test_fixgrid.py, test_llm.py, test_levers.py
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
  + 8 generic snap sites, one per area. Offices can be opened or moved to any of the 15.
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
The demo is mostly **yellow (hardship)**, not red; only `online_only` makes red spread.

**Group protections on the demo path** (manual levers, §11; useful as a "policy-side" answer next to the engine's fixes):
walk-in for elderly + disabled → served 81.6; + 20 home visits → 83.6 served, left out 0.5; all five stacked (walk-in,
30 home visits, 3 JD voucher for low income, free for over-65s, hybrid) → **87.1 / 12.6 / 0.3**.

**Heroes** (`heroes.json`, made by `scripts/pick_heroes.py`, factual `profile` per hero; all four get worse under the demo and recover with the top fix):
c_0028 Dana (71f, no car/smartphone, son helps), c_0031 Mohammad (67m, wheelchair, son helps),
c_0837 Bilal (38m, 07:00-16:00 shift, no helper), c_0020 Amina (63f, low digital literacy, no helper).

**Rehearsed requests** (`demo_requests.json`, all cached; check with `scripts.warm_cache --parse-only`): the on-stage sentence
"خلّوا الكاونترات تسكر الساعة 1 الظهر، وما حدا يراجع المكتب إلا بموعد مسبق أونلاين" applied to `consolidate` parses to exactly
`consolidate_digital_first`; plus close offices on Thursday (ar/en), close/reopen Marka, online-only + Saturday van in Wehdat,
double the fee, two visits, free for over-65s (ar/en, now supported), walk-in for elderly + disabled, 30 home visits for
wheelchair users, a 3 JD taxi voucher for low income, apply online and pick up, open a new office in Marka. The **unsupported**
rehearsal is "Add more staff at the Marka office" (and any road closure, e.g. "سكّروا شارع زهران", is answered "not supported").

## 7. Engine decisions worth knowing (deviations from CLAUDE.md, all deliberate)
- Option choice ranks **best status first** (served > hardship), then burden. Otherwise a citizen with a car would be pushed
  into "a relative did it online". (The teammate's frontend prompt called this a "known issue": it is already fixed.)
- `SensitivityResult` has `stable_top2` and `fix_checked`; `/sensitivity` accepts no fix (ranking-only), so the badge works before fixes.
  With a fix that doesn't move left-out, it is judged on left-out + hardship.
- AI fix proposals are capped at 3 changes (`count_changes`) so they stay comparable to grid pairs.
- Office ids need not be unique (the UI renames a dragged office `office_<area>`, and two real offices share area `khalda`).
- **Group protections** are per citizen by tags and are **not in the fix grid** (so the demo's fixes, heroes and cached AI fix
  don't change). Hybrid pickup is an *extra option* the citizen takes only if it's better (forcing it made the baseline worse).
  Home-visit slots go to eligible citizens worst off first (left out, then the heaviest hardship, ties by id).
- Performance: simulate ~50 ms, fix grid ~0.3 s locally (~5 s on Render), robustness ~0.5 s locally (~3.5 s on Render, cached after).

## 8. AI layer
- Providers: Gemini (primary) → Groq → OpenAI (`LLM_FALLBACK_PROVIDER=groq,openai`), then templates. Providers without a key are skipped.
- **Gemini free tier = ~20 requests/day per model**, so each slot is a comma-separated **model chain** in `.env`:
  `MODEL_FAST` (voices) = gemini-3.8/3.7/3.6/3.5-flash (no lite: its Arabic had typos), `MODEL_SMART` = 3.6/3.7/3.5-flash + 3.5/3.1-flash-lite,
  `GROQ_MODEL_FAST` empty on purpose (Groq Arabic is weak), `GROQ_MODEL_SMART` = gpt-oss-120b/20b, qwen3.8-27b,
  `OPENAI_MODEL_*` = gpt-4.1-mini, gpt-5.4-mini (**the OpenAI key has no credits**; it's benched automatically).
  When Gemini is out, **Groq still parses and explains fixes**; voices then use the template.
- Limited models go on cooldown (daily limit → until ~08:00 UTC; per-minute/overload → 30-65 s). `GET /llm/status` shows them.
- All attempts for one request share **17 s** (`LLM_TOTAL_BUDGET_S`), under the frontend's 20 s timeout. A slow Gemini model
  can use up the budget before Groq gets a turn (seen once with flash-lite): retrying the request fixes it.
- **Voices are in فصحى (Modern Standard Arabic)**, a team decision (CLAUDE.md updated). Helper words are stored in dialect in the
  population and mapped to فصحى (بنتي→ابنتي, أخوي→أخي, أبوي→أبي, صاحبي→صديقي). Voice checks reject numbers not in the facts,
  people other than the helper, "ليرة", a helper word missing its possessive, and known misspellings.
  Home visits: mode `home`; the template says "جاء موظف الأحوال المدنية إلى بيتي وجدّد هويتي" (and "دون أن أدفع أي رسوم" when free).
- Cache key = sha256(task + inputs), no provider/model; voice inputs include `"register": "msa"`. Policies in keys go through
  `tasks.policy_json`, which **drops the protection fields while they're at their defaults**, so keys made before the levers
  existed still hit. `DEMO_OFFLINE=1` = cache + templates only (verified: the whole demo path works offline).
- Gemini daily quota resets ~10:00 Amman time. Don't burn it in loops.

## 9. Frontend ↔ backend
- FastAPI serves `nas-frontend/` at `/` (mounted after the API routes; a test checks routes still win). `config.js` uses the page's
  own origin as the API (falls back to http://localhost:8000 when opened on :3000). `?api=<url>` and `?offline=1` (no map tiles) work.
- `api.js` adaptations: `/sensitivity` sends the fix's `policy`; backend `details[]` → UI `detail[]` rows.
- Policy panel: offices (each with a trash button to close it) + **"افتح مكتباً / Open an office"** (area select; picks the real
  CSPD site in that area if any), rules, **"حماية الفئات / Protections for groups"** (group chips for walk-in, fee discount with a
  % stepper, transport voucher with a JD stepper, home visits switch + groups + slots stepper, hybrid switch), mobile units, fee, visits.
  Impact panel shows "home visits used N / slots" when home visits are on. The citizen card hides travel facts for a home visit.
- The citizen drawer scrolls instead of squeezing its rows (`grid-auto-rows: max-content`), fixed on 2026-10-09.
- Verified end to end, locally and on Render, in Arabic and English: presets, map recolour + rings, hero cards with AI voices, fixes +
  AI fix + apply, robustness badge/table, free-text parse (demo sentence matches the preset exactly; unsupported message), report,
  backend-down error screen + Retry, `?offline=1`, dragging an office pin, every protection, opening/closing an office.

## 10. Open items / known caveats
1. **2 hero voices still use the template**: Bilal (c_0837) and Amina (c_0020) *after the engine's top grid fix* (the demo applies
   the AI fix, so they rarely show). After the Gemini reset: from `backend/`, `.venv/Scripts/python -m scripts.warm_cache`, then commit `backend/cache/`.
   Voices for citizens served by home visits are generated on click (AI or template); none are pre-cached.
2. **Fully offline demo**: the UI still loads Leaflet, Phosphor icons and Google Fonts from CDNs. Vendor them into `nas-frontend/` before a no-wifi demo.
3. **Native-speaker review** of the cached voices: the user said leave it.
4. Staff / operating-cost readout: **ruled out of scope** by the user (on stage: "operating cost is the next module").
5. `app.js` has its own *dialect* voice template (`fallbackVoiceAr`), used only if `/citizen/voice` fails outright. Our backend
   always answers within 17 s (AI or فصحى template), so it should never show; left as is (frontend rules).
6. The public URL can spend the free AI quota; share it only with judges/team.
7. A fee discount alone changes no statuses on the demo path (hardship there comes from appointments and helpers, not cost);
   it shows in the average cost. Opening a Marka office on the demo path also moves no statuses (it does on `consolidate`: 85.0 → 85.6).
   Both are honest results; don't tune them.
8. The user's local `.env` still has a `TOMTOM_API_KEY` from the removed road work; nothing reads it.

## 11. Group protections + opening offices (DONE, 2026-10-09)
Five Policy levers (models.py, engine.py), all per citizen by their tags, deterministic, manual/free-text only:
1. `appointment_exempt_groups`: those groups walk in without the online appointment. Demo + elderly/disabled: served 79.6 → 81.6.
2. `fee_discounts {group: %}`: the largest discount applies. "Free for over-65s" = `{"elderly": 100}` (now supported).
3. `home_visits {groups, slots}`: a clerk renews at home (`HOME_VISIT_MINUTES` = 120, a 2-hour visit window). Slots go to the
   worst-off eligible citizens first. Demo + 20 slots: left out 0.9 → 0.5. KPI `n_home_visits`.
4. `transport_vouchers [{groups, amount_jd}]`: bus/taxi fares paid up to X JD per round trip; taxis become affordable.
5. `hybrid_pickup`: apply online (self, or via a helper = hardship), then a `PICKUP_MINUTES` = 15 visit to collect. An extra
   option, never forced. Matters when full online renewal is off (baseline without online: served 48.9 → 55.6).
Plus opening an office in any area and closing any office from the UI (the schema always allowed it; the parser handles
"open a new office in X"). Validation: discounts 0-100, home visits and vouchers need at least one group. `count_changes`
counts each protection changed as 1. Tests: `tests/test_levers.py`.

**Road closures: built and removed (2026-10-09).** 18 major roads with our own OSM routing, TomTom-calibrated detours and an
everyday-trips module (work/university/hospital) were added, then removed entirely at the user's request: TomTom has no traffic
data for Amman, so without congestion the delays understated the impact. Everything is in git history (`315ba11`..`3a4e645`,
removed in `8b99eff`, `6d6c76f`, `dd16cc3`). A road request now gets the parser's honest "not supported" answer.
If it's ever revived, real congestion data is the blocker (Google Maps has Amman traffic but needs a billing account).

## 12. Useful commands (from `backend/`)
```bash
.venv/Scripts/python -m uvicorn app.main:app --port 8000        # app at http://localhost:8000
.venv/Scripts/python -m pytest -q                                # 39 offline tests
.venv/Scripts/python -m app.data.seed_census --install           # regenerate population (user must run it: auto mode blocks it)
.venv/Scripts/python -m app.data.fetch_map_data matrix           # re-fetch OSRM times after a population change
.venv/Scripts/python -m scripts.pick_heroes                      # re-pick heroes for the demo scenario
.venv/Scripts/python -m scripts.find_ai_fix                      # search for a verified AI fix (uses AI quota)
.venv/Scripts/python -m scripts.warm_cache                       # warm the AI cache (uses AI quota; only misses are requested)
.venv/Scripts/python -m scripts.warm_cache --parse-only          # just the rehearsed free-text requests (Groq can do these)
```
On Windows/Git Bash, set `PYTHONIOENCODING=utf-8` when printing Arabic to the console. With `DEMO_OFFLINE=1` in front,
`warm_cache` only reads the cache: a quick way to check that every rehearsed answer is still cached.

## 13. Timeline (git, newest first, abridged)
`dd16cc3`/`6d6c76f`/`8b99eff` road closures removed · `5ab38d2` protections panel + open/close offices in the UI ·
`f292274` five group protections in engine + AI · `0387862` HOME_VISIT_MINUTES / PICKUP_MINUTES set before use ·
`315ba11`..`3a4e645` road closures + everyday trips (since removed) · `4528c27` first HANDOFF ·
`a0a1745` start-up warm-up · `865f005` Render blueprint · `7913c13` one server for UI + API · `70c33b9`/`d289820`/`238bec0` clean-up,
seamless connection, docs · `5a946fc`/`979e22b` frontend connected and fixed · `5234425` real 7-office baseline + consolidation demo ·
`c635152` فصحى voices · `a34adff` model chains · `75d42cb` census population · `923ee74` engine API + AI layer · `6feaa3c` assumptions frozen.
