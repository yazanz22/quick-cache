# Nas (ناس): Policy Simulator for Jordan's Public Services

> Hackathon project for **AI Quest @ Al Hussein Technical University**.
> Theme: *Future in Jordan*. Sector: *Smart Society & Public Services*.
> Team of 3 · ~10 working hours left across 2 days · 7-min demo + 3-min Q&A on Day 2 (from 1:30 PM).

## 1. What we are building

Nas is a **"wind tunnel" for public services**. It lets an official test a policy **before** launch.

A digital model of Amman is populated by ~1,000 **synthetic citizens, AI-voiced**. Each citizen has an age, mobility, car ownership, smartphone access, digital literacy, work hours and income. An official tests a policy change, for example:

- "Move the Civil Status office from Downtown to Abdali"
- "Close counters at 1 PM and require online appointments"
- "Make ID renewal online-only"
- "Add a mobile service van in Marka on Saturdays"

The engine runs every citizen through the service under the new policy. The map lights up:

- 🟢 served
- 🟡 served with hardship
- 🔴 left out

Click any citizen and they explain their outcome **in clear Modern Standard Arabic (فصحى)**, e.g. *"أحتاج إلى حافلتين ونصف يوم، وابني لا يستطيع أخذ إجازة ليوصلني"* ("I'd need two buses and half a day, and my son can't take a day off to drive me").

Nas then **finds fixes**. The engine searches a grid of candidate fixes and verifies each one; the AI explains them and proposes one more that nobody listed, which the engine also verifies.

**The one-line pitch:** *Every policy leaves someone out. Nas shows you who, why, and how to fix it before you launch.*

**Wording rule:** say "synthetic citizens, AI-voiced", never "1,000 AI citizens". The citizens are rule-based; the AI gives them a voice. Overclaiming loses the AI judge.

### How Nas answers the judging criteria

| Criterion | How Nas answers it |
|---|---|
| Impact on Jordan | Directly answers "who is left out?" for elderly, disabled, low-income, no-car and no-smartphone residents. |
| Innovation | Policy testing on a synthetic population, with an engine that searches and verifies fixes and an AI that turns Arabic sentences into policies and numbers into human voices. |
| Feasibility & Scalability | Population anchored to public Department of Statistics figures; add services and cities by data, not code. Sold as SaaS to municipalities and ministries. |
| Technical Implementation | Deterministic, tested engine; robustness check; structured AI outputs with fallbacks; offline demo mode. Synthetic data clearly labelled. |
| UX & Design | Map-first UI for officials, fully bilingual Arabic/English with an RTL layout and a language toggle. |
| Pitch | A live "change the policy → watch who falls out → fix it → watch them come back" moment. |

### The answers to have ready
- **"Does your app reach the people left out?"** *"We reach them before the policy does. Excluded people are counted before launch instead of discovered after."*
- **"What does the AI do that a spreadsheet couldn't?"** *"The engine makes it honest; the AI makes it usable. It turns an official's Arabic sentence into a testable policy, turns 1,000 rows into the voice of the person left out, and proposes fixes nobody listed. The engine verifies every one."*
- **"Didn't you just tune the numbers to get this result?"** *"No. Assumptions were frozen before we ran any scenario, the key ones are anchored to public statistics, and the result holds when we move the uncertain ones by ±20%. Click the badge."*

## 2. Core design principle (do not break this)

**The deterministic engine decides and searches. The AI translates, explains and proposes. The engine verifies everything the AI proposes.**

- The **engine** (pure Python, deterministic, no AI) computes for each citizen:
  - which channel they can use
  - travel time, cost and hours lost
  - outcome and reason codes

  It also **searches the fix grid** (§6.4) and runs the **robustness check** (§6.5).
- The **AI** has exactly four jobs:
  1. **Parse** a free-text policy (Arabic or English) into a Policy, or say honestly that it can't be modeled.
  2. **Voice** a citizen's outcome in Modern Standard Arabic (فصحى), using *only* the numbers the engine computed.
  3. **Report**: write the official-facing impact summary (Arabic + English).
  4. **Explain and propose fixes**: explain the engine's top 3 fixes, and propose **one** extra policy not on the grid. That extra policy is shown only if the engine confirms it beats the best grid fix.

**Every AI task has a non-AI fallback** (§8.6), so a rate limit, a timeout or a bad output never leaves a blank or broken screen. The AI never decides an outcome and never states a number the engine didn't compute.

## 3. Tech stack

- **Frontend:** a static HTML/JS app in `nas-frontend/` (no build step, no framework), served by the backend itself at `/` (one server, one URL).
  - `api.js` is the only file that knows routes and JSON shapes; `app.js` computes nothing (every number comes from the backend).
  - Map: Leaflet + OpenStreetMap tiles. **Offline fallback:** `?offline=1` (or `OFFLINE_MAP` in `config.js`) draws no tiles, only labelled area zones. Don't bulk-download OSM tiles; their usage policy forbids it.
  - Fonts: `IBM Plex Sans Arabic` (Arabic) and `IBM Plex Sans` (Latin).
  - i18n: a hand-written dictionary in `i18n.js` (Arabic + English). **No i18n library.**
- **Backend:** Python 3.11+, FastAPI, Pydantic v2, Uvicorn. Plain Python is enough; NumPy optional.
- **AI:** provider-agnostic, chosen by `LLM_PROVIDER` in `.env`
  - **`gemini` (default, free tier):** the `google-genai` SDK with a free Google AI Studio key. Use Flash-class models; Pro models are not reliably on the free tier.
  - **`groq` (fallback, free tier):** Groq's OpenAI-compatible endpoint via the `openai` SDK with `base_url="https://api.groq.com/openai/v1"`. Fast, but weaker at natural Arabic, so prefer it for JSON tasks, not voices.
  - **`anthropic` (optional, paid):** the `anthropic` SDK with a Claude Console key.
  - Two model slots: `MODEL_FAST` (voices) and `MODEL_SMART` (parse, report, fixes). Model IDs live in `.env`, never hard-coded.
  - `llm/client.py` exposes one interface, `complete(task, system, user, json_schema=None, smart=False) -> str`, with one small adapter per provider. Nothing outside `llm/` imports a provider SDK.
  - On a 429 / rate-limit / timeout: back off once, then try `LLM_FALLBACK_PROVIDER` if set, then use the task's fallback (§8.6). Per-call timeout: 15 s.
