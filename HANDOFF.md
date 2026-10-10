# HANDOFF: Nas (ناس), state of the project

Read this first in a new context window, then `CLAUDE.md` (the full spec). **For the stage: `DEMO_RUNBOOK.md`** (clicks,
numbers, cached judge requests, fallbacks, morning checklist). Last updated 2026-10-10 (evening, Amman), after the
third sector, **medical exemptions (Royal Court, for uninsured citizens)**, was added (§16). Earlier that day: the second
sector, **everyday travel (fuel prices)** (§15), the verified health-insurance anchors (§5), and a full review pass
(42 issues fixed, 26 improvements); see §14 for what is on hold.

### Pick up here (written 2026-10-10 ~15:00 Amman, at the context-window switch)
- **Code:** everything is on `main` (last commit `e7f9fe8`), working tree clean, `pytest -q` = 285 passed, 57 xfailed
  (the xfails are AI cache entries not warmed yet: id_renewal 1, everyday_travel 28, medical_exemption 28).
- **Three user actions remain, none of which Claude can do:** (1) deploy Render by hand (production is still on the
  2026-10-09 build; check `/health` shows `warm`); (2) warm the AI cache on a **phone hotspot** (the venue network's
  FortiGate blocks the AI APIs: §10.1 has the commands, ~60 calls in total); (3) the pitch deck from `GAMMA_PROMPT.md`
  (9-slide version, also in §17).
- **Dev server for browser checks:** `.claude/launch.json` → `nas-dev` on port 8010 (`--reload`); port 8000 belongs to
  another desktop session running old code. Use `?offline=1`; `?sector=id_renewal|everyday_travel|medical_exemption`
  skips the sector list.
- **Don't:** change any value in `assumptions.py` (35 constants, all frozen); change fix titles or anything in a cache key
  for id_renewal (§8); re-run the population generator before the demo.

## 1. What Nas is (one paragraph)
A "wind tunnel" for public policy in Amman, built for AI Quest @ Al Hussein Technical University.
1,000 **synthetic citizens, AI-voiced** (never say "1,000 AI citizens") go through a policy in one of **three sectors**:
**ID renewal** (offices, online, appointments, vans, protections: served / hardship / left out); since 2026-10-10,
**everyday travel under fuel prices** (each citizen's regular trip to work, university or hospital under fuel and fare
changes and cash support: fine / squeezed / priced out, §15); and, since the evening of 2026-10-10, **Royal Court medical
exemptions** (the 441 synthetic residents without health insurance apply for an exemption: one office and two visits today,
Sanad, intake points, mobile intake days, a relative applying for them: served / hardship / left out over the uninsured
only, §16). The app opens on a sector list. The **deterministic engine**
decides every outcome and number, searches a grid of fixes, and runs a ±20% robustness check. The **AI** only translates
(free text → policy), voices citizens (in فصحى), writes the report, and explains/proposes fixes. **The engine verifies
everything the AI proposes.** Every AI task has a template fallback.

