<img src="nas-frontend/assets/logo.png" alt="Nas logo" width="220">

# Nas (ناس): Policy Simulator for Jordan's Public Services

*Every policy leaves someone out. Nas shows you who, why, and how to fix it before you launch.*

Nas is a policy simulator for Jordan's public services: it tests a policy on 1,000 synthetic citizens of Amman,
AI-voiced, and shows who it leaves out, why, and how to fix it before launch.

- **Live:** https://nas-rbo5.onrender.com (free plan: the first visit can take 30-60 s to wake). On stage, add
  `?sector=id_renewal`, `?sector=everyday_travel` or `?sector=medical_exemption` to skip the sector list.
- **Built for:** AI Quest @ Al Hussein Technical University · theme *Future in Jordan* · sector *Smart Society & Public Services*.
- **Team:** Sultan Abbas (Software Engineer) · Yazan Zarka (Software Engineer) · Omar Hawasheen (Data Scientist).

The deterministic engine decides and searches; the AI translates, explains and proposes; the engine verifies everything
the AI proposes. See [CLAUDE.md](CLAUDE.md) for the full spec.

## How it works

1. **Population.** 1,000 synthetic Jordanian adults spread across Amman's 22 districts, generated with a fixed seed so
   that published shares become the same shares of people (e.g. 95.6% internet use → 956 with a smartphone, MoDEE 2024).
   Homes sit on real OpenStreetMap streets; road distances to every office come from OSRM.
2. **Policy.** An official changes the policy with the controls, or types it in Arabic or English; the AI turns the
   sentence into a structured policy and shows an "understood as" list before anything is applied.