- **Storage:** JSON files on disk. **No database, no auth, no Docker.**
- **Text-to-speech:** none. Citizen voices are text bubbles.

### API key note
- The app runs on **free-tier API keys** (Gemini by default, Groq as fallback). Each teammate can make their own key for local development.
- Free tiers are rate-limited per minute and per day. The cache (§8.4) keeps us far below the limits. Don't burn the daily quota on loops during development. Gemini's daily quota resets at midnight Pacific time, about 10:00 AM Amman time.
- Free-tier inputs may be used by the provider to improve its models. That's acceptable here **only because all citizen data is synthetic**; never send real personal data.
- Do **not** wire in Claude subscription (Pro/Max) OAuth tokens. Subscription credentials are only for using Claude Code itself.

## 4. Repository layout

```
nas/
├── CLAUDE.md
├── README.md
├── .env.example                # see §15
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py             # FastAPI app: the two routers, serves nas-frontend/ at /, warms the demo path at start-up
│   │   ├── config.py           # loads the repo-root .env
│   │   ├── models.py           # ALL Pydantic schemas (source of truth for the API contract)
│   │   ├── routes/
│   │   │   ├── sim_routes.py   # /population, /scenarios, /sites, /areas, /heroes, /assumptions, /simulate, /compare, /fixgrid, /sensitivity
│   │   │   └── llm_routes.py   # /policy/parse, /citizen/voice, /report, /fixes, /llm/status
│   │   ├── sim/
│   │   │   ├── assumptions.py  # every tunable constant, each with a comment, a rationale and an "ASSUMPTION" or "ANCHORED" tag
│   │   │   ├── assumption_labels.py # Arabic/English labels for the assumptions table (text only, no values)
│   │   │   ├── travel.py       # OSRM road distances/times, mode times and costs, bus transfers
│   │   │   ├── engine.py       # simulate(policy, population, assumptions=None) -> SimResult
│   │   │   ├── compare.py      # baseline vs scenario diff + equity breakdown
│   │   │   ├── fixgrid.py      # build + score the candidate-fix grid (§6.4)
│   │   │   ├── sensitivity.py  # ±20% robustness check (§6.5)
│   │   │   ├── validate.py     # policy checks beyond the schema (known sites/areas, hours)
│   │   │   ├── warmup.py       # pre-computes the demo path at start-up (fast first request after a cold start)
│   │   │   └── world.py        # loads population, areas, sites, scenarios, travel matrix once
│   │   ├── llm/
│   │   │   ├── client.py       # provider-agnostic complete(): model chains, cooldowns, time budget
│   │   │   ├── prompts.py      # all prompts in one file
│   │   │   ├── cache.py        # disk cache keyed by sha256(task + canonical inputs), see §8.4
│   │   │   ├── fallbacks.py    # non-AI template text for every task (§8.6)
│   │   │   ├── checks.py       # grounding check: numbers in AI text must match engine output (§8.3)
│   │   │   └── tasks.py        # parse_policy, voice_citizen, write_report, explain_and_propose_fixes
│   │   └── data/
│   │       ├── seed_census.py  # generates the census-anchored population (seed=42); --install writes population.json
│   │       ├── seed.py         # shared helpers for seed_census: names, shifts, helper relations, tag rules
│   │       ├── census/         # seed_census outputs: VALIDATION.md, targets.json, reference CSV/JSON sets
│   │       ├── fetch_map_data.py # one-time OSM/OSRM fetches: home_points.json, travel_matrix.json
│   │       ├── fetch_roads.py  # one-time: OSM road network -> roads.json (catalogue) + road_deltas.json (detours)
│   │       ├── anchors.json    # public figures, each with status, source name, URL, year
│   │       ├── areas.json      # the 8 engine areas: name_ar, name_en, lat, lng, side
│   │       ├── sites.json      # 15 office sites: the 7 real CSPD offices + 8 generic snap sites
│   │       ├── population.json # 1,000 synthetic citizens, committed so everyone has the same people
│   │       ├── travel_matrix.json, home_points.json  # fetched once (OSRM / OpenStreetMap)
│   │       ├── roads.json, road_deltas.json  # closable roads + per-road detours (fetch_roads.py)
│   │       └── scenarios/      # baseline + presets (demo one flagged "demo": true), heroes.json, demo_requests.json
│   ├── scripts/                # pick_heroes.py, find_ai_fix.py, warm_cache.py, road_impact.py
│   ├── cache/                  # AI cache files (committed for offline mode)
│   └── tests/                  # test_engine.py, test_fixgrid.py, test_llm.py (offline, no AI calls)
└── nas-frontend/               # static UI, no build step (see its README)
    ├── index.html              # layout + all CSS (light/dark, RTL, responsive)
    ├── config.js               # backend URL, timeouts, offline map switch, fallback areas/heroes
    ├── api.js                  # the ONLY file that knows routes and JSON shapes (normalisers)
    ├── i18n.js                 # every UI string, ar + en
    └── app.js                  # UI logic: rendering, map, events, request ordering
```

## 5. Data model (contract, freeze it in the first hour)