## 2. Where things run
| What | Where |
|---|---|
| Repo | https://github.com/yazanz22/quick-cache (branch `main`; push directly to main) |
| Local app (UI + API, one server) | from `backend/`: `.venv/Scripts/python -m uvicorn app.main:app --port 8000` → **http://localhost:8000** (API docs at `/docs`) |
| Production | **https://nas-rbo5.onrender.com** (Render free web service from `render.yaml`). **Auto-deploy did not fire on push on 2026-10-09: the user deploys by hand** in the Render dashboard (Manual Deploy → latest commit). After a deploy the old build keeps serving for ~1 min. |
| Tests | from `backend/`: `.venv/Scripts/python -m pytest -q` → **285 passed, 57 xfailed** (2026-10-10 evening), all offline (no AI calls). `test_demo.py` guards the ID-renewal demo numbers; `test_travel.py` guards the travel sector (numbers, heroes, robustness, and that ID-renewal outcomes stay byte-identical); `test_exemption.py` guards the medical-exemption sector (numbers, heroes, proxy rule, eligibility, seed_insurance determinism, and sha256 hashes pinning id_renewal and travel outcomes byte-identical); `test_cache_hits.py` guards every cached AI answer (the 57 xfails = Amina's post-AI-fix voice + 28 travel + 28 medical-exemption entries not warmed yet, see §10.1); `test_api.py` covers the HTTP 422 paths and gzip |
| Dev server for agents/browser checks | `.claude/launch.json` has `nas` (port 8000) and `nas-dev` (port 8010, `--reload`); use `nas-dev` when another session already holds 8000 |
| Python | local venv is Python 3.14 (`backend/.venv`); Render uses 3.12.7 |

Render notes: the free plan sleeps after ~15 min idle; the first visit takes ~30-60 s to wake (the UI shows
"can't reach the engine" → press Retry). At start-up the server pre-computes the demo path (`sim/warmup.py`)
so the first real request is fast. Secrets (GEMINI/GROQ/OPENAI keys) are set in the Render dashboard
(Environment tab), never in the repo. New AI answers generated on Render are lost on restart; the committed cache persists.

## 3. Hard rules (from the user and CLAUDE.md)
- **Never add a co-author / "Co-Authored-By" line** to commits or PRs. Small, focused commits pushed to `main`.
- **Freeze rule:** never change values in `backend/app/sim/assumptions.py` to make a story appear. Change scenarios instead.
  (Assumptions were committed as frozen in `6feaa3c` *before* any scenario ran; the two constants added later for new
  levers, `HOME_VISIT_MINUTES` and `PICKUP_MINUTES`, were committed in `0387862` before any code used them; the 7 travel
  constants were committed in `3b1cde0` before any travel scenario ran, §15; the 2 medical-exemption constants,
  `EXEMPTION_VISIT_MINUTES` and `UNINSURED_RATE_BY_BAND`, in `a200815` before any exemption scenario ran, §16.)
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
CLAUDE.md, README.md, HANDOFF.md, render.yaml, .env.example, .gitignore (also ignores .claude/, the desktop app's local config)
"Amman in a Box_ A Verified Statistical Blueprint for Policy Simulation.md"   # teammate's AI-assisted desk research (Qwen; source for seed_census); unverified unless ANCHORED in anchors.json
"Estimating Amman's Uninsured Rate_ ....md"   # research doc behind the medical-exemption sector (46aa477); checked figures are in anchors.json (§5)
backend/
  app/main.py            # FastAPI: routers, CORS (only for :3000), serves nas-frontend/ at /, start-up warm-up
  app/config.py          # loads repo-root .env (LLM_*, MODEL_*, DEMO_OFFLINE ...)
  app/models.py          # all Pydantic schemas (contract), incl. the group protections (HomeVisits, TransportVoucher),
                         # Service literal, ServiceInfo, CashSupport, the travel levers and travel outcome fields (§15),
                         # Citizen.has_health_insurance, the "uninsured" Group, Policy.proxy_allowed (§16)
  app/routes/sim_routes.py  # /services /population /scenarios /sites /areas /heroes?service= /assumptions /simulate /compare /fixgrid /sensitivity
  app/routes/llm_routes.py  # /policy/parse /citizen/voice /report /fixes /llm/status
  app/sim/   assumptions.py (frozen), assumption_labels.py (ar/en text only), travel.py, engine.py, compare.py,
             fixgrid.py, sensitivity.py, validate.py, warmup.py, world.py,
             travel_service.py (the everyday_travel engine: regular trips, monthly cost, share of income; engine.py dispatches by policy.service;
             engine.py's SERVICE_RULES runs id_renewal and medical_exemption on the same in-person machinery, §16)
  app/llm/   client.py, prompts.py, cache.py, fallbacks.py, checks.py, tasks.py   (all service-aware since e70cd11)
  app/data/  population.json (1,000), travel_matrix.json (OSRM), home_points.json (OSM streets), sites.json (16: + royal_court_csu),
             areas.json (8), anchors.json, seed_census.py (+ census/ outputs), seed.py (shared helpers),
             fetch_map_data.py, scenarios/*.json (+ heroes.json, demo_requests.json; exemption_today / _online_only /
             _hybrid / _regional / _no_proxy for medical_exemption),
             services.json (the 3 sectors: id, names, levers, baseline/demo scenario; served by GET /services),
             seed_insurance.py (has_health_insurance + the "uninsured" tag, seed 42; re-run after seed_census --install),
             hubs.json (25 trip destinations: 14 work, 7 university, 4 public hospitals; OSM Nominatim, weights ASSUMPTION),
             daily_trips.json (one regular trip per citizen, made by seed_daily.py, seed 42),
             hub_matrix.json (OSRM citizen → hub times/distances, fetched 2026-10-09), seed_daily.py
  scripts/   pick_heroes.py, find_ai_fix.py, warm_cache.py   (find_ai_fix and warm_cache take --service id_renewal|everyday_travel|medical_exemption)
  cache/     committed AI cache: parse 61, voice 12, report 6, fixes 1 (all ID renewal; travel and medical exemption not warmed yet, §10.1)
  tests/     test_engine.py, test_fixgrid.py, test_levers.py, test_api.py (HTTP 422s, gzip, warm-up), test_llm.py (AI checks,
             fixes flow, templates), test_cache_hits.py (every cached answer still hits), test_demo.py (pinned numbers, heroes, 6/6),
             test_travel.py (travel numbers, heroes, fix grid, 5/6 robustness, id_renewal outcomes byte-identical),
             test_exemption.py (exemption numbers, heroes, proxy rule, not-applicable counting, seed_insurance, other sectors' hashes)
nas-frontend/  index.html, config.js, api.js, i18n.js, app.js, README.md   # static, no build step
  vendor/      Leaflet, Phosphor icons, IBM Plex fonts (local copies of the old CDN files; see vendor/README.md)
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
- **Hours** 08:30-15:30 Sun-Thu (CSPD's published hours, TEAM_CONFIRMED in anchors.json; a Fri/Sat 10-14 line is not modelled: may be contact-centre hours).
- **Fee** JD 2: confirmed by the team (`anchors.json` status TEAM_CONFIRMED). The research's "JD 1" is for a different CSPD service.
- **anchors.json** (documentation only, nothing reads it at runtime): ANCHORED (team opened the source) = MoDEE 2024 internet use
  95.6%, Amman smartphone households 99%, e-gov use 38.1%, and the CSPD office list; TEAM_CONFIRMED = the JD 2 fee and the
  08:30-15:30 hours (page URL not recorded); everything else from the research is CITED_UNVERIFIED (called **CITED** in
  `VALIDATION.md` and `seed_census.py`, renamed from "ANCHORED" on 2026-10-10). Bus fare 0.34-0.55 JD and the 25.4-min peak bus
  wait are CITED context for `BUS_FARE_JD` / `BUS_FIRST_WAIT_MIN`, shown as `source` notes in the assumptions table.
- **Fuel sector anchors (added 2026-10-10, CITED_UNVERIFIED = press reports):** the Fuel Pricing Committee's October 2026
  prices (90-octane 1.050 JD/L, +0.05; 95-octane 1.360, +0.05; diesel 0.900, +0.05; kerosene 0.550, unchanged; Jordan News,
  2026-10-01) and the National Aid Fund's fuel support of 8-14 JD/month per beneficiary family (Ammon News). The 2012 subsidy
  removal is context only, no figure anchored. None of them sets an engine constant.
- **Health-insurance anchors for the third sector** (Royal Court medical exemption, §16; the engine now uses the Amman figure
  through `UNINSURED_RATE_BY_BAND`), checked 2026-10-10: DoS "Health Insurance in Jordan" (Census 2015 paper, ANCHORED): 68.7% of Jordanians and ~56% of the total
  population insured; under-6s all insured by MoH; **Amman: 55.2% of Jordanians insured (44.8% not), 41.2% of the total
  population (58.8% not)**, Amman and Zarqa the lowest (41%); non-Jordanians 25.3% nationally, 16.4-16.8% in Amman; lowest
  coverage at ages 15-34. JPFHS 2023 (ANCHORED): 69% of ever-married women and 59% of men aged 15-49 insured. **Do not reuse**
  the research doc's "76.8% of Jordanians insured" (BMC 2024 article whose breakdown sums to 84.9 and that cites DoS 2015 anyway)
  or its "38% of non-Jordanians insured" (conflates 25.3% insured with "38% of the insured are under special arrangements");
  both are `research_doc_*` entries marked DO NOT USE. Recommended engine input: Amman Jordanians 16+ uninsured ≈ 45-50%
  (44.8% is all ages incl. the fully insured under-6s, so adults are higher; the range itself is our assumption).
  **Used since `da8d79f`:** `seed_insurance.py` (seed 42) draws each citizen's insurance from `UNINSURED_RATE_BY_BAND`
  (low 0.65 / middle 0.45 / high 0.20, ASSUMPTION calibrated to that anchor): **441 of 1,000 uninsured (44.1%; low 61.0%,
  middle 44.6%, high 17.5%)**, tag `uninsured`, field `has_health_insurance`. It must be **re-run after
  `seed_census --install`** (which rewrites population.json without these fields). Only the medical-exemption engine reads them.
- **Royal Court medical exemption process** (anchors.json `royal_court_medical_exemption_process`, CITED_UNVERIFIED = press
  reports, Al Rai and Ad-Dustour): applications in person at the Citizen Services Unit with a medical report, a Ministry of Health
  doctor's review, a return visit for the letter. Hours and queue time are not published (hence 08:00-15:00 Sun-Thu ASSUMED and
  `EXEMPTION_VISIT_MINUTES` = 120 ASSUMPTION).
- **Royal Court site** (`sites.json` `royal_court_csu`, area downtown, `real: true`): 31.9565, 35.9475 (Raghadan, ±1 km). One
  Nominatim query returned nothing, so these are **fallback coordinates**; there are no OSRM rows for it, so road distance is
  straight-line × `ROAD_FACTOR`. It appears only in the medical-exemption sector's site lists (`config.js` `SERVICE_ONLY_SITES`),
  so ID renewal still offers its 15 sites.
- **Engine constants: all 35 are ASSUMPTION** (26 for ID renewal + shared travel model, 7 for everyday travel, 2 for medical exemption). On stage: *"The population is anchored to published figures where we found them;
  the engine constants are labelled assumptions, frozen before any scenario ran and tested at ±20%."* Never "verified official statistics".
  Slide-ready list: README, **"What is real and what is assumed"** (incl. what each group means).
- **Groups** (tags): elderly = 65+ (65 people); disabled = limited mobility or wheelchair (69: mobility only, not the 10.4% WG rate);
  low_income = bottom 30% of synthetic per-capita income (300; not the 8.3% poverty rate); offline = no smartphone or low digital
  skills (204); no_car (534); worker = employed, Sun-Thu shifts (320); student = 18-24 and not working (164);
  **uninsured** = no health insurance (441, from `seed_insurance.py`; the eligibility tag of the medical-exemption sector,
  ignored by the other two).
- **Neighbourhood labels fixed in `seed_census.py` only** (2026-10-10, text, no logic): Bader's "Al-Qwesmeh road side" is now
  "Airport Road (Bader)" (matching its Arabic "طريق المطار - بدر"), and the two "Al-Hilal" become "Al-Hilal (Al-Yarmouk)" /
  "Al-Hilal (Bader)" with matching Arabic. **`population.json` still carries the old strings** until the next regeneration
  (names don't affect the RNG, so regenerating changes only these labels); Dana's profile in `heroes.json` was fixed by hand.
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
**Guard:** `tests/test_demo.py` pins baseline 88.4/11.5/0.1, demo 79.6/19.5/0.9, 93 worse off, worst groups elderly, offline,
ranking 6/6, and that every hero gets worse and recovers with the top grid fix. If it fails: update this section, re-pick heroes,
re-warm the cache.

**Group protections on the demo path** (manual levers, §11; useful as a "policy-side" answer next to the engine's fixes):
walk-in for elderly + disabled → served 81.6; + 20 home visits → 83.6 served, left out 0.5; all five stacked (walk-in,
30 home visits, 3 JD voucher for low income, free for over-65s, hybrid) → **87.1 / 12.6 / 0.3**.

**Heroes** (`heroes.json`, made by `scripts/pick_heroes.py`, factual `profile` per hero; all four get worse under the demo and recover with the top fix):
c_0028 Dana (71f, no car/smartphone, son helps), c_0031 Mohammad (67m, wheelchair, son helps),
c_0837 Bilal (38m, 07:00-16:00 shift, no helper), c_0020 Amina (63f, low digital literacy, no helper).

**Everyday-travel presets** (`service: "everyday_travel"`, compared against `travel_today`; statuses read fine / squeezed /
priced out; full rules in §15):
| id | policy | fine / squeezed / priced out | worse off |
|---|---|---|---|
| `travel_today` | today's fuel and fares, no support | 72.2 / 17.8 / 10.0 | – |
| `fuel_plus_5` | Oct 2026 rise (+0.05 JD/L on 90-octane ≈ +5%), fares follow by pass-through | 71.6 / 18.3 / 10.1 | 7 (all car drivers) |
| `fuel_plus_25` | fuel +25%, regulated fares mostly held (pass-through) | 70.6 / 18.6 / 10.8 | 24 (all car drivers) |
| **`fuel_plus_25_fares`** (travel demo) | fuel +25% and bus/taxi fares +25% (as after the 2012 hike) | **70.2 / 14.6 / 15.2** | **72** (48 bus, 24 car) |
| `fuel_plus_25_support` | the same + 14 JD/month cash for low_income | 73.8 / 11.7 / 14.5 | 66 (37 better) |

Travel demo facts: worst groups **worker, offline, low_income**; average extra cost 4.54 JD/month. Engine top fix: **"14 JD/month
cash support for people without a car + freeze bus fares"**: priced out 15.2 → 8.0 (−7.2 pts; squeezed 14.6 → 15.5, since people
lifted out of "priced out" land in "squeezed"). Robustness **5/6** (§15), fix helps 6/6. Heroes: c_0627 Mustafa, c_0883 Rana,
c_0982 Issa (the top fix does not reach him, on purpose).

**Rehearsed requests** (`demo_requests.json`, all cached; check with `scripts.warm_cache --parse-only`): the on-stage sentence
"خلّوا الكاونترات تسكر الساعة 1 الظهر، وما حدا يراجع المكتب إلا بموعد مسبق أونلاين" applied to `consolidate` parses to exactly
`consolidate_digital_first`; plus close offices on Thursday (ar/en), close/reopen Marka, online-only + Saturday van in Wehdat,
double the fee, two visits, free for over-65s (ar/en, now supported), walk-in for elderly + disabled, 30 home visits for
wheelchair users, a 3 JD taxi voucher for low income, apply online and pick up, open a new office in Marka. The **unsupported**
rehearsal is "Add more staff at the Marka office" (and any road closure, e.g. "سكّروا شارع زهران", is answered "not supported").
"All cached" is true for the ID-renewal requests only. The **12 travel requests** (`service: "everyday_travel"`, on `travel_today`
or `fuel_plus_25_fares`) are **not cached yet** (§10.1): raise petrol 10% (ar/en), fuel +25% with 14 JD/month for low-income
families (ar/en), freeze bus fares (ar/en), pay the bus fare for students (ar/en), give every worker 20 JD a month, and three
unsupported ones: lower electricity prices (ar/en) and "raise diesel only" (one fuel price change only).

**Medical-exemption presets** (`service: "medical_exemption"`, compared against `exemption_today`; **percentages of the 441
uninsured only**, the 559 insured are "not applicable"; full rules in §16):
| id | policy | served / hardship / left out | worse off |
|---|---|---|---|
| `exemption_today` | the Royal Court Citizen Services Unit only, 08:00-15:00 Sun-Thu (ASSUMED), 2 visits, no fee, no online channel, a relative may apply | 0.0 / 74.8 / 25.2 | – |
| **`exemption_online_only`** (exemption demo) | applications only through Sanad, the letter by post | **77.6 / 14.1 / 8.4** | **30** (364 better) |
| `exemption_hybrid` | today + apply on Sanad and collect the letter in one short visit | 77.6 / 20.9 / 1.6 | 0 (364 better) |
| `exemption_regional` | the unit + intake at the 7 CSPD offices, same hours, no online | 0.0 / 87.1 / 12.9 | 0 (54 better) |
| `exemption_no_proxy` | today, but the patient must come in person | 0.0 / 74.8 / 25.2 (identical to today) | 0 |

Exemption demo facts: the 30 worse off are **all offline residents with no helper** (offline left out 29.3% → 37.4%); worst groups
**offline, elderly**; robustness **6/6**, fix helps 6/6 (offline stable top). Top grid fix: **"intake at the 7 CSPD offices + a
Saturday mobile intake day in Downtown"**: left out 8.4 → 0.2 (37 → 1 people; hardship 14.1 → 22.2 as they move up). Heroes:
c_0931 Salma, c_0497 Abdullah, c_0188 Ali (all hardship → left out → hardship with the top fix). The 12 rehearsed exemption
requests in `demo_requests.json` are **not cached yet** (§10.1).

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
- **Engine memo (2026-10-10):** the per-channel memo is an LRU capped at 150 entries of compact tuples (~0.3 MB each, ~50 MB max).
  Before, entries were ~1 MB and only cleared at 4,000, i.e. 116 MB after warm-up and +20 MB per policy edit: it would have
  exhausted Render's 512 MB mid-demo. Outcomes are byte-identical before and after (verified by snapshot).
- Warm-up runs in a background thread; `/health` returns `{ok, warm}`; it also precomputes robustness for the top grid fix and the
  cached AI fix. Responses are gzipped (`/compare` 556 KB → 13 KB).
- `validate.policy_errors` also rejects: NaN/inf numbers, `online_only` with online disabled, an office day or van open for less
  than one visit (`SERVICE_MINUTES`), `fee_jd > 1000`. 422 bodies are either a string `detail` or a list `[{loc, msg, type}]`.
- "Late Thursday" in the fix grid only extends offices already open on Thursday (it used to reopen a closed Thursday at 08:00).
- `summarize()` adds `kpis.left_out_by_reason` / `hardship_by_reason` (a person with several reasons counts under each).
- `/fixgrid` returns `{fixes, scenario_kpis}`; each `FixCandidate` carries `n_changes` and its policy's `kpis`.

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
  Home visits: mode `home`; the template says "جاء موظف الأحوال المدنية إلى بيتي وجدّد هويتي" (and "دون أي رسوم" when free).
- **Checks hardened (2026-10-10):** AI output is validated with the full Pydantic model inside `check()` (a bad shape can no longer be
  cached and 500 forever); kin words are caught with attached prefixes (وأخي، ولأمي) and the list covers عمي/خالي/جدتي etc.; each fix
  explanation is grounded against its own numbers; proposal titles are grounded; proposals may not use the group protections; cache
  hits are re-validated; `_verify_proposal` runs `policy_errors` first; a `/fixes` answer whose proposal was invalid is not cached.
  `complete()` returns a `Completion` (str with `.meta`); a timeout on a short leftover budget no longer benches the model. The time
  budget starts at request start (routes pass `started_at`). Templates: proper Arabic counted nouns and duals (`count_ar`), feminine
  helper verbs, "دون أي رسوم", rises vs drops. Parse fallback distinguishes "not understood" (فصحى) from "AI unavailable".
- `/citizen/voice` prefers `{citizen_id, policy}` (the backend recomputes the outcome); `/report` prefers `{baseline, scenario, fix?}`
  and adds an `applied_fix` block to the summary when a fix is given (that is a new cache key; the no-fix summary is unchanged).
- Cache key = sha256(task + inputs), no provider/model; voice inputs include `"register": "msa"`. Policies in keys go through
  `tasks.policy_json`, which **drops the protection fields while they're at their defaults**, so keys made before the levers
  existed still hit. `DEMO_OFFLINE=1` = cache + templates only (verified: the whole demo path works offline).
- Gemini daily quota resets ~10:00 Amman time. Don't burn it in loops.

## 9. Frontend ↔ backend
- **Start state (2026-10-10, `b5b6d45` + `9237f55`):** the app opens on a **sector list** in the left panel (three cards from
  `GET /services`: "تجديد الهوية / ID renewal", "أسعار المحروقات / Fuel prices" and, since `397b8e4`, "الإعفاءات الطبية /
  Medical exemptions"); the map shows every citizen as a neutral
  **blue** dot (accent colour, no pins, rings or heroes), the right panel waits until a sector is chosen, and no `/compare` is
  sent. Choosing a card loads that sector's presets (`/scenarios` items carry `service`), heroes (`GET /heroes?service=<id>`)
  and policy-panel levers (`ServiceInfo.levers`). A back button in the panel head returns to the list and resets everything.
  The sector is not remembered; **`?sector=id_renewal`, `?sector=everyday_travel` or `?sector=medical_exemption` skips the
  list: use it on stage.** Since `397b8e4` there is a **third card, "الإعفاءات الطبية / Medical exemptions"**: insured
  residents are drawn as lighter neutral dots with a legend entry ("Insured: not applicable"), KPI cards read "N of 441
  uninsured", the panel reuses the ID-renewal controls relabelled (intake offices incl. the Royal Court site, online via Sanad,
  mobile intake days, visits, protections) plus a **"Applying on someone's behalf"** switch (`proxy_allowed`), and the citizen
  card shows `helper_visit` as "a relative applied on his/her behalf" (details in `nas-frontend/README.md`).
  Per-sector strings are `<key>_<service>` overrides in `i18n.js` (e.g. "Fine" for served). The fuel panel: fuel % stepper
  (with "90-octane 1.050 JD/L → X", display only, from `config.js`), bus and taxi fares (follow fuel / freeze / custom %),
  cash support (group chips + JD/month), transport vouchers. The travel map has no hub pins (§14).
- FastAPI serves `nas-frontend/` at `/` (mounted after the API routes; a test checks routes still win). `config.js` uses the page's
  own origin as the API (falls back to http://localhost:8000 when opened on :3000). `?api=<url>` and `?offline=1` (no map tiles) work.
- `api.js` adaptations: `/sensitivity` sends the fix's `policy`; backend `details[]` → UI `detail[]` rows.
- Policy panel: offices (each with a trash button to close it) + **"افتح مكتباً / Open an office"** (area select; picks the real
  CSPD site in that area if any), rules, **"حماية الفئات / Protections for groups"** (group chips for walk-in, fee discount with a
  % stepper, transport voucher with a JD stepper, home visits switch + groups + slots stepper, hybrid switch), mobile units, fee, visits.
  Impact panel shows "home visits used N / slots" when home visits are on. The citizen card hides travel facts for a home visit.
- The citizen drawer scrolls instead of squeezing its rows (`grid-auto-rows: max-content`), fixed on 2026-10-09.
- **2026-10-10 UI pass** (details in `nas-frontend/README.md`): hero card shows today → policy → after fix plus the hero note; fix
  cards show people counts ("left out 9 → 1 · hardship 195 → 90"), "N changes", and the AI card only its rationale; the AI-hidden
  message comes from `ai_proposal.status` (never "didn't beat" when the AI didn't answer); KPI cards show counts ("796 of 1,000")
  and pulse on change, deltas after a fix are vs the policy before the fix (toggle to "vs today"); "Who is left out" uses the
  backend's `left_out_by_reason`; a 4xx restores the last good policy (no Retry; Retry only on network/5xx) and the panel can't
  produce hours the engine rejects; robustness runs on badge click, after fixes load, and after Apply (not on every edit);
  header chip from `/llm/status` (AI live / cache only / resting); "nobody's outcome changed" note; map fits the central 90% of
  residents, labels offset from pins; group glossary ("i" next to the equity title); gender-neutral Arabic card labels; contrast
  ≥ 4.5:1 everywhere; focus trap in modals; per-route timeouts (30 s `/fixes` and `/report`); the local dialect voice template is gone
  (English mode uses the backend's `summary_en`); heroes stay clickable under the drawer at 1280×720; phone layout reordered.
- Verified end to end, locally and on Render, in Arabic and English: presets, map recolour + rings, hero cards with AI voices, fixes +
  AI fix + apply, robustness badge/table, free-text parse (demo sentence matches the preset exactly; unsupported message), report,
  backend-down error screen + Retry, `?offline=1`, dragging an office pin, every protection, opening/closing an office.

## 10. Open items / known caveats
1. **Pending online warm runs (57 xfails in `pytest -q`: ID renewal 1, travel 28, medical exemption 28):**
   - **ID renewal, 1 call:** Amina (c_0020)'s voice after the **AI fix** (every Gemini voice model hit its daily limit on the night
     of 10-10; voices never go to Groq). Everything else for ID renewal is cached: all 61 rehearsed requests, all other hero
     voices, the reports with and without a fix.
   - **Everyday travel, nothing warmed yet (28 xfails):** 12 rehearsed parses, the `/fixes` answer on `fuel_plus_25_fares`
     (explanations + an AI-proposed fix), 12 hero voices (Mustafa, Rana, Issa × today / demo / top fix / AI fix) and 3 reports
     (no fix / top fix / AI fix). Until then the travel sector shows templates (honest, never blank).
   - **Medical exemption, nothing warmed yet (28 xfails):** 12 rehearsed parses, the `/fixes` answer on
     `exemption_online_only`, 12 hero voices (Salma, Abdullah, Ali × today / demo / top fix / AI fix) and 3 reports.
     About 28 calls, plus up to 6 for `find_ai_fix`. Templates until then.
   - **Totals:** id_renewal 1 call, everyday_travel ~24 (+ find_ai_fix), medical_exemption ~28 (+ up to 6).
   - **Network:** the venue network has a **FortiGate TLS interception on googleapis / groq** (AI calls fail with certificate
     errors). Run the warm steps on a **phone hotspot**.
   - **Steps, from `backend/`, after the Gemini reset (~10:00 Amman):**
     1. `.venv/Scripts/python -m scripts.warm_cache --service everyday_travel --parse-only` (12 calls; Groq can do these)
     2. `.venv/Scripts/python -m scripts.warm_cache --service everyday_travel` (~12 calls: fixes 1, voices 9, reports 2)
     3. optional: `.venv/Scripts/python -m scripts.find_ai_fix --service everyday_travel` (if step 2 shows no verified AI fix),
        then step 2 again for the 3 AI-fix voices and the AI-fix report
     4. `.venv/Scripts/python -m scripts.warm_cache --service id_renewal` (Amina, 1 call)
     5. `.venv/Scripts/python -m scripts.find_ai_fix --service medical_exemption` (up to 6 calls), then
        `.venv/Scripts/python -m scripts.warm_cache --service medical_exemption` (~28: 12 parses, 1 fixes, 12 voices, 3 reports)
     6. `DEMO_OFFLINE=1 .venv/Scripts/python -m scripts.warm_cache` must end with "No misses" (or list only what you chose to skip)
     7. `pytest -q`: the warmed entries become XPASS; then drop the xfail marks in `tests/test_cache_hits.py`
        (`travel_pending` / `TRAVEL_PENDING`, `exemption_pending` / `EXEMPTION_PENDING`, on the hero/fixes/report tests and on the
        rehearsed requests) and Amina from `PENDING_VOICES`
     8. commit `backend/cache/` (and `tests/test_cache_hits.py`), push, redeploy Render by hand.
   Voices for citizens served by home visits are generated on click (AI or template); none are pre-cached.
2. **Fully offline demo: DONE.** Leaflet 1.9.4, Phosphor icons (regular + fill) and IBM Plex (arabic/latin subsets) are vendored in
   `nas-frontend/vendor/` (~1 MB). Verified: with `?offline=1` the page makes no request outside the server, in Arabic and English.
   Add `DEMO_OFFLINE=1` in `.env` and nothing needs the internet.
3. **Native-speaker review** of the cached voices: the user said leave it.
4. Staff / operating-cost readout: **ruled out of scope** by the user (on stage: "operating cost is the next module").
5. (Removed 2026-10-10: the frontend's dialect voice template is gone; a failed `/citizen/voice` shows an i18n "couldn't load" line with Retry.)
6. The public URL can spend the free AI quota; share it only with judges/team.
7. A fee discount alone changes no statuses on the demo path (hardship there comes from appointments and helpers, not cost);
   it shows in the average cost. Opening a Marka office on the demo path also moves no statuses (it does on `consolidate`: 85.0 → 85.6).
   Both are honest results; don't tune them. Closing every office on Thursdays moves nobody either (baseline and demo path):
   Nas has no capacity/queue model, so open days are interchangeable (CLAUDE.md §14 has the Q&A answer).

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

## 14. Deliberately on hold (user decision, 2026-10-10)
- **Three engine-semantics fixes** that would change results: (a) workers can't use a slot that ends before their shift starts
  (`engine.py` rule 5; 2 baseline citizens would go hardship → served, demo path unchanged); (b) `NO_TRANSPORT` is only assigned to
  wheelchair users, the spec says anyone with no mode (reason chips only); (c) the worsens-a-group check skips `student`. Kept as is
  so the rehearsed numbers stay exact; revisit after the demo.
- **Western digits in the fix titles** (`fixgrid.py` "٩–٢", "٧"): `title_ar` is part of the cached `/fixes` key for the demo path, so
  changing it would lose the cached AI fix. Change only together with a re-warm.
- **Area mapping** (`jabal_al_hussein` holds Basman residents; `wehdat` spans 14 km, so 23 citizens near the real Jabal Al-Hussein
  office are charged 2 bus transfers): a labelled limitation. Fixing it changes every outcome, the heroes and the whole AI cache.
- **Everyday travel (2026-10-10):** nothing new on hold except two known limits, both "next module" on stage:
  (a) **no mode switching with price**: a driver who would take the bus at +50% still drives, and a rider never buys a car;
  (b) **no hub pins on the travel map**: the backend sends no hub coordinates to the UI, so the map shows citizens only.
- **Medical exemption (2026-10-10 evening):** two known limits, both honest findings, not tuned away:
  (a) **the proxy rule rarely matters**: a relative may make the visits, but helpers work the same Sun-Thu hours and are free
  only from `HELPER_FREE_FROM` (16:00), after the unit closes (15:00); so in every preset nobody uses `helper_visit` and
  `exemption_no_proxy` equals `exemption_today`. The lever exists (and works in tests) for the free-text box and for a
  Saturday or late intake day.
  (b) **the Royal Court coordinates are a fallback** (±1 km, Raghadan; Nominatim found nothing) and have no OSRM rows, so trips
  to the unit use straight-line × `ROAD_FACTOR`. Fixing them changes exemption outcomes, heroes and the (not yet warmed) cache.

## 12. Useful commands (from `backend/`)
```bash
.venv/Scripts/python -m uvicorn app.main:app --port 8000        # app at http://localhost:8000
.venv/Scripts/python -m pytest -q                                # offline tests (incl. the demo guard)
.venv/Scripts/python -m app.data.seed_census --install           # regenerate population (user must run it: auto mode blocks it)
.venv/Scripts/python -m app.data.fetch_map_data matrix           # re-fetch OSRM times after a population change
.venv/Scripts/python -m scripts.pick_heroes                      # re-pick heroes for the demo scenario
.venv/Scripts/python -m scripts.find_ai_fix                      # search for a verified AI fix (uses AI quota)
.venv/Scripts/python -m scripts.warm_cache                       # warm the AI cache (uses AI quota; only misses are requested)
.venv/Scripts/python -m scripts.warm_cache --parse-only          # just the rehearsed free-text requests (Groq can do these)
.venv/Scripts/python -m scripts.warm_cache --service everyday_travel [--parse-only]   # one sector only (also: find_ai_fix --service ...)
.venv/Scripts/python -m scripts.warm_cache --service medical_exemption                # the exemption sector
.venv/Scripts/python -m app.data.seed_daily                      # regenerate daily_trips.json (seed 42; only after a population/hub change)
.venv/Scripts/python -m app.data.seed_insurance                  # re-add has_health_insurance + "uninsured" (seed 42; after every seed_census --install)
```
On Windows/Git Bash, set `PYTHONIOENCODING=utf-8` when printing Arabic to the console. With `DEMO_OFFLINE=1` in front,
`warm_cache` only reads the cache and ends with a MISSES list: a quick way to check that every rehearsed answer is still cached.

## 13. Timeline (git, newest first, abridged)
**2026-10-10 (medical exemption):** `225ac27` exemption AI layer: service prompts, exemption voice facts and templates, proposal
limits, rehearsed requests, per-service `warm_cache` · `397b8e4` frontend: medical-exemptions card, proxy switch, not-applicable
dots, KPIs over the uninsured, intake offices, helper-visit card · `da8d79f` exemption engine: `uninsured` tag (seed 42, 44.1%),
Royal Court site, service rules (2-hour visits, eligibility, proxy visits), presets, fix grid, heroes · `a200815` exemption
contract: **2 constants frozen before use** (`EXEMPTION_VISIT_MINUTES`, `UNINSURED_RATE_BY_BAND`), Service/Group/Policy schema,
services registry · `53e6302` docs for the fuel sector, verified fuel and health-insurance anchors · `48793b4` logo.
**2026-10-10 (everyday travel):** `9237f55` start state: neutral citizen dots in the accent blue · `46aa477` research doc on the
Amman uninsured rate (checked figures now in anchors.json) · `b5b6d45` frontend: sector list start state, fuel-price panel
(fuel, fares, cash support), trip card, travel KPIs, `?sector=` · `e70cd11` travel AI layer: service-aware prompts, voice facts
and templates, proposal limits, per-service `warm_cache`, rehearsed fuel requests · `415ceba` travel engine: regular trips under
fuel and fare prices, cash support, fix grid, robustness, presets, heroes · `3b1cde0` travel contract: **7 constants frozen before
use**, Policy/outcome schema, services registry, trips data restored from `3a4e645`.
**2026-10-10 (review pass):** `c3b95f0` review fixes · `1cc23da` pitch outline · `9b344df` demo runbook · `35a0edf`/`f10992e`
rehearsals and warmed cache · `a31557d` honest anchoring wording · `c0e364a`/`2d91d90` frontend and AI-layer fixes.
**Before:** `dd16cc3`/`6d6c76f`/`8b99eff` road closures removed · `5ab38d2` protections panel + open/close offices in the UI ·
`f292274` five group protections in engine + AI · `0387862` HOME_VISIT_MINUTES / PICKUP_MINUTES set before use ·
`315ba11`..`3a4e645` road closures + everyday trips (since removed) · `4528c27` first HANDOFF ·
`a0a1745` start-up warm-up · `865f005` Render blueprint · `7913c13` one server for UI + API · `70c33b9`/`d289820`/`238bec0` clean-up,
seamless connection, docs · `5a946fc`/`979e22b` frontend connected and fixed · `5234425` real 7-office baseline + consolidation demo ·
`c635152` فصحى voices · `a34adff` model chains · `75d42cb` census population · `923ee74` engine API + AI layer · `6feaa3c` assumptions frozen.

## 15. Everyday travel (fuel prices) sector (DONE, 2026-10-10)
The second sector, `service: "everyday_travel"` (UI name "أسعار المحروقات / Fuel prices"). Same core principle: the engine
(`sim/travel_service.py`, deterministic, no AI) decides every number; the AI parses, voices, reports and proposes; the engine
verifies. **Fixes never change the fuel price**: it is the government decision being tested.

**The model**
- **One regular trip per citizen**: 948 of 1,000 have one (320 to work and 164 to university, 5 days a week; 464 to their
  nearest public hospital, once a week); the other 52 (16-17-year-olds) have none and count as fine at zero cost. From
  `daily_trips.json` (made by `seed_daily.py`, seed 42), `hubs.json` (25 destinations) and `hub_matrix.json` (OSRM), restored
  from the removed everyday-trips module (`3a4e645`) in `3b1cde0`.
- **Mode by profile**: own car if they have one; wheelchair users go in a helper's car (if they have a helper) or by taxi;
  everyone else by bus (with `bus_transfers` as in ID renewal). **No mode switching with price** (next module).
- **Monthly cost** = round-trip cost × days per week × `WEEKS_PER_MONTH` (4.33). A fuel change of X% scales the car's per-km
  cost by X × `FUEL_SHARE_OF_CAR_COST` (0.6); bus fares follow by `BUS_FARE_FUEL_PASS_THROUGH` (0.3) and the taxi per-km tariff
  by `TAXI_FARE_FUEL_PASS_THROUGH` (0.5), **unless** the policy sets `bus_fare_change_pct` / `taxi_fare_change_pct` explicitly
  (`null` = follow fuel, `0` = freeze, N = that change). `cash_support` (`[{groups, amount_jd_month}]`, a citizen gets their
  largest amount) comes off the monthly cost; `transport_vouchers` cut the bus/taxi round-trip fare, never car costs (floor 0).
- **Status** by the share of per-capita income the trip takes each month (`INCOME_JD_MONTH` 130 / 350 / 950 JD by band = the
  medians of the generator's own synthetic incomes, rounded; not a statistic): **fine** < 10% (`TRANSPORT_SHARE_SQUEEZED`),
  **squeezed** 10-20%, **priced out** ≥ 20% (`TRANSPORT_SHARE_PRICED_OUT`). Internally these are served / hardship / left_out,
  so compare, equity bars, worst groups and the fix grid work unchanged. Reasons: `TRANSPORT_OVER_BUDGET` plus `FUEL_COST`
  (car / helper_car) or `FARE_COST` (bus / taxi).
- **Outcome fields** (`CitizenOutcome`, null for ID renewal): `purpose`, `days_per_week`, `monthly_cost_before_jd` (today's
  prices), `cost_jd` (after the policy), `extra_jd_month`, `income_share_pct`, `cash_support_jd_month`. KPIs add
  `avg_monthly_cost_jd`, `avg_extra_jd_month`, `total_extra_jd_month`, `avg_income_share_pct`, `n_cash_support`, `by_purpose`, `by_mode`.
- **Freeze rule kept**: all 7 new constants (`WEEKS_PER_MONTH`, `INCOME_JD_MONTH`, `TRANSPORT_SHARE_SQUEEZED`,
  `TRANSPORT_SHARE_PRICED_OUT`, `FUEL_SHARE_OF_CAR_COST`, `BUS_FARE_FUEL_PASS_THROUGH`, `TAXI_FARE_FUEL_PASS_THROUGH`) are
  ASSUMPTION and were committed in **`3b1cde0` before any travel scenario ran**. ID-renewal outcomes are byte-identical
  (sha pinned in `tests/test_travel.py`), and the travel levers are no-ops at their defaults, so ID-renewal cache keys didn't move.
- **Fix grid** (travel): cash support (low_income 8 / 14 / 20 JD, no_car / worker / student 14 JD), freeze bus fares, freeze taxi
  fares, vouchers 0.5 JD for low_income / no_car, plus pairs of the top singles. **Robustness** perturbs
  `FUEL_SHARE_OF_CAR_COST`, `BUS_FARE_FUEL_PASS_THROUGH` and `TRANSPORT_SHARE_SQUEEZED` by ±20% (6 runs).

**The numbers** (engine output, re-checked with `DEMO_OFFLINE=1`, `compare(travel_today, preset)`; table in §6)
- Today (`travel_today`): 72.2 fine / 17.8 squeezed / 10.0 priced out. Low-income daily bus commuters (work or university)
  already spend a median **30%** of income on the trip today: they were priced out before any fuel rise.
- `fuel_plus_5` (October 2026: +0.05 JD/L on 90-octane ≈ +5%): 71.6 / 18.3 / 10.1, 7 people worse, **all car drivers**.
- `fuel_plus_25` (fares mostly held): 70.6 / 18.6 / 10.8, 24 worse, **all car drivers** (regulated fares lag fuel).
- **`fuel_plus_25_fares` (travel demo: fuel +25% and bus/taxi fares +25%, as after the 2012 hike): 70.2 / 14.6 / 15.2, 72 worse
  (48 bus riders, 24 drivers), worst groups worker, offline, low_income; average extra 4.54 JD/month.**
- `fuel_plus_25_support` (the same + 14 JD/month for low_income, the top of NAF's 8-14 JD range): 73.8 / 11.7 / 14.5:
  14 JD does not undo a 25% fare rise for a daily commuter.
- **Top grid fix** on the demo: "14 JD/month cash support for people without a car + freeze bus fares": priced out 15.2 → 8.0
  (**−7.2 pts**; squeezed rises 0.9 pts as people move up out of priced out). Runner-up ties it with a 0.5 JD voucher instead of
  the freeze; third: freeze bus fares + 14 JD for workers (−6.8).
- **Robustness: ranking held 5/6, fix helps 6/6, stable top group `worker`.** At `TRANSPORT_SHARE_SQUEEZED` × 1.2 (0.12) the
  second-worst group becomes **no_car** instead of offline. Show it honestly ("worker is first in every run; second place
  depends on where 'squeezed' starts") and claim only `worker`.

**Heroes** (`heroes.json`, `service: "everyday_travel"`, scenario `fuel_plus_25_fares`)
- **c_0627 Mustafa** (23m, low income, bus to Wehdat with 1 transfer, work, 5 days): 38.97 → 48.71 JD/month, 30.0% → 37.5% of
  income: priced out before and after; with the top fix 24.97 JD, 19.2%: **squeezed**.
- **c_0883 Rana** (18f student, middle income, bus with 2 transfers to Applied Science University): 58.45 → 73.07 JD, 16.7% → 20.9%:
  squeezed → **priced out** → squeezed with the fix (44.45 JD, 12.7%).
- **c_0982 Issa** (29m, middle income, drives 44 min each way to King Hussein Business Park): 61.5 → 70.72 JD, 17.6% → 20.2%:
  squeezed → priced out, and **the top fix does not reach him** (cash for people without a car + a bus-fare freeze does nothing
  for a middle-income driver). Kept on purpose as the "who does the fix still miss?" moment; a judge can try cash support for
  workers live: the third grid fix (freeze bus fares + 14 JD/month for workers) brings Issa back to squeezed (56.72 JD, 16.2%),
  at −6.8 pts priced out overall instead of −7.2.

**AI layer** (`e70cd11`): travel prompts (parse knows the fuel/fare/cash levers and that electricity, diesel-only or mode
changes are unsupported), voice facts (trip, mode, transfers, JD before/after, share of income) and templates, proposal limits
(an AI fix may not change the fuel price), per-service `warm_cache` / `find_ai_fix`. **The travel cache is not warmed yet**:
steps and the hotspot note in §10.1.

**Real figures for this sector** (anchors.json, §5): October 2026 fuel prices (Jordan News, CITED) and NAF fuel support 8-14
JD/month (Ammon News, CITED). They give context to the presets; no constant comes from them.

## 16. Medical exemptions sector (DONE, 2026-10-10 evening)
The third sector, `service: "medical_exemption"` (UI name "الإعفاءات الطبية / Medical exemptions"): a resident **without
health insurance** applies for a **Royal Court medical exemption**. Same core principle: the engine decides every number; the
AI parses, voices, reports and proposes; the engine verifies. It runs on the **same in-person engine as ID renewal**
(`engine.py` `SERVICE_RULES`), so channels, travel, helpers, protections, the fix grid and the robustness check are shared.

**The model**
- **Who applies** (`seed_insurance.py`, seed 42): each citizen is uninsured with probability `UNINSURED_RATE_BY_BAND`
  (low 0.65 / middle 0.45 / high 0.20, ASSUMPTION calibrated to the DoS 2015 Amman figure of 44.8% of Jordanians uninsured,
  all ages; adults are higher because under-6s are all insured). Result: **441 of 1,000 uninsured (44.1%; low 61.0%,
  middle 44.6%, high 17.5%)**, field `has_health_insurance: false` and tag `uninsured` (appended last; the other tags are
  unchanged). **Re-run `python -m app.data.seed_insurance` after every `seed_census --install`.** The other two sectors ignore
  both, and `tests/test_exemption.py` pins their outcomes by sha256 (byte-identical).
- **Insured = not applicable:** the 559 insured citizens get `channel: "not_applicable"` and are **excluded from every
  percentage**; `kpis.n_eligible` = 441, `kpis.n_not_applicable` = 559. Home visits never go to them.
- **Today's process** (`exemption_today`): one office, the Royal Court's Citizen Services Unit (`royal_court_csu`, fallback
  coordinates, §5), 08:00-15:00 Sun-Thu (**ASSUMED**: no published hours), **2 visits** (apply with the medical report; return
  for the letter, as press reports describe it), fee 0, **no online channel**. One visit at the counter =
  `EXEMPTION_VISIT_MINUTES` = 120 (ASSUMPTION: queue + the doctor's review; no published queue time).
- **Channels:** `royal_court_unit`; `intake_<cspd office>` ("Exemption intake at …", at the 7 real CSPD sites); generic intake
  offices in an area; `mobile:<area>:<day>` ("Mobile intake day in …"); `online` ("Online (Sanad)" / "عبر منصة سند");
  `home_visit`; `not_applicable`.
- **Proxy rule** (`Policy.proxy_allowed`, `null` = the service default, which is **on** for medical exemption and off for ID
  renewal): the citizen's helper (a first-degree relative) may make the visits instead, by the household's mode, only in the
  helper's free time (Fri/Sat, or Sun-Thu from `HELPER_FREE_FROM` 16:00); mode `helper_visit`, always a hardship (someone
  else loses the time), no work missed for the citizen. **Honest finding:** it changes nothing in the presets, because the unit
  closes at 15:00 before helpers are free; `exemption_no_proxy` is identical to today and nobody uses `helper_visit` in any
  preset or in the top fix. The lever stays for the free-text box and the panel switch.
- **Fix grid:** the ID-renewal grid in exemption wording (16 mobile intake days, Sat/Thu 09:00-14:00, walk-in) + toggles:
  **hybrid** (apply on Sanad, one short visit to collect; under online-only it reopens the unit), **regional intake** (intake at
  the 7 CSPD offices with the unit's hours), and, with offices in play, late Thursday, no appointments, accessible, proxy (when
  not already allowed). Under an online-only scenario an in-person fix first lifts `online_only` (Sanad stays on). Pairs of the
  top singles, ranked as §6.4. **Robustness** perturbs `EXEMPTION_VISIT_MINUTES`, `BUS_WAIT_PLUS_TRANSFER_MIN`,
  `HARDSHIP_THRESHOLD` by ±20%.
- **Freeze rule kept:** the 2 new constants were committed in **`a200815` before any exemption scenario ran**.

**The numbers** (engine output, re-checked with `DEMO_OFFLINE=1`, `compare(exemption_today, preset)`; percentages of the 441)
- **Today: 0.0 served / 74.8 hardship / 25.2 left out** (0 / 330 / 111 people). **Nobody is served today**: two 2-hour visits
  already equal the 4-hour `HARDSHIP_THRESHOLD`, so today's process is a hardship for everyone who needs it, before any travel.
  That is a frozen-constant result, not tuning; say it plainly.
- **`exemption_online_only` (DEMO, "applications only through Sanad"): 77.6 / 14.1 / 8.4 (342 / 62 / 37), 364 better off,
  30 worse.** The 30 are **all offline residents with no helper**: they lose the counter and have nobody to apply online for
  them (offline left out 29.3% → 37.4%). Worst groups **offline, elderly**. **Robustness 6/6, fix helps 6/6**, stable top offline.
- **Top grid fix:** "Exemption intake at the 7 Civil Status offices + a Saturday mobile intake day in Downtown" (2 changes):
  **left out 8.4 → 0.2 (37 → 1)**, hardship 14.1 → 22.2 (people lifted out of left out land in hardship). Tied on the numbers
  with the same pair using Jabal Al-Hussein or Tabarbour for the Saturday day.
- `exemption_hybrid` (today + apply on Sanad, collect the letter): 77.6 / 20.9 / 1.6, 364 better, nobody worse.
- `exemption_regional` (the unit + intake at the 7 CSPD offices, no online): 0.0 / 87.1 / 12.9, 54 better; worst groups
  worker, elderly; **robustness 5/6** (at `EXEMPTION_VISIT_MINUTES` × 1.2 the second group becomes low_income), fix helps 6/6,
  stable top worker.
- `exemption_no_proxy`: identical to today (the proxy finding above).
- **The sector's story:** *"Sanad helps most people, but 30 offline people with nobody to help them lose the counter; the
  engine finds the mix that reaches them."*

**Heroes** (`heroes.json`, `service: "medical_exemption"`, scenario `exemption_online_only`; all three: hardship today →
left out under Sanad-only → hardship with the top fix)
- **c_0931 Salma** (72f, Wehdat, no car, low digital literacy, no helper): `LOW_DIGITAL_LITERACY`; the fix reaches her through
  the **Downtown Saturday intake day** (by bus).
- **c_0497 Abdullah** (42m, works 07:00-16:00 Sun-Thu, car, low digital literacy, no helper): reached by the Saturday intake day.
- **c_0188 Ali** (77m, Marka, limited mobility, no smartphone, no helper): `NO_SMARTPHONE`, `LOW_DIGITAL_LITERACY`; reached
  through **`intake_marka`** (by taxi).

**AI layer** (`225ac27`): exemption prompts (parse knows Sanad, intake offices, mobile intake days, the proxy switch, and that
who is insured, the exemption amount, or staff/doctors are unsupported), voice facts (how they applied: in person / Sanad /
hybrid / a relative / home), templates, proposal limits (an AI fix may use only offices, online, mobile units, appointments,
hybrid, proxy and the protections; never the service, who is insured, the fee or the number of visits). Insured citizens get a
one-line template, never an AI call. **Nothing is cached yet** (28 xfails); warm steps in §10.1 (on a hotspot):
`python -m scripts.find_ai_fix --service medical_exemption` (up to 6 calls), then
`python -m scripts.warm_cache --service medical_exemption` (~28: 12 parses, 1 fixes, 12 voices, 3 reports), then commit
`backend/cache/` and drop the exemption xfail marks in `tests/test_cache_hits.py`.

**Rehearsed requests** (`demo_requests.json`, `service: "medical_exemption"`): on `exemption_today`: let relatives apply
(ar; already the default), "The patient must come in person" (= `exemption_no_proxy`), open intake at the Civil Status offices
(ar), "Accept applications only through Sanad" (= the demo), apply on Sanad and collect at the office (ar, = hybrid), "Add a
mobile intake day in Marka on Saturday", 30 home visits for people with disabilities (ar); on `exemption_online_only`: let the
elderly apply at the office (ar) and "Open the office for people without a smartphone" (both reopen the unit for **everyone**:
Nas can't limit an office to one group, and the change list must say so); **unsupported**: "Make everyone insured", raise the
exemption amount (ar), "Add more doctors to the committee".

**Real figures for this sector** (anchors.json, §5): DoS 2015 (ANCHORED, now used through `UNINSURED_RATE_BY_BAND`), JPFHS
2023 (ANCHORED, cross-check), and the exemption process from press reports (CITED_UNVERIFIED: Al Rai, Ad-Dustour).

## 17. Pitch deck: the Gamma prompt (master copy: `GAMMA_PROMPT.md`)

Paste the fenced block into Gamma (Create new → Paste in text → "Preserve" text; 9 cards, 16:9). Every number is verified (research notes, `anchors.json`, or engine output in §6, §15, §16).

```
Create a 9-slide pitch deck for "Nas (ناس)", a policy simulator for Jordan's public services, built by a team of 3 at the AI Quest hackathon at Al Hussein Technical University. Audience: a judging panel of technologists and public-sector people. Tone: confident, precise, evidence-led. Language: English, with the Arabic name ناس on the title slide.

RULES FOR CONTENT
- Use exactly the numbers below. Do not add statistics, market sizes or claims that are not listed.
- Every number is followed by its source in brackets, e.g. "95.6% use the internet (MoDEE ICT Survey 2024)". Keep every bracketed source on the slide, exactly as written, rendered as small grey caption text right after the figure. Never drop or merge them.
- "(Nas simulation)" means the number is our own engine's output; keep that tag too.
- Always say "synthetic citizens, AI-voiced". Never say "AI citizens".

VISUAL DIRECTION (make it rich, not plain)
- Palette: deep navy #0F1E2E for title and section slides, warm sand #F5EFE6 for content slides, accent green #2E9E6B (from the logo), with amber #E0A526 and coral #D9534F used only for the three status colours (green = served, amber = hardship, coral = left out).
- Typography: bold geometric sans for headings, large numbers (60–96 pt) for key stats, short lines.
- A faint Arabic geometric (girih) line pattern as texture on the dark slides.
- Imagery: warm, photographic Amman — white limestone houses stacked on hills, Downtown streets, a bus stop, an older woman holding a phone. No robots, no glowing brains, no stock "AI" clichés.
- Vary the layout on every slide: full-bleed image, three cards with icons, big-number stat row, a horizontal flow diagram with arrows, a two-column comparison table. Use icons generously (map pin, bus, smartphone, wheelchair, shield, check mark).
- Where an image placeholder is marked, leave a clearly labelled frame for our screenshot.

---

SLIDE 1 — Title (dark navy, full-bleed photo of Amman's hills at golden hour, darkened)
Large: "ناس · Nas"
Tagline: A wind tunnel for public services.
Subtitle: Every policy leaves someone out. Nas shows you who, why, and how to fix it, before you launch.
Footer chips: AI Quest @ HTU · Smart Society & Public Services · Team of 3

---

SLIDE 2 — The problem (sand background; big-number stat row of four, then one statement)
Title: Policies are tested on real people, after launch.
Lead line: When an office closes, hours are cut, or an online appointment becomes required, nobody knows in advance who can no longer reach the service. The people who fall through are the ones least able to complain: the elderly, people with disabilities, people without a car, people who cannot use an app alone.
Stat row (four big numbers, each with its caption and source):
- 95.6% of people in Jordan use the internet (MoDEE ICT Survey 2024)
- 80.2% of people aged 65+ own a smartphone (MoDEE ICT Survey 2024)
- only 38.1% used any e-government service (MoDEE ICT Survey 2024)
- only 3.7% of people aged 65+ use a computer (MoDEE ICT Survey 2024)
Below the row: The gap is not devices, it is use. And services are moving online fast: 85.5% of targeted government services are already digital, with 100% targeted by the end of 2026 (Petra News Agency).
Callout box: The UN Special Rapporteur on extreme poverty warns that digital-only public services can exclude the people who need them most (UN General Assembly report A/74/493, 2019).
Bottom line, large type: "Who does this policy leave out?" Today, no one can answer that before launch.

---

SLIDE 3 — Meet Nas (split layout: text left, screenshot right)
Title: Test a policy on 1,000 synthetic citizens before it touches a real one.
Three steps with icons, left to right:
1) Change a policy: use the controls, or type a sentence in Arabic or English ("close the counters at 1 PM and require online appointments").
2) Watch the map: every citizen is run through the new policy and lights up green (served), amber (served with hardship) or coral (left out).
3) Fix it: Nas searches for fixes, verifies each one, and shows who comes back. Click any citizen and they explain their outcome in their own words, in Arabic.
Strip at the bottom, three sector cards with icons:
- ID renewal (Civil Status offices, online, appointments, mobile vans)
- Fuel prices (each citizen's regular trip to work, university or hospital under a price change)
- Royal Court medical exemptions (how residents without health insurance apply)
Note: a new sector is new data and rules on the same engine, population and interface.
[Image placeholder: screenshot of the Nas map with green, amber and coral dots and an open citizen card]

---

SLIDE 4 — A digital Amman, built from published figures (sand background; a "published figure → people in Nas" table with arrows, plus a 10×10 dot-grid illustration)
Title: Every share in Amman becomes people in Nas.
Lead line: Our 1,000 synthetic citizens are generated so that each published share becomes the same share of people. If 47% of residents are women, 470 of our 1,000 citizens are women.
Table, three columns: "Published figure" → "In Nas (out of 1,000)" → "Source":
- 47% women → 470 women, 530 men (Department of Statistics, via The Jordan Times)
- 95.6% use the internet → 956 have a smartphone (MoDEE ICT Survey 2024)
- 38.1% used an e-government service → 381 have (MoDEE ICT Survey 2024)
- 62.5% of men and 16% of women are in the labour force → 331 of 530 men, 75 of 470 women (World Bank Gender Data Portal)
- 49.3% of people aged 65+ have a functional difficulty → 32 of our 65 elderly (UNFPA Jordan country profile 2024)
- 44.8% of Amman's Jordanians have no health insurance → 441 uninsured (Department of Statistics, Health Insurance in Jordan, 2015 Census)
- Each of Amman's 22 districts gets its census share, e.g. Basman 10.62% → 106 residents, Marka 4.21% → 42 (2015 Census district populations)
Side panel, "Real places": every home sits on a real residential street (OpenStreetMap); travel uses real road distances from each home to every office (OSRM routing on OpenStreetMap); the baseline is the 7 real Civil Status offices in Amman, open 08:30–15:30 Sunday to Thursday, with the JD 2 renewal fee (Civil Status and Passports Department).
Footer: Generated with a fixed random seed, so every run uses the same 1,000 people. Synthetic by design: no personal data is ever used.

---

SLIDE 5 — How the engine decides (technical; a horizontal flow diagram of four boxes with arrows, then a formula strip)
Title: A deterministic engine decides every outcome.
Flow, four boxes:
1) Policy in: offices, opening hours per day, online on/off, appointments, mobile vans, fees, and protections for groups (walk-in for the elderly, fee discounts, transport vouchers, home visits).
2) Every option, for every citizen: each office, each mobile van and online; every open day; every way to get there (own car, a relative's car, bus with transfers, taxi). Each option is checked against the citizen's work hours, mobility, smartphone, digital skills, income and whether a relative is free to help.
3) Pick the easiest option: burden = hours lost + cost in JD + work hours missed (weighted). Nas picks the option with the lowest burden.
4) Outcome with reasons: served (easy, no help needed), served with hardship (needs a relative, misses work, or a heavy burden), or left out (no option works), each with reason codes such as "too far", "no smartphone", "clashes with work hours".
Strip below, three metrics with icons:
- 1,000 citizens simulated in about 50 milliseconds (Nas simulation)
- Fix search: about 30 candidate fixes (mobile vans in 8 areas, longer hours, rule changes, and pairs of the best) scored and ranked in about one second (Nas simulation)
- Robustness: the 3 most uncertain settings are moved ±20% in 6 re-runs; on the ID-renewal demo, the groups hit hardest stay the same in 6 of 6 (Nas simulation)
Footer: All 35 engine settings are documented in an open assumptions table and were fixed before any scenario ran. Same input, same answer, every time.

---

SLIDE 6 — Where the AI fits, and how we keep it honest (technical; three cards in a row, then a verification banner)
Title: The engine decides. The AI explains. The engine verifies.
Card 1, "Understands": turns an official's Arabic or English sentence into a structured policy and shows it as an "understood as" list before anything is applied. Example: "خلّوا الكاونترات تسكر الساعة 1 الظهر، وما حدا يراجع المكتب إلا بموعد مسبق أونلاين" → close at 13:00 · online appointment required.
Card 2, "Gives a voice": each citizen explains their outcome in clear Modern Standard Arabic, using only the numbers the engine computed. Example: "أحتاج إلى حافلتين ونصف يوم، وابني لا يستطيع أخذ إجازة ليوصلني".
Card 3, "Proposes": explains the engine's top 3 fixes, writes the official's impact report, and suggests one fix nobody listed.
Verification banner, three check-mark items:
- Grounding check: any AI sentence containing a number the engine did not compute is rejected.
- Every AI-proposed fix is re-run through the engine and shown only if it beats the best engine fix without hurting any group, with a badge: "AI-proposed · verified".
- Every AI task has a template fallback and every answer is cached, so the full demo runs even with no internet.
Footer tech strip (small icons): Python · FastAPI · Pydantic schemas · Leaflet + OpenStreetMap · OSRM · Gemini and Groq (provider-agnostic) · 285 automated tests · fully bilingual Arabic/English interface.

---

SLIDE 7 — Who pays, and why now (business; left: three "why now" cards; right: model and a comparison table)
Title: Jordan now requires impact assessment before launch.
Why now, three cards:
- The Good Regulation and Impact Assessment System No. 16 of 2025 has been in force since September 2025; the Prime Ministry's unit had received 45 assessment studies by April 2026 (Ad-Dustour; Petra News Agency).
- The Digital Transformation Strategy 2026–2028 tracks what Nas measures: use of digital services by vulnerable groups, access to service centres, customer effort, and plans predictive models for policy effectiveness (MoDEE Digital Transformation Strategy 2026–2028).
- The Digital Inclusion Policy 2025 names the elderly, people with disabilities, women and remote residents as priorities and plans incentives for startups serving them (MoDEE Digital Inclusion Policy 2025).
First buyers: the Prime Ministry's impact assessment unit and the ministries it reviews; 28 government entities are in the public-sector reform programme (Ammon News). Donor-funded digital government programmes, such as Jordan's World Bank-supported digital transformation programme of about $549M (World Bank, project P180291).
Business model: SaaS per service and agency, plus a calibration engagement. Target price $30K–$75K per agency per year. Low running cost: a CPU-only engine and cached AI calls.
Precedent: UK regulators already require banks to assess the impact on vulnerable customers before closing branches (UK Financial Conduct Authority, FG22/6).
Comparison table, Nas vs enterprise digital twins such as Replica (raised $41M, Dealroom): focus — public-service access vs traffic and land use; vulnerability — modelled per person vs aggregate; language — Arabic in and out vs English; data — synthetic by design vs mobile and location data.

---

SLIDE 8 — Next steps, the ask, and the team (dark navy; roadmap timeline on top, ask in the middle, team at the bottom)
Roadmap, three steps on a timeline:
1) Calibrate with Department of Statistics and MoDEE microdata.
2) Add office capacity and queues, and more services: first ID at 16, chronic medication pickup, the disability card.
3) More cities: each is new areas, sites and figures on the same engine.
The ask, large type: A pilot with the Prime Ministry's impact assessment unit, on one real policy, before it launches.
Team, three equal cards, no photos:
- Sultan Abbas — Software Engineer
- Yazan Zarka — Software Engineer
- Omar Hawasheen — Data Scientist
Closing line, large: Every policy leaves someone out. Nas shows you who, why, and how to fix it, before you launch.

---

SLIDE 9 — Sources (sand background, two columns, one source per line, small type, each with its link; keep every URL)
Title: Sources

Digital use and policy
1. MoDEE, Household ICT Access and Use Survey 2024, English summary (internet use 95.6%, e-government use 38.1%) — https://modee.gov.jo/ebv4.0/root_storage/en/eb_list_page/summary_of_the_survey_on_ict_access_and_use_in_households_and_by_individuals_2024.pdf
2. MoDEE, Household ICT Survey 2024, full analytical report in Arabic (65+: smartphone 80.2%, computer use 3.7%) — https://modee.gov.jo/ebv4.0/root_storage/ar/eb_list_page/%D8%A7%D9%84%D8%AA%D9%82%D8%B1%D9%8A%D8%B1_%D8%A7%D9%84%D8%AA%D8%AD%D9%84%D9%8A%D9%84%D9%8A_%D9%84%D9%85%D8%B3%D8%AD_%D8%A7%D8%B3%D8%AA%D8%AE%D8%AF%D8%A7%D9%85_%D9%88%D8%A7%D9%86%D8%AA%D8%B4%D8%A7%D8%B1_%D8%A7%D9%84%D8%A7%D8%AA%D8%B5%D8%A7%D9%84%D8%A7%D8%AA_%D9%88%D8%AA%D9%83%D9%86%D9%88%D9%84%D9%88%D8%AC%D9%8A%D8%A7_%D8%A7%D9%84%D9%85%D8%B9%D9%84%D9%88%D9%85%D8%A7%D8%AA_%D9%81%D9%8A_%D8%A7%D9%84%D9%85%D9%86%D8%A7%D8%B2%D9%84_2024.pdf
3. Petra News Agency, 85.5% of government services digitised, 100% targeted by end of 2026 — https://www.petra.gov.jo/en/news/jordan-digitizes-855-of-govt-services-targets-100-completion-by-year-end
4. MoDEE, Jordanian Digital Inclusion Policy 2025 — https://www.modee.gov.jo/ebv4.0/root_storage/en/eb_list_page/jordanian_digital_inclusion_policy_2025.pdf
5. MoDEE, Digital Transformation Strategy and Implementation Plan 2026–2028 — https://www.modee.gov.jo/ebv4.0/root_storage/en/eb_list_page/jordanian_digital_transformation_strategy_and_the_implementation_plan_2026-2028.pdf
6. Ad-Dustour, on the Good Regulation and Impact Assessment System No. 16 of 2025 — https://www.addustour.com/articles/1512441
7. Petra News Agency, minister urges data-driven legislative reform (impact assessment studies) — https://www.petra.gov.jo/en/news/minister-urges-data-driven-legislative-reform-to-boost-public-trust
8. Prime Ministry, Tawasul consultation on impact assessment instructions — https://tawasal.gov.jo/Consultations/redirect/1275
9. UN General Assembly, Report of the Special Rapporteur on extreme poverty and human rights (digital welfare state), A/74/493, 2019 — https://documents.un.org/doc/undoc/gen/n19/312/13/pdf/n1931213.pdf

Population and places
10. Department of Statistics figures as reported by The Jordan Times (47% women) — https://www.facebook.com/thejordantimes/posts/1482363837271805/
11. 2015 Census district populations of Greater Amman, as tabulated on Wikipedia "Amman" — https://en.wikipedia.org/wiki/Amman
12. World Bank Gender Data Portal, Jordan (labour-force participation 62.5% men, 16% women) — https://genderdata.worldbank.org/en/economies/jordan
13. UNFPA Arab States, Jordan country profile 2024 (49.3% of people 65+ with a functional difficulty) — https://arabstates.unfpa.org/sites/default/files/pub-pdf/country_profile_-_jordan_10-1-2024.pdf
14. Department of Statistics, Health Insurance in Jordan, 2015 Census analytical paper (Amman: 44.8% of Jordanians uninsured) — https://dosweb.dos.gov.jo/DataBank/Analytical_Reports/Health_Insurance_in_Jordan.pdf
15. Department of Statistics and DHS Program, Jordan Population and Family Health Survey 2023 — https://dosweb.dos.gov.jo/DataBank/Population/Health/JPFHS_Summary_Report__2023_en.pdf
16. Civil Status and Passports Department, directorates and offices list (7 Amman offices) — https://cspd.gov.jo/EN/ListDetails/Department_Directorates_and_Offices/17/1
17. Civil Status and Passports Department, services guide (JD 2 fee, office hours) — https://www.cspd.gov.jo/EN/ListDetails/Services__Guide/45/20
18. OpenStreetMap (homes on residential streets, map data © OpenStreetMap contributors) — https://www.openstreetmap.org/copyright
19. OSRM, Open Source Routing Machine (road distances and times) — https://project-osrm.org/

Fuel prices
20. Jordan News, Fuel Pricing Committee prices for October 2026 — https://www.jordannews.jo/Section-112/Economy/Jordan-Raises-Gasoline-and-Diesel-Prices-for-October-56784
21. Ammon News, National Aid Fund fuel support of 8–14 JD a month — https://www.ammonnews.net/article/697007

Market and precedent
22. Ammon News, 28 government entities in the public-sector reform programme — https://www.instagram.com/p/DDKXFnAIAaG/
23. World Bank, Jordan digital transformation programme P180291 (about $549M) — https://documents1.worldbank.org/curated/en/099021924052029939/pdf/P18029117c2ce2031a2bd192181a1ce9ad.pdf
24. UK Financial Conduct Authority, FG22/6 Branch and ATM closures or conversions — https://www.fca.org.uk/publications/finalised-guidance/fg22-6-branch-and-atm-closures-or-conversions
25. Dealroom, Replica company profile (funding) — https://dealroom.co/companies/replica/

Footer: Synthetic citizens, AI-voiced: generated from the published figures above; no real person's data is used. (Nas simulation) = output of our own engine.
```

Screenshots for slides 3 and 5: `PITCH_OUTLINE.md`, "Screenshots to take".