3. **Engine** (pure Python, deterministic, ~50 ms for 1,000 people). For every citizen it tries every channel (each office,
   mobile van, online), every open day and every way to get there (own car, a relative's car, bus with transfers, taxi),
   checks work hours, mobility, smartphone, digital skills and income, and picks the lowest burden (hours lost + cost +
   work missed). Result: served / hardship / left out, with reason codes.
4. **Fixes.** The engine scores ~30 candidate fixes (mobile vans, longer hours, rule changes, pairs) in about a second and
   shows the top 3. The AI explains them and proposes one more; the engine re-runs it and shows it only if it beats the
   best engine fix without hurting any group.
5. **Trust.** A ±20% robustness check on the most uncertain assumptions; a grounding check that rejects any AI text with a
   number the engine didn't compute; a template fallback for every AI task and a committed cache, so the demo runs offline.

**Stack:** Python 3.11+ · FastAPI · Pydantic v2 · static HTML/JS (no build step) · Leaflet + OpenStreetMap · OSRM ·
Gemini and Groq through one provider-agnostic client · fully bilingual Arabic/English UI with RTL.
**Tests:** `pytest -q` → 285 passed, 57 xfailed (the xfails are AI answers not pre-cached yet), all offline.

**Docs:** [CLAUDE.md](CLAUDE.md) (spec) · [HANDOFF.md](HANDOFF.md) (project state, demo numbers) ·
[DEMO_RUNBOOK.md](DEMO_RUNBOOK.md) (stage clicks and fallbacks) · [PITCH_OUTLINE.md](PITCH_OUTLINE.md) ·
[GAMMA_PROMPT.md](GAMMA_PROMPT.md) (8-slide pitch deck prompt with sources) · logos in [nas-frontend/assets/](nas-frontend/assets/)
(`logo-dark-transparent.png` for dark slides).

## Sectors

The app opens on a sector list (`?sector=id_renewal`, `?sector=everyday_travel` or `?sector=medical_exemption` skips it):

| Sector | What each citizen does | Outcomes | Demo preset |
|---|---|---|---|
| **تجديد الهوية / ID renewal** (`id_renewal`) | renews their national ID at an office, online, at a mobile van or by a home visit | served / hardship / left out | `consolidate_digital_first` |
| **أسعار المحروقات / Fuel prices** (`everyday_travel`) | makes their one regular trip (to work, university or a public hospital) under fuel and fare prices | fine / squeezed / priced out (the trip's monthly cost as a share of income: < 10% / 10-20% / ≥ 20%) | `fuel_plus_25_fares` |
| **الإعفاءات الطبية / Medical exemptions** (`medical_exemption`) | if uninsured (441 of 1,000), applies for a Royal Court medical exemption: at the Citizen Services Unit, an intake office, a mobile intake day, through Sanad, or by a relative | served / hardship / left out, **over the 441 uninsured only** (insured residents are "not applicable") | `exemption_online_only` |

The fuel sector, in numbers (engine output vs today's prices, 72.2 fine / 17.8 squeezed / 10.0 priced out): the October 2026
rise (+5%) makes 7 people worse off, all drivers; fuel +25% with fares held, 24, all drivers; **fuel +25% with bus and taxi
fares raised to match (as after 2012) makes 72 people worse off and priced out rises 10.0% → 15.2%**; 14 JD/month for
low-income people brings it only to 14.5%. The engine's best fix (14 JD/month for people without a car + a bus-fare freeze)
cuts priced out by 7.2 points, and still misses middle-income drivers: we show who it misses.

The medical-exemption sector, in numbers (engine output vs today's process, over the 441 uninsured): **today nobody is served**
(0.0 / 74.8 hardship / 25.2 left out: one office in Downtown and two visits of about two hours each already reach the hardship
line). **Applications only through Sanad** helps 364 people (77.6 / 14.1 / 8.4) but makes **30 worse off: all offline residents
with nobody to apply for them** (offline left out 29.3% → 37.4%). The engine's best fix (intake at the 7 Civil Status offices +
a Saturday mobile intake day in Downtown) cuts left out from 8.4% to 0.2%; the ranking holds 6/6 at ±20%. Letting a relative
apply changes nobody here: relatives work the same hours, and we say so.

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

**ID renewal:** offices (open, close or move one at any of 15 sites, hours per day, late Thursday, wheelchair access), online on/off/only,
appointments, mobile units (area, day, hours), the fee, the number of visits, and **protections for groups**: walk-in without
an appointment, fee exemptions or discounts, transport vouchers, capped home visits, and "apply online, collect in person".

**Fuel prices:** the fuel price change (%), bus and taxi fares (follow fuel by their assumed pass-through, freeze, or a set %),
**cash support** per group (JD a month, like the National Aid Fund's fuel support) and transport vouchers. The engine's fixes
use cash support, fare freezes and vouchers; they never change the fuel price, which is the decision being tested.

**Medical exemptions:** intake offices (the Royal Court's Citizen Services Unit, or open, close or move one at any site, e.g. an
intake point at a Civil Status office), online **via Sanad** on/off/only, mobile intake days (area, day, hours), the number of
visits, "apply on Sanad, collect the letter in person", **applying on someone's behalf** (a first-degree relative makes the
visits) and the protections for groups. The engine's fixes use mobile intake days, intake at the 7 Civil Status offices,
apply-and-collect and office toggles; they never change who is insured, the fee or the number of visits.

All of it from the policy panel or in Arabic/English free text. Anything else (e.g. extra staff, road closures, a separate
diesel price, electricity prices, people switching from car to bus, making people insured, the exemption amount, more doctors)
gets an honest "not supported yet" with the closest supported change.

## API (for the frontend)

Contract: [backend/app/models.py](backend/app/models.py). The frontend reads it only through [nas-frontend/api.js](nas-frontend/api.js).

| Method | Path | Body → Response |
|---|---|---|
| GET | `/services` | → `ServiceInfo[]` `{id, name_ar, name_en, description_ar, description_en, levers, baseline_scenario, demo_scenario}` (the 3 sectors) |
| GET | `/population` | → `Citizen[]` (1,000) |
| GET | `/scenarios` | → `Scenario[]`, each with `service`. ID renewal: baseline = the 7 real CSPD offices, consolidate, digital_first, online_only, consolidate_digital_first = demo path (`demo: true`). Fuel: travel_today (baseline), fuel_plus_5, fuel_plus_25, fuel_plus_25_fares (`demo: true`), fuel_plus_25_support. Medical exemptions: exemption_today (baseline), exemption_online_only (`demo: true`), exemption_hybrid, exemption_regional, exemption_no_proxy |
| GET | `/sites`, `/areas` | → `Site[]` (16: the 15 ID-renewal sites + `royal_court_csu`, shown only in the medical-exemption sector), `Area[]` |
| GET | `/assumptions` | → rows `{name, value, unit, tag, rationale, source, label_ar, label_en, rationale_ar, source_ar, perturbed_in_robustness_check, service}` (all 35 tagged ASSUMPTION; `service` = `id_renewal`, `everyday_travel`, `medical_exemption` or `shared`; `source` = short context note or null) |
| GET | `/heroes?service=` | → `Hero[]` `{id, note_ar, note_en, profile, service}`: hero citizens for that sector's demo path (default `id_renewal`) |
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

**Fuel levers** (Policy fields with `service: "everyday_travel"`; no-ops for ID renewal): `fuel_price_change_pct`,
`bus_fare_change_pct` / `taxi_fare_change_pct` (`null` = follow fuel, `0` = freeze, N = that change), `cash_support`
`[{groups, amount_jd_month}]`, `transport_vouchers`. Travel outcomes add `purpose`, `days_per_week`, `monthly_cost_before_jd`,
`extra_jd_month`, `income_share_pct`, `cash_support_jd_month` (`cost_jd` is the monthly cost after the policy); KPIs add
`avg_monthly_cost_jd`, `avg_extra_jd_month`, `avg_income_share_pct`, `n_cash_support`, `by_purpose`, `by_mode`.

**Medical-exemption levers** (Policy fields with `service: "medical_exemption"`): the ID-renewal fields (offices, `online_enabled`
/ `online_only` = Sanad, `mobile_units` = mobile intake days, `visits_required`, `hybrid_pickup`, the protections) plus
`proxy_allowed` (`null` = the service default: on for medical exemption, off for ID renewal). Only citizens with the
`uninsured` tag (`Citizen.has_health_insurance: false`) apply; the others get `channel: "not_applicable"` and are left out of
every percentage (`kpis.n_eligible` = 441, `kpis.n_not_applicable` = 559). Channels: `royal_court_unit`, `intake_<cspd office>`,
`mobile:<area>:<day>`, `online` (Sanad), `home_visit`; mode `helper_visit` = a relative made the visits.

## Data

| File | What | Source |
|---|---|---|
| `backend/app/data/population.json` | 1,000 synthetic citizens (Jordanian nationals 16+) across 22 GAM districts | `seed_census.py`, seed 42, quotas from *Amman in a Box*; targets vs results in `data/census/VALIDATION.md`. Health insurance (`has_health_insurance`, tag `uninsured`) added by `seed_insurance.py`, seed 42 |
| `backend/app/data/home_points.json` | residential street points (optional, places homes on real streets) | OpenStreetMap via Overpass, `fetch_map_data.py homes` |
| `backend/app/data/travel_matrix.json` | road km + car time, every citizen to every site and area centre | OSRM (OpenStreetMap), fetched once by `fetch_map_data.py` |
| `backend/app/data/anchors.json` | public figures with their status (ANCHORED / TEAM_CONFIRMED / CITED_UNVERIFIED) | desk research, each figure with its verification status (documentation; not read at runtime) |
| `backend/app/data/sites.json` | the 7 real CSPD offices + 8 generic snap sites + the Royal Court's Citizen Services Unit (medical exemptions only) | cspd.gov.jo office list, located with OSM Nominatim; the Royal Court unit at approximate coordinates (Nominatim found nothing, ±1 km) |
| `backend/app/data/services.json` | the 3 sectors: ids, names, policy-panel levers, baseline and demo preset | ours (served by `GET /services`) |
| `backend/app/data/hubs.json` | 25 everyday-trip destinations: 14 work areas, 7 universities, 4 public hospitals | locations from OpenStreetMap Nominatim (2026-10-09); weights are ASSUMPTION |
| `backend/app/data/daily_trips.json` | one regular trip per synthetic citizen (948 of 1,000: 320 work, 164 university, 464 hospital weekly) | `seed_daily.py`, seed 42 (rules are ASSUMPTION) |
| `backend/app/data/hub_matrix.json` | road km + car time, every citizen to every hub | OSRM (OpenStreetMap), fetched 2026-10-09 |

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
- **Trip destinations** (work areas, universities, public hospitals) placed with OpenStreetMap Nominatim, and **road times to them** from OSRM (`hubs.json`, `hub_matrix.json`).

**Fuel sector (press reports, CITED)**
- **October 2026 fuel prices** (Fuel Pricing Committee, as reported by Jordan News on 2026-10-01): 90-octane 1.050 JD/L (+0.05), 95-octane 1.360 (+0.05), diesel 0.900 (+0.05), kerosene 0.550 (unchanged). The `fuel_plus_5` preset is this rise.
- **National Aid Fund fuel support**: 8-14 JD a month per beneficiary family (Ammon News). The `fuel_plus_25_support` preset uses 14 JD.
- The 2012 subsidy removal is the model for `fuel_plus_25_fares` (fuel and fares raised together): context only, no 2012 figure is used.

**Health insurance and the Royal Court medical exemption (the third sector)**
- **DoS, "Health Insurance in Jordan", Census 2015 analytical paper (ANCHORED, official PDF):** 68.7% of Jordanians and ~56% of the total population insured; all children under 6 insured by the Ministry of Health; **Amman: 55.2% of Jordanians insured (44.8% not), 41.2% of the total population (58.8% not)**, Amman and Zarqa the lowest governorates (41%); non-Jordanians 25.3% insured nationally, 16.4-16.8% in Amman; the least-covered age group is 15-34.
- **JPFHS 2023 (DoS / DHS, ANCHORED):** 69% of ever-married women and 59% of men aged 15-49 have any health insurance.
- **Not used:** a "76.8% of Jordanians insured" figure (a 2024 article whose breakdown sums to 84.9%, with no year, citing DoS 2015 anyway) and a "38% of non-Jordanians insured" figure (a misreading: 38% of the *insured* non-Jordanians are under special arrangements). Both are marked DO NOT USE in `anchors.json`.
- **Now used by the engine:** income-band uninsured rates (low 65% / middle 45% / high 20%, an ASSUMPTION calibrated to the anchored 44.8%, which covers all ages including the fully insured under-6s, so adults are higher) give **441 of our 1,000 synthetic adults uninsured (44.1%)**.
- **The exemption process** (press reports, CITED): applications in person at the Royal Court's Citizen Services Unit with a medical report, a Ministry of Health doctor's review, and a return visit for the letter. Office hours and queue time are not published, so 08:00-15:00 Sun-Thu and a 2-hour visit are labelled assumptions.

**Quoted, not verified (CITED)**
- **2015 census district shares** (22 GAM districts): they decide where the 1,000 synthetic citizens live.
- Sex ratio, disability rates, labour force and unemployment, informality, the 8.3% poverty rate, the 14% public-transport share, digital skills, household size (targets vs results in `data/census/VALIDATION.md`).

**Assumed (labelled, frozen before any scenario ran)**
- **All 26 engine constants** in `sim/assumptions.py` (service time, bus speed and waits, taxi fares, hardship threshold, ...). Three of them (`SERVICE_MINUTES`, `BUS_WAIT_PLUS_TRANSFER_MIN`, `HARDSHIP_THRESHOLD`) are moved by ±20% in the robustness check: the worst-group ranking holds 6/6.
- **The 7 fuel-sector constants**, committed before any travel scenario ran: weeks per month (4.33), a representative income per band (130 / 350 / 950 JD a month: the medians of our synthetic incomes, not a statistic), the squeezed / priced-out thresholds (10% / 20% of income), fuel's share of a car's running cost (0.6), and how much of a fuel change bus fares and taxi tariffs pass on (0.3 / 0.5). Three are moved by ±20%: the top group (workers) holds in 6/6 runs, the second place in 5/6 (we show the run where it changes).
- **The 2 medical-exemption constants**, committed before any exemption scenario ran: one visit at the Citizen Services Unit takes 120 minutes (queue + the doctor's review), and the uninsured rate per income band (65 / 45 / 20%). Three constants are moved by ±20% (visit minutes, bus wait per transfer, hardship threshold): on the Sanad-only demo the ranking holds 6/6.
- **Who travels where**: each citizen's one regular trip and how they make it (own car, a helper's car or taxi for wheelchair users, else the bus); nobody switches mode when prices change.
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
| `uninsured` | no health insurance (`seed_insurance.py`; only the medical-exemption sector uses it) | 441 |

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
python -m scripts.warm_cache --service everyday_travel   # one sector only (find_ai_fix takes --service too)
python -m scripts.warm_cache --service medical_exemption # the medical-exemption sector (after find_ai_fix --service medical_exemption)
python -m app.data.seed_insurance        # re-add health insurance + the "uninsured" tag (seed 42) after every seed_census --install
python -m app.data.seed_daily            # regenerate daily_trips.json (seed 42) after a population or hub change
pytest -q                                # offline tests, incl. the demo guard (test_demo.py)
```

Project state and decisions for the next person (or AI session): [HANDOFF.md](HANDOFF.md).