### Citizen
```python
class Citizen(BaseModel):
    id: str                       # "c_0001"
    name_ar: str                  # from a list of common Jordanian first names
    name_en: str                  # transliteration of the same name
    age: int
    gender: Literal["m", "f"]
    area: str                     # key into areas.json
    lat: float; lng: float        # jittered around the area centroid
    mobility: Literal["none", "limited", "wheelchair"]
    has_car: bool
    has_smartphone: bool
    digital_literacy: Literal["low", "medium", "high"]
    works: bool
    work_start: str | None        # "08:00"
    work_end: str | None          # "16:00"
    income_band: Literal["low", "middle", "high"]
    has_helper: bool              # family member who can drive or help online
    helper_relation_ar: str | None  # e.g. "ابني", "بنتي", "جاري"; voices may only mention this person
    helper_relation_en: str | None  # "my son", "my daughter", "my neighbour"
    tags: list[str]               # derived by seed.derive_tags, see rules below
```

Tag rules (derived, never set by hand):
- `elderly`: age ≥ 65
- `disabled`: mobility != "none"
- `low_income`: income_band == "low"
- `no_car`: not has_car
- `offline`: not has_smartphone or digital_literacy == "low"
- `worker`: works
- `student`: 18 ≤ age ≤ 24 and not works

All workers work **Sun–Thu** between `work_start` and `work_end`. Non-workers are free every day.

**Helpers work too.** A helper can drive the citizen only on Fri/Sat, or on Sun–Thu at or after `HELPER_FREE_FROM` (an assumption, e.g. 16:00). Helping online has no time limit. This is what makes "my son can't take a day off to drive me" true, and what makes late-hours and Saturday fixes matter.

### Policy
```python
Day = Literal["sat", "sun", "mon", "tue", "wed", "thu", "fri"]

class Office(BaseModel):
    id: str; name_ar: str; name_en: str
    site_id: str                  # key into sites.json (gives lat/lng); pins snap to sites
    schedule: dict[Day, tuple[str, str]]   # per-day hours, e.g. {"sun": ("08:00","15:00"), "thu": ("08:00","19:00")}
    wheelchair_accessible: bool = True

class MobileUnit(BaseModel):
    area: str                     # parks at the area centroid
    day: Day; open: str; close: str
    # Mobile units are ALWAYS walk-in (no appointment) and wheelchair accessible.

class Policy(BaseModel):
    service: str = "id_renewal"   # only one service for the MVP
    offices: list[Office]
    online_enabled: bool = True
    online_only: bool = False     # if True, offices and mobile units are ignored entirely
    mobile_units: list[MobileUnit] = []
    appointment_required: bool = False  # applies to OFFICES only, see §6.1 rule 3
    fee_jd: float
    visits_required: int = 1
    closed_roads: list[str] = []  # ids from roads.json (19 major roads); trips that used them take the detour (§6.1 rule 4)
```

**What Nas can model** is exactly what this schema expresses: where offices are (8 sites), their hours per day, wheelchair access, online on/off/only, appointments at offices, mobile units (area, day, hours), the fee, the number of visits, and which of the 19 catalogue roads are closed (all day, every day). Anything else is "not supported yet" (§8.5).

### Simulation output
```python
ReasonCode = Literal[
    "TOO_FAR", "NO_TRANSPORT", "HOURS_CONFLICT_WORK", "NO_SMARTPHONE",
    "LOW_DIGITAL_LITERACY", "NOT_WHEELCHAIR_ACCESSIBLE", "TOO_EXPENSIVE", "OFFICE_CLOSED_ON_AVAILABLE_DAYS",
]

class CitizenOutcome(BaseModel):
    citizen_id: str
    status: Literal["served", "hardship", "left_out"]
    channel: str | None           # office id, "online", or "mobile:<area>:<day>"
    channel_name_ar: str | None   # e.g. "مكتب العبدلي", "الوحدة المتنقلة في ماركا يوم السبت", "أونلاين"
    channel_name_en: str | None
    mode: str | None              # car, helper_car, bus, taxi, online
    bus_transfers: int = 0        # 0, 1 or 2; from travel.py (cross-city trips need a transfer)
    visit_day: Day | None
    travel_minutes: float
    cost_jd: float
    hours_lost: float             # total time away incl. waiting, × visits
    work_hours_missed: float
    reasons: list[ReasonCode]     # why NOT served (or why hardship)

class SimResult(BaseModel):
    outcomes: list[CitizenOutcome]
    kpis: dict                    # pct_served, pct_hardship, pct_left_out, avg_hours_lost, avg_cost_jd
    by_group: dict                # tag -> {served, hardship, left_out} percentages

class CompareResult(BaseModel):
    baseline: SimResult
    scenario: SimResult
    flipped_worse: list[str]      # citizen ids whose status got worse
    flipped_better: list[str]     # citizen ids whose status improved
    kpi_delta: dict               # scenario minus baseline, same keys as kpis
    worst_groups: list[str]       # tags ranked by Δ(left_out% + hardship%), worst first
```

### Fixes, parsing and robustness
```python
class FixCandidate(BaseModel):
    id: str                       # e.g. "van:marka:sat", "late_thu", "pair:van:marka:sat+late_thu"
    title_ar: str; title_en: str  # template titles built by the engine
    policy: Policy                # full policy = scenario policy + this change
    source: Literal["engine_grid", "ai_proposed"]
    left_out_drop: float          # percentage points vs the scenario being fixed
    hardship_drop: float
    worsens_any_group: bool
    explanation_ar: str | None = None   # filled by AI or fallback
    explanation_en: str | None = None

class ParseResult(BaseModel):
    status: Literal["ok", "unsupported"]
    policy: Policy | None         # full policy when status == "ok"
    changes_ar: list[str]         # human-readable "understood as" list, e.g. "إغلاق الساعة 13:00"
    changes_en: list[str]
    message_ar: str | None        # for "unsupported": what can't be modeled + what can
    message_en: str | None

class SensitivityResult(BaseModel):
    runs: int                     # 6
    ranking_held: int             # how many runs kept the same top-2 worst groups in the same order
    fix_still_helps: int          # how many runs where the chosen fix still reduces left_out
    stable_top_group: str | None  # the group that is top in all runs, if any
    passed: bool                  # ranking_held == runs and fix_still_helps == runs
```

