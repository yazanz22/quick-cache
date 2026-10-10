# Nas frontend (UI only)

A static, bilingual (Arabic RTL / English) frontend for the Nas policy simulator. No build step, no framework.
**It computes nothing.** Every number, outcome, fix and sentence comes from the backend described in `CLAUDE.md` §5 and §7.

```
nas-frontend/
├── index.html   # layout + all CSS (light/dark tokens, RTL, responsive)
├── config.js    # backend URL, timeouts, offline map, fallback areas/heroes  <- edit this
├── api.js       # the ONLY file that knows routes and JSON shapes            <- adapt this if the backend differs
├── i18n.js      # every UI string, ar + en
└── app.js       # UI logic: rendering, map, events, request ordering
```

## Run it

The backend serves this folder itself: start it (`uvicorn app.main:app --port 8000` from `backend/`) and open
**http://localhost:8000**. `config.js` then uses the page's own origin as the API.

To work on the UI separately, `python -m http.server 3000 --directory nas-frontend` also works (the backend's
CORS allows port 3000, and `config.js` falls back to http://localhost:8000). To point at another backend without
editing anything: `?api=http://192.168.1.20:8000`.

If the backend is down, the page shows a "can't reach the engine" screen with the URL it tried and a Retry button.

## Sectors (services)

The page always opens on a **start state**: the left panel lists one card per sector from `GET /services`
("اختر القطاع / Choose a sector"; names from i18n `svc_name_<id>`: ID renewal, **Fuel prices** for `everyday_travel`,
**Medical exemptions** for `medical_exemption`, always in that order; the backend's `description_*` as one line). The map shows every resident as a neutral dot (no pins, rings, heroes or
steps), the right panel shows a short note instead of KPIs, and no `/compare` is sent. The sector is **not** remembered.
`?sector=id_renewal`, `?sector=everyday_travel` or `?sector=medical_exemption` skips the list (for the stage).

Choosing a card loads that sector: its presets (`/scenarios` filtered by `service`, its `baseline_scenario` first and
used as the compare baseline), its heroes (`/heroes?service=<id>`), and a policy panel built from `ServiceInfo.levers`.
The panel head has a back button ("→ القطاعات / ← Sectors") that returns to the start state and drops everything (policy,
fixes, robustness, report, drawer, filter). Strings that differ per sector are `<key>_<service id>` overrides in
`i18n.js` (e.g. `served_everyday_travel` = "Fine"), picked by `ts()` in `app.js`; ID renewal has none, so it reads as before.

## What the UI calls

All bodies are JSON. Field names follow `backend/app/models.py` (CLAUDE.md §5). Timeouts: `config.js` `TIMEOUT_MS`
(20 s) by default, `TIMEOUT_AI_MS` per AI route (30 s for `/fixes` and `/report`, 25 s for `/policy/parse` and `/citizen/voice`).

| When | Call | Body | UI expects back |
|---|---|---|---|
| Page load | `GET /population` | | `Citizen[]` (or `{citizens: [...]}`) with `tags` (the backend always sends them) |
| Page load | `GET /sites` | | `[{id, name_ar, name_en, lat, lng, area}]` (or a dict keyed by id) |
| Page load | `GET /scenarios` | | `[{id, name_ar?, name_en?, description_ar?, description_en?, policy, demo?, service?}]`, or a dict `{id: {...}}`, or `{id: Policy}`. `service` (else `policy.service`, else `id_renewal`) puts it in a sector; the sector's `baseline_scenario` (ID renewal: `baseline`) is its baseline |
| Page load | `GET /assumptions` | | `[{name, value, tag, rationale, source, label_ar?, label_en?, unit?, rationale_ar?, source_ar?, service?}]` (the table shows rows whose `service` is the current sector or `shared`; untagged rows always) (`source`: a short context note or null; every tag is ASSUMPTION) or a dict `{NAME: {value, tag, rationale, source}}` |
| Page load, optional | `GET /areas` | | `[{id, name_ar, name_en, lat, lng}]`. 404 → uses `config.js` AREAS |
| Page load, optional | `GET /services` | | `[{id, name_ar, name_en, description_ar, description_en, levers[], baseline_scenario, demo_scenario}]`. 404 → `config.js` SERVICES (ID renewal only). A service with no scenario in `/scenarios` isn't listed |
| A sector is chosen (once per sector) | `GET /heroes?service=<id>` | | `[{id, note_ar, note_en, service}]` or `["c_0262", ...]`. Only heroes whose `service` matches are kept (an older backend that ignores the parameter sends ID-renewal heroes). 404 → `config.js` HERO_IDS for ID renewal. The note shows under the name on the citizen card |
| Page load, and after every AI call | `GET /llm/status` | | `{offline, providers, models: [{provider, slot, model, available, cooldown}]}`. Drives the header chip: "AI live", "AI: cache only" (`offline`) or "AI resting (rate limit)" (no model available); clicking it lists the models. Failure hides the chip |
| Any policy edit, pin drop (300 ms debounce) | `POST /compare` | `{baseline, scenario}` | `CompareResult`. A 4xx (the engine rejects the policy) restores the last policy that ran, with its applied fix, fixes and robustness result, and shows a translated reason (bad hours / unknown site or area / contradictory settings) with no Retry. Retry is offered only for network errors and 5xx |
| A fix is applied (for the green "got better" rings, the three-step status on the citizen card and the KPI deltas "vs the policy before the fix") | `POST /compare` | `{baseline: <policy before fix>, scenario: <fix policy>}` | `CompareResult` |
| "Suggest fixes" | `POST /fixgrid` | `{baseline, scenario}` | `{fixes: FixCandidate[], scenario_kpis}` (a bare list also works). Shown immediately, with "left out 9 → 1 · hardship 195 → 90" from `fix.kpis` vs `scenario_kpis` and "N changes" from `n_changes` |
| Right after `/fixgrid`, only if a fix has no `kpis` (older backend) | `POST /simulate` × each fix | `{policy}` | `SimResult`. Only `kpis` is used. Failure just hides the counts |
| Right after `/fixgrid` | `POST /fixes` | `{baseline, scenario}` | `{fixes: FixCandidate[], source, ai_proposal: {status, ...}}`. Explanations are matched to grid fixes **by `id`**; one with `source: "ai_proposed"` becomes the AI card (its explanation is shown up to the first " — ", i.e. the AI's own rationale). Without an AI card, `ai_proposal.status` picks the note: `hidden_not_better`, `hidden_worsens_a_group`, `hidden_duplicate_of_grid`, `hidden_no_change`, `invalid`, `ai_unavailable`, `no_grid_fixes` |
| The robustness badge is clicked (if not yet run for this policy); automatically once fixes have loaded (with the top fix) and after a fix is applied (with that fix). Never on every edit | `POST /sensitivity` | `{baseline, scenario, fix}` | `SensitivityResult`. `fix` is `null` before fixes exist: the backend then checks the ranking only (`fix_checked: false`) and the badge says the fix is checked later. Until it runs, the badge reads "Check robustness". `stable_top2` (same two groups, order flips) is named when the ranking doesn't hold. `api.js` sends the fix's `policy` and maps the backend's `details[]` to `detail: [{key, factor, top2, fixHelps}]` for the per-run table (labelled from `/assumptions`) |
| "Read it" (free text) | `POST /policy/parse` | `{text, current_policy, lang}` | `ParseResult` (+ `source`). `source: "fallback"` shows the backend's message as is, under a neutral heading with a "template" tag |
| Click a citizen | `POST /citizen/voice` | `{citizen_id, policy}`: the policy whose outcome the card shows (after a fix is applied, the fix policy; in the "Before" view, the baseline). The backend recomputes the outcome | `{text_ar, summary_en, source: "ai" \| "fallback"}`. `summary_en` is shown under the Arabic bubble in English mode. On failure the card says the words couldn't be loaded, with a Retry button; failures aren't kept |
| "Write report" | `POST /report` | `{baseline, scenario, fix}`: `scenario` = the policy before any fix, `fix` = the applied fix's policy or `null` (the report then covers the fix too) | `{summary_ar, summary_en, source}`. Newlines become paragraphs. Kept per policy pair; if another modal is open when it arrives, it shows on the next click |

### Shapes the UI relies on

- `SimResult.kpis`: `pct_served`, `pct_hardship`, `pct_left_out` (0-100), `avg_hours_lost`, `avg_cost_jd`, `n`, `n_served`, `n_hardship`, `n_left_out` (people, shown as "9 of 1,000"), `n_home_visits`, `left_out_by_reason` (`{reason: n people}`, for "Who is left out"; a person with several reasons counts under each, and the panel says so when the rows add up to more than `n_left_out`). If the `n_*` or `left_out_by_reason` keys are missing, the UI counts the outcomes instead.
- `SimResult.by_group`: `{tag: {served, hardship, left_out}}` in percent. Any tag is shown; known ones get translated labels (`elderly, disabled, no_car, offline, low_income, worker, student`), defined in a glossary (the "i" next to "Who carries the cost?").
- `SimResult.outcomes[]`: `citizen_id, status, channel, channel_name_ar, channel_name_en, mode, bus_transfers, visit_day, travel_minutes, cost_jd, hours_lost, work_hours_missed, reasons[]`. A home visit has `channel: "home_visit"`, `mode: "home"` (the card then hides the travel facts).
- `CompareResult`: `baseline`, `scenario`, `flipped_worse[]`, `flipped_better[]`, `kpi_delta`, `worst_groups[]`. `kpi_delta` is used when present (else recomputed from the two `kpis`). When nobody's status changes, the impact panel says so (Nas doesn't model queues or capacity).
- `FixCandidate`: `id, title_ar, title_en, policy, source, left_out_drop, hardship_drop` (percentage points; a negative drop shows as a rise), `n_changes`, `kpis`, `explanation_ar/_en` (may be null). Optional `explanation_source: "ai" | "fallback"` per fix; otherwise the `/fixes` response's `source` is used for the tag. Titles are shown as sent (they keep Arabic-Indic digits).
- `ParseResult`: `status: "ok" | "unsupported"`, `policy`, `changes_ar[]`, `changes_en[]`, `message_ar`, `message_en`, `source`.
- 4xx bodies: `detail` as a string (the engine's policy checks) or a list `[{loc, msg, type}]` (schema errors); `api.js` turns both into `err.detail` text.
- Reason codes and modes are the enums from §5; their labels live in `i18n.js` (`r_TOO_FAR`, `m_bus`, ...). Plurals use `key_one/_two/_few/_many/_other` variants picked by `Intl.PluralRules`.

### Everyday travel (fuel prices)

- **Policy fields the panel edits** (`ServiceInfo.levers` = `fuel`, `fares`, `cash_support`, `transport_vouchers`):
  `fuel_price_change_pct` (stepper −50..+100, step 5; next to it "90-octane 1.050 JD/L → X", display only, from
  `config.js` `FUEL_PRICE_90_JD`), `bus_fare_change_pct` and `taxi_fare_change_pct` (each: "Follow fuel" = `null`,
  "Freeze" = `0`, "Custom %" = a −50..+100 stepper that skips 0), `cash_support` (`[{groups, amount_jd_month}]`: group
  chips + a 0..50 JD/month stepper, step 2; the panel shows the first entry and editing replaces the list), and
  `transport_vouchers` (the same voucher control as ID renewal). Everything else in the Policy is sent as the preset had it.
- **Outcome fields the citizen card reads**: `purpose` (work / university / hospital), `channel_name_*` (the destination),
  `mode` (car, helper_car = "family member's car", bus with `bus_transfers`, taxi), `days_per_week`, `travel_minutes` (one way),
  `monthly_cost_before_jd` → `cost_jd` with `extra_jd_month`, `income_share_pct`, `cash_support_jd_month` (when > 0), `reasons`.
  `channel: "no_regular_trip"` shows a one-line note instead. Missing fields are hidden.
- **KPIs**: the status words are fine / squeezed / priced out (بخير / مضغوطون / عاجزون عن التنقل). Under the cards, when present:
  `avg_monthly_cost_jd`, `avg_extra_jd_month` (+ `total_extra_jd_month`), `avg_income_share_pct`, `n_cash_support`; deltas from
  `kpi_delta` (else the plain difference). "Who is squeezed or priced out" lists `left_out_by_reason` and `hardship_by_reason`
  (reasons `TRANSPORT_OVER_BUDGET`, `FUEL_COST`, `FARE_COST`); clicking one dims everyone else of that status on the map.
  `by_purpose` / `by_mode` (`{key: {served, hardship, left_out, n}}` in percent) are drawn as small bars. The glossary adds the
  two thresholds from `/assumptions` (`TRANSPORT_SHARE_SQUEEZED`, `TRANSPORT_SHARE_PRICED_OUT`).
- **Map**: no pins (the backend has no hub coordinates; offices and vans are ID-renewal levers), no candidate-site marks.
- Fixes, robustness and the report work exactly as for ID renewal (titles and numbers from the backend; the report heading names the sector).

### Medical exemptions (Royal Court)

- **Who**: only residents without health insurance (tag `uninsured`, `Citizen.has_health_insurance: false`) apply. An insured
  resident's outcome has `channel: "not_applicable"`: the map draws them in the neutral blue idle style (lighter), the legend adds
  "مؤمَّن صحياً: لا ينطبق / Insured: not applicable" with `kpis.n_not_applicable`, and their card shows a one-line note with no
  numbers, no reasons and no voice call. `api.js` leaves them out of the counts when it has to count outcomes itself.
- **KPIs** are over the uninsured: the cards read "N of `n_eligible` uninsured" ("{n} من {t} غير مؤمَّن"), with a line
  "`n_not_applicable` insured residents don't need the exemption". Status words are ID renewal's. Fix cards say "left out 40 → 12 ·
  hardship ... of the uninsured". The `uninsured` bar is hidden here (it is everyone counted); in the other sectors it shows only
  if the backend sends it, labelled "غير المؤمَّنين صحياً / Uninsured", and it is never named under a reason. The glossary adds it.
- **Policy panel** (`ServiceInfo.levers` = `offices`, `online`, `mobile_units`, `visits`, `proxy`, `protections`): the ID-renewal
  controls, relabelled through `<key>_medical_exemption` strings: intake offices (open, close, move to any site, incl.
  `royal_court_csu`; "Open an intake office" lists the areas and then the Royal Court site as its own option `site:<id>`), online
  via Sanad on / off / only, mobile intake days, visits, protections (no walk-in without the `appointments` lever, no fee discount
  without the `fee` lever), and **"التقديم بالإنابة / Applying on someone's behalf"**: one switch bound to `proxy_allowed`
  (`null` = the service default, shown on; the switch always writes `true` / `false`). No fee or appointment control.
- **Sites**: `config.js` `SERVICE_ONLY_SITES` (`royal_court_csu: "medical_exemption"`) keeps the Royal Court site out of the other
  sectors' site lists, pin snapping and map marks, so ID renewal still offers its 15 sites.
- **Citizen card**: channel, mode (`helper_visit` = "قريب من الدرجة الأولى قدّم بدلاً عنه/عنها / A relative applied on his/her
  behalf", with the helper relation), day, travel, visits (`outcome.visits` if sent, else the policy's `visits_required`, hidden
  with the Sanad-and-collect option), time lost and cost. Online reads "عبر سند / via Sanad". A "health insurance" chip joins the
  profile chips.

### What the UI sends as a Policy

Exactly §5's `Policy`. When an office pin is dragged it snaps to the nearest site and sets `site_id`, `id = "office_<area>"`, `name_ar`, `name_en` from `/sites`. "Open an office" adds one the same way at the chosen area's site (the real CSPD office there if any; a suffix keeps the id unique) with the first office's hours; the trash button removes one. Mobile units are `{area, day, open, close}`. Days are `sat..fri`, times `HH:MM`. The panel never sends hours the engine rejects: a closing time less than an hour after the opening time (offices and mobile units) is refused in place with a message, and switching "Online only" on also switches online on.

The "Protections for groups" section edits `appointment_exempt_groups` (group chips), `fee_discounts` (chips + a 25-100 % stepper; every chosen group gets the same %), `transport_vouchers` (one voucher: chips + a 1-20 JD stepper), `home_visits` (switch, chips, 10-200 slots stepper) and `hybrid_pickup` (switch). A stepper with no group chosen only changes the value the next chosen group gets; it doesn't re-run the policy (an applied fix stays). A policy from free text can hold more than the panel shows (e.g. two vouchers); the panel shows the first and editing replaces it.

## If the backend's shapes differ

Change `api.js` only. Each endpoint function returns the normalised shape above; `app.js` never touches raw responses.

## Notes

- Requests that come back out of order are ignored (only the latest `/compare` wins).
- Language and theme are remembered in `localStorage` (wrapped in try/catch).
- Accessibility: the modals trap focus and return it to the button that opened them; only the voice bubble and the KPI cards are live regions; the Impact / Fixes tabs follow the tablist pattern (arrow keys). Text meets 4.5:1 in light and dark (status text on soft backgrounds uses the `--*-ink` tokens).
- Layout: at 1280×720 the citizen card stops above the hero bar; under 1024 px the heroes are a scrollable row on the map and the Impact panel comes before the Policy panel.
- Leaflet, the Phosphor icons and the IBM Plex fonts are vendored in `vendor/` (sources and licences in `vendor/README.md`). Only map tiles (OpenStreetMap) need internet: for the venue, set `OFFLINE_MAP: true` (or open with `?offline=1`) to draw each area as a 1.6 km zone without tiles. The map frames the central 90% of residents; area labels move out from under office pins.