## 6. Engine rules (simple, explainable, frozen)

### 6.1 Per-citizen evaluation
For each citizen, evaluate every available **channel**: each office, each mobile unit, and online. If `online_only`, online is the only channel.

1. **Visit time:** an in-person visit takes `travel there + SERVICE_MINUTES + travel back`. The cost is `fee_jd + travel cost`.
2. **Online:** feasible if `online_enabled`, `has_smartphone`, and `digital_literacy != "low"`. If they lack a smartphone or literacy but `has_helper`, it's feasible **with hardship**. Otherwise not feasible (reasons `NO_SMARTPHONE` / `LOW_DIGITAL_LITERACY`).
3. **Appointments (offices only):** if `appointment_required`, an office visit first needs an online booking, using rule 2's feasibility (helper allowed, counts as hardship). If they can't book, they make one wasted trip first: `visits_required + 1`, and the reason is added. **Mobile units never need appointments.**
4. **Travel mode** for an office or mobile unit, evaluated per open day:
   - `car` if `has_car`.
   - `helper_car` if `has_helper` and the helper is free at that time (§5 helper rule). Sets the hardship flag.
   - `bus` if `mobility != "wheelchair"`. `travel.py` returns minutes and `bus_transfers` (0 within an area, 1 across areas, 2 between east and west Amman; an assumption).
   - `taxi` if its cost is within the income band's `TAXI_MAX_JD`. Above that, taxi is **infeasible** with reason `TOO_EXPENSIVE`.
   - Wheelchair users need `wheelchair_accessible` (mobile units always are) and cannot use the bus.
   - A mode whose one-way time exceeds `MAX_TRAVEL_MINUTES` is infeasible with reason `TOO_FAR`. If no mode exists at all (no car, no free helper, no bus, taxi unaffordable): `NO_TRANSPORT`.
   - **Closed roads:** if the policy closes roads, a trip's road time and distance get that road's detour from `road_deltas.json` (routed once on the OSM network with the road removed, `fetch_roads.py`), so car, taxi and bus all slow down and taxis cost more. Several closures: the largest single-road detour per trip (a lower bound). Homes that open onto the road keep local access. The outcome records `detour_minutes` and `detour_road`.
   - Among feasible modes, pick the lowest burden (rule 6).
5. **Time slot:** the channel must be open on some day for the full visit duration.
   - Non-workers: any open day works; pick the lowest-burden day.
   - Workers: a slot is **outside work** if it's on Fri/Sat, or on a workday starting at or after `work_end`. If an outside-work slot exists, use it. Otherwise the visit happens during work: `work_hours_missed = full visit duration × visits`, the hardship flag is set, and the reason is `HOURS_CONFLICT_WORK`.
   - Work-missed caps per income band (`MAX_WORK_HOURS_MISSED[band]`): above the cap, that channel is infeasible with `HOURS_CONFLICT_WORK`.
   - If the channel is never open on any day: `OFFICE_CLOSED_ON_AVAILABLE_DAYS`.
6. **Burden:** `burden = hours_lost + COST_WEIGHT × cost_jd + WORK_WEIGHT × work_hours_missed`. Pick the feasible (channel, day, mode) with the lowest burden. Ties: fewer hardship flags, then online over in-person, then channel id alphabetically.
7. **Classification** of the chosen option:
   - **Served:** `burden < HARDSHIP_THRESHOLD` **and** no hardship flag.
   - **Hardship:** `burden ≥ HARDSHIP_THRESHOLD` **or** any hardship flag (helper used for travel or online, work missed, a wasted appointment trip).
   - **Left out:** no feasible option.
8. **Reasons:**
   - Left out: the **deduplicated union** of failure reasons across all channels.
   - Hardship: only the reasons attached to the chosen option (e.g. `HOURS_CONFLICT_WORK`, `NO_SMARTPHONE` when a helper booked).
   - Served: empty.

The engine must be **deterministic** and run 1,000 citizens in well under 1 second (target: under 0.1 s), because the fix grid and the robustness check run it ~40 times.

### 6.2 Assumptions: set once, then frozen
Every constant lives in `sim/assumptions.py` with a comment, a one-line rationale, and a tag:
- `# ANCHORED: <source>` if it comes from a public figure in `anchors.json`.
- `# ASSUMPTION` otherwise (round, plausible values).

Constants include `SERVICE_MINUTES`, `BUS_SPEED_KMH`, `BUS_WAIT_PLUS_TRANSFER_MIN` (per transfer), `CAR_SPEED_KMH`, taxi base fare and per-km rate, `MAX_TRAVEL_MINUTES`, `TAXI_MAX_JD[band]`, `MAX_WORK_HOURS_MISSED[band]`, `HELPER_FREE_FROM`, `HARDSHIP_THRESHOLD`, `COST_WEIGHT`, `WORK_WEIGHT`.

**Freeze rule (do not break this):** *Set assumptions once to round, plausible values with a stated rationale. Freeze them before running any scenario. If a scenario's story doesn't appear, change the scenario, not the assumptions.* Never present any of these values as official statistics.

### 6.3 Population anchors
`anchors.json` records the public figures (the census generator, `seed_census.py`, documents its own targets in `data/census/VALIDATION.md`). Spend at most **30 minutes** sourcing real public figures; anything not found stays an `# ASSUMPTION`. Never invent a value and label it as sourced. Targets:
1. Share of residents aged 65+ in Amman governorate (Department of Statistics population estimates or Census).
2. Household car ownership rate (DoS household surveys or the Jordan Statistical Yearbook).
3. Smartphone or internet use, ideally by age group (DoS / Ministry of Digital Economy ICT household survey).
4. Optional: disability prevalence (Census).

Per-area variation (some areas older, poorer, fewer cars) stays a labelled synthetic assumption.

### 6.4 Fix grid (`sim/fixgrid.py`)
Given a scenario policy, build and score candidate fixes, each a full Policy = scenario + one change:
- **16 mobile vans:** 8 areas × {Sat, Thu}, 09:00–14:00, walk-in.
- **3 toggles:** a late Thursday at every office (until 19:00), remove `appointment_required`, make every office wheelchair accessible. Skip any toggle that changes nothing.
- **Pairs:** take the top 5 singles and combine them two at a time, skipping two vans in the same area. About 9–10 pairs.

Score each against the scenario: `left_out_drop`, `hardship_drop`, `worsens_any_group`. Drop any candidate that worsens a group. **Rank deterministically** by `left_out_drop`, ties broken by `hardship_drop`, then by fewer changes. Return the top 3. The whole grid must run in about 1 s, with no AI.

### 6.5 Robustness check (`sim/sensitivity.py`)
Perturb `SERVICE_MINUTES`, `BUS_WAIT_PLUS_TRANSFER_MIN` and `HARDSHIP_THRESHOLD`, **one at a time, ±20%** = 6 runs, re-running baseline, scenario and the chosen fix.

**Pass rule:** in all 6 runs, the top-2 `worst_groups` are the same and in the same order, **and** the chosen fix still reduces left_out. Precompute it for the demo scenarios and cache the JSON. It takes under 1 s, so it can also re-run live if a judge asks.

If the ranking flips: **don't retune and don't hide it.** Show it ("the order of elderly vs offline depends on bus wait") and only claim the `stable_top_group`.

### Areas (approximate centroids, verify on the map first)
Downtown/Al-Balad (31.951, 35.934) · Abdali (31.962, 35.910) · Jabal Al-Hussein (31.968, 35.920) · Marka (31.975, 35.985) · Wehdat (31.935, 35.940) · Tabarbour (32.000, 35.940) · Sweileh (32.020, 35.840) · Khalda (31.995, 35.835).

### Candidate office sites (`sites.json`)
8 fixed sites, one per area. When an office pin is dragged on the map, it **snaps to the nearest site**. This keeps scenarios realistic and keeps AI cache keys stable.

## 7. API

| Method | Path | Purpose |
|---|---|---|
| GET | `/population` | All citizens (for drawing dots) |
| GET | `/scenarios` | Preset scenarios (baseline + demo presets) |
| GET | `/sites` | Candidate office sites |
| GET | `/roads` | Closable major roads with map geometry |
| GET | `/assumptions` | All constants with value, rationale, tag and source (for `AssumptionsTable`) |
| POST | `/simulate` | `{policy}` → `SimResult` |
| POST | `/compare` | `{baseline, scenario}` → `CompareResult` |
| POST | `/fixgrid` | `{baseline, scenario}` → top 3 `FixCandidate` (engine only, no AI) |
| POST | `/sensitivity` | `{baseline, scenario, fix}` → `SensitivityResult` (engine only, cached) |
| POST | `/policy/parse` | `{text, current_policy, lang}` → `ParseResult` (AI) |
| POST | `/citizen/voice` | `{citizen_id, outcome}` → `{text_ar, source: "ai" or "fallback"}` (AI, cached) |
| POST | `/report` | `{compare_result, sensitivity}` → `{summary_ar, summary_en, source}` (AI) |
| POST | `/fixes` | `{baseline, scenario}` → `{fixes: list[FixCandidate]}`: runs `/fixgrid`, then one AI call to explain the top 3 and propose one off-grid policy; the off-grid policy is engine-verified and included only if it beats the best grid fix |

The frontend calls `/fixgrid` first and renders the engine fixes **immediately**, then calls `/fixes` to fill explanations and possibly add the AI fix. The fix moment never waits on the AI.

## 8. AI layer rules

### 8.1 Structured output
Every AI task except voices returns JSON, validated with Pydantic. On a validation failure, retry once with the error message, then use the fallback (§8.6).

### 8.2 Voices
- Clear, simple Modern Standard Arabic (فصحى), first person, 1–3 sentences. (Team decision: easier for the model to write correctly and for judges and officials to read than Jordanian dialect.)
- Concrete details: buses, hours, dinars, the helper.
- Respectful, never stereotyping or mocking.
- The prompt receives the citizen profile **and** the engine's outcome: status, reasons, `channel_name_ar`, mode, `bus_transfers`, `visit_day`, minutes, cost and work hours missed. It must not invent numbers, places or people. It may mention only `helper_relation_ar` as a family member. "Two buses" is allowed only if `bus_transfers` says so.
- Voices are always Arabic, whatever the UI language. In English mode, show a one-line English summary under the bubble (from the fallback template, no AI call).

### 8.3 Grounding check (`llm/checks.py`)
Extract every number from AI text (Arabic-Indic and Western digits). Each must match a number in the inputs (rounded). If any doesn't, discard the text and use the fallback. Same check for the report and fix explanations.

### 8.4 Caching
`llm/cache.py` keys each call by `sha256(task + canonical_json(inputs))`, deliberately **without** provider or model. Free text is normalized before hashing (trim, collapse whitespace, unify Arabic letter variants such as أ/إ/آ→ا and ى→ي, strip tashkeel), so a stray space doesn't miss the cache. Leaving the provider out of the key means the fallback provider's answer still counts as a hit. Provider, model and timestamp are stored inside the entry as metadata. Entries go in `backend/cache/`.

**Modes:**
- **Live (default, `DEMO_OFFLINE=0`):** read the cache first; on a miss, call the AI and store the result. **Any new request, including one a judge asks for, works live.**
- **Offline (`DEMO_OFFLINE=1`):** emergency switch for no internet. Cache hits only; a miss uses the fallback (§8.6). Never a crash, never a blank.

**Cache invalidation:** if assumptions or scenarios change after warming, outcomes change and the cache misses. Warm the cache **after** final scenario work.

### 8.5 Policy parse
- The prompt includes the current policy JSON, the list of areas, sites and offices, the schema, and the explicit **"what Nas can model" list** (§5).
- Output is a `ParseResult`: either a full Policy plus a bilingual "understood as" change list, or `unsupported` with a short message saying what can't be modeled and what the closest supported change would be.
- Examples of unsupported requests: a fee waiver for one group (fees are per policy, not per group), an office outside the 8 sites, a second service, changes to bus routes, closing a road outside the catalogue or only on some days.
- Road closures: the parser gets `roads_named_in_text` (a deterministic name match against the catalogue) as a hint; the AI still decides. AI fix proposals must keep the scenario's `closed_roads` (road works are not the service's decision).
- The UI shows the change list in `ParsePreview` and only applies the policy after **Apply**. A wrong parse is visible and harmless.
- Any policy a parse could produce can also be built with the manual controls, so if parsing fails on stage, build it by hand.

### 8.6 Fallbacks (`llm/fallbacks.py`)
Every AI task has a deterministic template, filled from engine output and reason codes, in Arabic and English:
- **Voice:** e.g. "لم أتمكن من إنجاز المعاملة: لا أملك هاتفاً ذكياً، والمكتب بعيد ٤٥ دقيقة بالحافلة." built from reason codes + numbers.
- **Fix explanation:** from the fix id and its drops, e.g. "Saturday mobile van in Marka: 9.1 pts fewer people left out, mostly elderly and no-car."
- **Report:** a short templated summary of KPI deltas and the top-2 worst groups.
- **Parse:** "Couldn't understand that. Try the controls on the left." (no fallback policy).

The response always carries `source: "ai" | "fallback"`. The UI may show a small "template" tag on fallbacks; never hide that it's a fallback.

### 8.7 Fixes call
One `MODEL_SMART` call. Input: the scenario policy, the left-out breakdown by group and reason, and the top 3 grid fixes with their numbers. Output: an explanation (ar/en) for each of the 3, plus **one** off-grid Policy with a title and rationale. The off-grid policy must be expressible in the schema and must not duplicate a grid candidate. The backend runs it through the engine: invalid (fails validation, unknown site/area) → retry once, then drop and log; doesn't beat the best grid fix or worsens any group → hidden. Every fix shown carries a badge: **"Engine-searched · verified"** or **"AI-proposed · verified"**.

## 9. Frontend UX

### 9.1 Language
- Two full UI languages, **Arabic (default) and English**, switched by the language button in the header and remembered in `localStorage` (wrapped in try/catch).
- Switching sets `<html lang dir>`; the layout mirrors in RTL (Policy Panel on the right in Arabic). Use logical CSS properties (`inset-inline-start`, `margin-inline-*`, ...), never left/right, for layout.
- **No UI string is hard-coded in a component.** Every label comes from `nas-frontend/i18n.js` via `t()`.
- Every engine/AI response carries both `_ar` and `_en` text where it is shown to the user; the frontend picks by language.
- Numbers: Western digits in both languages (judges read them faster); dates and times as `HH:MM`.

### 9.2 Layout
Policy Panel · Map · Impact Panel. The Citizen Card opens as a drawer over the map.

- **Map:**
  - Dots colored by status, with a toggle for baseline vs scenario.
  - Citizens who got worse get a pulsing ring.
  - Office pins are **draggable** and snap to the nearest site. Dropping one re-runs `/compare`, debounced by 300 ms.
- **Policy Panel:**
  - Preset scenario buttons.
  - Per-office hours, toggles (online-only, appointments, wheelchair access), "Add mobile unit" (area, day, hours), fee.
  - Free-text box: *"اكتب السياسة بكلماتك"* / "Describe the policy in your own words" → `/policy/parse` → `ParsePreview` → Apply.
- **Impact Panel:**
  - KPI cards with deltas (▲▼).
  - Equity bars by group (elderly, disabled, no-car, offline, low-income, workers) against everyone.
  - "Who is left out" list grouped by reason.
  - **Robustness badge**: "Ranking held 6/6 at ±20%" (or the honest partial result). Clicking it opens `AssumptionsTable`, showing each constant, its value, tag and source.
  - "Suggest fixes" and "Generate report" buttons.
- **Fix Suggestions:** top 3 engine fixes appear instantly with before/after numbers and badges; explanations fill in when the AI returns (skeleton until then); the AI fix appears last if verified. "Apply" applies a fix to the map.
- **Citizen Card:** name, age, area, icons for car/smartphone/mobility, outcome numbers, the Arabic voice bubble (`dir="rtl"`), reason chips in the UI language.
- `SyntheticBadge` always visible: "Synthetic population — demo data, not real people" / "سكان افتراضيون — بيانات تجريبية وليسوا أشخاصاً حقيقيين".
- Map and KPIs never wait on the AI.

## 10. Demo scenarios (preset JSON in `data/scenarios/`)

1. **`baseline`:** today's network: the **7 real CSPD offices in Amman** (Tabarbour head office, Jabal Amman, Marka, Sweileh, Jabal Al-Hussein, Tla' Al-Ali, Wadi Al-Seer; addresses from CSPD's own office list, located with OpenStreetMap, real: true in `sites.json`), 08:30–15:30 Sun–Thu as CSPD publishes, walk-in, online enabled. Wheelchair access is assumed; the fee is JD 2 (the ID-renewal fee, confirmed by the team).
2. **`consolidate`:** close 5 offices, keep only Tabarbour and Jabal Amman. Elderly, offline and no-car residents far from those two feel it.
3. **`digital_first`:** all 7 offices close at 13:00 and office visits need an online appointment. A realistic "digital transformation" policy with a hidden cost to elderly, offline and worker citizens.
4. **`online_only`:** the extreme version, kept as a backup.
5. **`consolidate_digital_first`:** the **demo path** (`"demo": true` in its JSON): `consolidate` **plus** the `digital_first` rules. This is exactly what the §13 script produces, so tune scenarios, pick heroes, find the AI fix and warm the cache against **this** preset. It is also the preset-button fallback if the free-text parse fails on stage. Scripts and the debug page find it by its `demo` flag.

**If a scenario's story doesn't appear, change the scenario, not the assumptions (§6.2).**

### The demo fix
For `consolidate_digital_first`, the engine's top grid fix is a pair of Saturday vans (currently Sweileh + Downtown: service comes back near the closed branches). Whatever the grid actually returns is what we show.

**Guaranteed AI fix:** before warming the cache, run `/fixes` for the demo path until the AI proposes an off-grid policy that the engine verifies beats the best grid fix (try a few prompt variations if needed; e.g. vans in two areas on different days, or a late day plus a Saturday office opening). Save its inputs and output in the cache and note it in `demo_requests.json`. The demo then always shows one "AI-proposed · verified" fix. If none can be found, say so on stage honestly: "the AI's own idea didn't beat the engine's best this time, so it's hidden."

### Hero citizens
After scenarios are final, pick 3–4 fixed citizen IDs and save them in `heroes.json` with a note each: e.g. an elderly woman in Marka with no car whose son helps her; a wheelchair user in Wehdat; a factory worker in Tabarbour on 7–4 shifts. The demo always clicks these, so their voices are cached and checked.

### Judge-request rehearsal (`demo_requests.json`)
List ~6 policies a judge is likely to ask for, run each live once, and keep the cached results:
- "Close all offices on Thursdays" / "اسكروا المكاتب يوم الخميس"
- "Close the Marka office" and "Reopen the Marka office"
- "Make it online-only but keep a Saturday van in Wehdat"
- "Double the fee"
- "Require two visits"
- One unsupported one, e.g. "Make it free for people over 65", to rehearse the honest "not supported yet" answer.

## 11. Team split (3 people)

| Person | Owns | Files |
|---|---|---|
| **A: Engine & data** | seed + anchors, travel model, engine, compare, fix grid, robustness check, tests, scenarios | `backend/app/sim/*`, `backend/app/data/*`, `backend/app/routes/sim_routes.py`, `tests/` |
| **B: Frontend** | bilingual UI, map, panels, citizen card, fix suggestions, assumptions table, API wiring, polish | `nas-frontend/*` |
| **C: AI & pitch** | AI client, prompts, cache, fallbacks, grounding check, parse/voice/report/fixes, AI routes, slides, demo script, Q&A | `backend/app/llm/*`, `backend/app/routes/llm_routes.py`, `README.md` |

`main.py` is created once in the first hour and barely touched after, to avoid merge conflicts.

**Contract-first:** in the first hour, A writes `models.py`, B maps it in `nas-frontend/api.js`, C writes `.env.example`. B builds against a static mock JSON until `/simulate` is live.

**Side tasks (any one person, ~30 min each, early):**
- Source the public figures for `anchors.json` (§6.3).
- A native Arabic speaker reviews ~20 generated voices in hour 3 and fixes the prompt.
- With their consent, ask ~5 elderly or no-car relatives in east Amman: "If ID renewal needed an online appointment, could you book it alone?" Put their anonymized answers next to the simulated voices on one slide. No names, no personal details.

## 12. Build plan (we start at H1; ~10 hours)

| Hours | Goal | Done when |
|---|---|---|
| H1–2 | Scaffold backend + frontend, freeze schemas, areas/sites, `.env`, i18n skeleton (`ar`/`en`, RTL switch), repo pushed. Start anchor sourcing. | `uvicorn` and `npm run dev` run; toggle flips the empty layout |
| H2–4 | **A:** seed + engine + `/simulate` + `/compare`, assumptions frozen. **B:** map with dots + Policy Panel on mock data, bilingual. **C:** client + cache + fallbacks + voice + parse, tested in a script. Native-speaker voice review at H3. | Each part works in isolation |
| H4–6 | **Integration checkpoint.** Scenarios 1–3 tuned *by changing scenarios only*. Citizen Card with voices (AI or fallback). | Change policy → dots recolor → KPIs update → click hero → voice, end to end |
| H6–7 | **A:** `fixgrid.py` + `/fixgrid`. **B:** Fix Suggestions with instant engine fixes + Apply. **C:** ParsePreview flow end to end. | Break → red → voice → engine fix → green, **with no AI dependency** |
| H7–9 | **A:** `sensitivity.py` + `/assumptions`. **B:** equity bars, robustness badge, assumptions table. **C:** `/fixes` explain + off-grid proposal, report, grounding check; find the guaranteed AI fix. | Full story incl. AI fix and robustness badge |
| H9–10 | Polish, pick hero citizens, run `demo_requests.json`, **then** warm the cache. Save the frontend's CDN files (Leaflet, icons, fonts) locally while online. Test with wifi off: `DEMO_OFFLINE=1` and `?offline=1`, in both languages. | Whole demo runs offline and online |
| H10–11 | **FEATURE FREEZE.** Record a backup screen video. Rehearse the 7-min demo 3+ times, including one judge request. | Demo under 6:30 with margin |

**Cut order if behind schedule:** report → AI off-grid fix (keep engine fixes + explanations) → equity chart polish → free-text parse (manual controls still work). **Never cut:** map + simulate + citizen voice + engine fix loop + language toggle.

## 13. Demo script (7 minutes)

1. **0:00–0:45 Problem.** "Every new policy in Jordan is tested on real people after launch. The ones who fall through the cracks are the ones who can't complain: elderly, disabled, no car, no smartphone. Nas reaches them before the policy does."
2. **0:45–1:15 What Nas is.** 1,000 synthetic citizens of east and west Amman, AI-voiced, anchored to public statistics. Show the baseline map and the synthetic badge. Flip the language once to show it's fully bilingual, then stay in Arabic.
3. **1:15–3:00 Break it.** Click the `consolidate` preset: 5 of the 7 real offices close, only Tabarbour and Jabal Amman stay. Then type the `digital_first` rules in Arabic in the free-text box, using the **rehearsed sentence** from `demo_requests.json`; show the "understood as" list; Apply. The result must equal the `consolidate_digital_first` preset (if parsing fails, click that preset). Yellow spreads (hardship roughly doubles) and left-out rises. Click the first hero in `heroes.json` (an elderly woman whose son helps her) and read her voice.
4. **3:00–4:15 Understand it.** Equity bars: elderly and offline citizens hit hardest. Click the robustness badge: "this ranking holds when we move our uncertain assumptions by ±20%."
5. **4:15–5:45 Fix it.** Click "Suggest fixes": the engine's verified fixes appear instantly, then the AI explains them and adds its own idea, also verified. Apply the best one. Green returns. Click the hero again: she's served now.
6. **5:45–6:30 Impact & business.** Who pays: municipalities, ministries, digital transformation programs. Next steps: calibrate with more public data, add more services and cities. One slide with the relatives' real answers next to the simulated voices.
7. **6:30–7:00** Close with the pitch line. Invite a judge to name a policy during Q&A.

## 14. Judge Q&A prep

- **"Are these real people?"** No. A clearly labelled synthetic population, anchored to public figures where we could source them. The engine is data-agnostic; better data drops in.
- **"Didn't you tune it to get this result?"** Assumptions were frozen before any scenario ran; the key ones are anchored; the ranking holds 6/6 at ±20% (badge). If a story didn't show up, we changed the scenario, never the assumptions.
- **"Is the AI making things up?"** No. The engine computes every outcome and number. A grounding check rejects any AI text with a number the engine didn't produce, and every AI fix is re-verified by the engine before it's shown.
- **"What does the AI do that a spreadsheet couldn't?"** See §1.
- **"Does it reach the people left out?"** See §1. Plus: the relatives' answers slide.
- **"Show us another policy."** Type it live. If it's outside what Nas models, it says so and suggests the closest supported change.
- **"Business model?"** SaaS per service/municipality plus a setup engagement to calibrate data. Cheap to run: the engine is CPU-only and AI calls are cached.
- **"Scalability?"** A new service is a policy template + channel rules; a new city is areas + sites + anchors.

## 15. Commands

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.data.seed_census --install            # census-anchored population.json (1,000 citizens, seed=42)
python -m app.data.fetch_map_data matrix             # then refresh OSRM road times for the new homes
uvicorn app.main:app --reload --port 8000
pytest -q

# the app: the backend above also serves the UI -> http://localhost:8000
# ?api=http://<host>:8000 points the UI at another backend, ?offline=1 draws no map tiles

# demo prep (online, after final scenario work)
python -m scripts.pick_heroes && python -m scripts.find_ai_fix && python -m scripts.warm_cache   # from backend/
```

`.env.example` (repo root) lists every setting with a comment: provider keys, model chains per slot
(`MODEL_FAST`, `MODEL_SMART`, `GROQ_MODEL_*`, `OPENAI_MODEL_*`), `LLM_FALLBACK_PROVIDER`, `LLM_TIMEOUT_S`,
`LLM_TOTAL_BUDGET_S` and `DEMO_OFFLINE`. The frontend's backend URL lives in `nas-frontend/config.js`.

## 16. Rules for Claude Code in this repo

- **Ship a working demo over completeness.** Prefer the simplest thing that makes the demo work. No auth, no DB, no Docker, no extra services, no i18n library.
- **Respect the core principle (§2).** The engine decides and searches; the AI explains and proposes; the engine verifies. Never route an outcome or number through the AI.
- **Respect the freeze rule (§6.2).** Never change `assumptions.py` to make a scenario look better. Change the scenario. If asked to, refuse and point to this rule.
- **`models.py` is the API contract.** If you change it, check `nas-frontend/api.js` (its normalisers) in the same change and say so.
- **Keep the engine pure and deterministic.** No randomness at simulate time; randomness only in `seed_census.py` with a fixed seed. Engine functions accept an optional assumptions override (needed by `sensitivity.py`).
- **Every constant goes in `assumptions.py`** with a comment, rationale and `# ANCHORED` or `# ASSUMPTION` tag. Never mark a value ANCHORED without a real source in `anchors.json`.
- **Never present synthetic numbers as real Jordanian statistics** in UI copy, prompts, or the report.
- **No real personal data.** Names come from generic first-name lists only.
- **Every AI call goes through `llm/client.py` + `llm/cache.py` + `llm/checks.py`, and every AI task has a fallback in `llm/fallbacks.py`.** Must work with `DEMO_OFFLINE=1`. Never import a provider SDK outside `llm/`.
- **Respect free-tier rate limits.** Never generate voices for all 1,000 citizens in a loop. Generate on click, plus at most ~5 sampled citizens per worst group for the report.
- **Bilingual UI:** every user-facing string comes from `nas-frontend/i18n.js`; use logical CSS properties so the layout mirrors in RTL. Citizen voices are always Arabic.
- **Frontend computes nothing:** no simulation, scoring or ranking in `nas-frontend/`; adapt shapes only in `api.js`.
- **Before declaring a feature done:** run `pytest -q` for engine changes, and click through the affected demo scenario in the browser **in both languages**.
- **Small, focused commits.** Three people are pushing to the same repo.
