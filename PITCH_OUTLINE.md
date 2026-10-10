# Nas pitch: slide outline (7 min talk + 3 min Q&A)

The live demo carries the middle of the talk (see `DEMO_RUNBOOK.md`); slides bracket it. Keep slides to one idea each,
Arabic on screen with English subtitles if the jury mixes. Every number below is current engine output.

## 1. Title (0:00)
- **ناس · Nas** — a wind tunnel for public services.
- One line: *Every policy leaves someone out. Nas shows you who, why, and how to fix it before you launch.*
- Team of 3 · AI Quest @ HTU · Smart Society & Public Services.

## 2. The problem (0:00–0:45)
- Every new public-service policy in Jordan is tested on real people **after** launch.
- The ones who fall through are the ones who can't complain: elderly, disabled, no car, no smartphone, shift workers.
- Visual: a form on a phone screen; next to it an older woman with no phone. (Stock or illustration, no real person.)

## 3. What Nas is (0:45–1:15)
- A digital Amman: **1,000 synthetic citizens, AI-voiced** (never "1,000 AI citizens"). Age, mobility, car, smartphone,
  digital skills, work hours, income, who helps them at home.
- Anchored to published figures where we found them (MoDEE 2024: 95.6% internet use, 99% smartphone households, 38.1%
  e-gov use), the 7 real CSPD offices in Amman, real road times from OpenStreetMap routing.
- Three sectors on the same engine and population: **national ID renewal** (the live demo), **fuel prices** (slide 7b) and
  **Royal Court medical exemptions** for the uninsured (slide 5 aside, backup B6). Add services and cities by data, not code.
- Then: **switch to the live app.** (Baseline: 88.4% served · 11.5% hardship · 1 person left out.)

## 4. Live: break it (1:15–3:00) — no slide; app on screen
- Consolidate to 2 offices → type the policy in Arabic → the AI's "understood as" list → apply.
- 79.6 / 19.5 / 0.9 · 93 people worse off · 9 left out · 195 in hardship. Dana's voice.

## 5. Live: understand it (3:00–4:15) — no slide
- Elderly hardship 40% → 85%, offline residents 56% → 96%. Robustness badge: ranking held 6/6 at ±20%.
- (Optional aside, ~15 s, or the answer to "who does going digital leave out?") **The same pattern in health: Royal Court
  medical exemptions**, over the 441 synthetic residents without health insurance. Today: one office, two visits, nobody
  served (0.0 / 74.8 / 25.2). **Sanad only: 364 people better off, 30 worse off, all offline with nobody to apply for them**
  (offline left out 29.3% → 37.4%). The engine's fix, intake at the 7 Civil Status offices + a Saturday intake day in
  Downtown: left out 8.4% → 0.2%. Robustness 6/6. Footer: uninsured rate anchored to DoS 2015 (44.8% of Amman's Jordanians);
  the process from press reports; hours and visit time are labelled assumptions.

## 6. Live: fix it (4:15–5:45) — no slide
- Engine fixes instantly (Saturday vans Sweileh + Downtown: left out 9 → 1, hardship 195 → 90), AI explains and proposes
  a third van (hardship 195 → 76), engine verifies. Apply: **92.3% served, 130 people better off.** Dana is served.

## 7. How it works (one slide, 5:45) — show while switching back from the app
- Three boxes: **Engine** (deterministic, decides every outcome, searches ~30 candidate fixes, ±20% robustness check) →
  **AI** (parses Arabic/English into a policy, voices citizens in فصحى, explains fixes, proposes one more) → **Engine
  verifies** every AI proposal; a grounding check rejects any AI number the engine didn't compute.
- Footer: every AI task has an offline template fallback; the demo runs with no internet.

## 7b. Not only services: a price shock (one slide, ~20 s; or the first Q&A answer)
- Title: **ليست الخدمات فقط: صدمة أسعار / Not only services: a price shock.** Same engine, same 1,000 synthetic citizens,
  a second sector: **fuel prices**. Each citizen's one regular trip (work, university, hospital) priced per month against
  their income: fine (< 10%), squeezed (10-20%), priced out (≥ 20%).
- Numbers (engine output vs today's prices, 72.2 fine / 17.8 squeezed / 10.0 priced out):
  - This month's real rise (+0.05 JD/L on 90-octane, ≈ +5%): **7 people worse off, all drivers**.
  - Fuel +25%, fares held: 24 worse off, all drivers. Fares are regulated and lag fuel.
  - **Fuel +25% and fares +25% (as after 2012): 72 worse off, priced out 10.0% → 15.2%**, 4.54 JD a month extra on average;
    hit hardest: workers, offline, low income. Low-income bus commuters were already at ~30% of income before the rise.
  - 14 JD a month for low-income people (the top of the National Aid Fund's 8-14 JD) only brings priced out to 14.5%.
  - The engine's best fix: **14 JD a month for people without a car + freeze bus fares: −7.2 points priced out.** And it shows
    who it still misses: Issa, a middle-income driver, stays priced out.
- Footer: fuel prices and NAF support from press reports (CITED); the 7 travel constants are labelled assumptions, frozen
  before any travel scenario ran; robustness 5/6 at ±20% (the top group, workers, holds in every run).
- Visual: the fuel map with the KPI cards (70.2 / 14.6 / 15.2) and Issa's card (17.6% → 20.2% of income).

## 8. Who pays and what's next (5:45–6:30)
- Buyers: Greater Amman Municipality, ministries running digital-transformation programmes, CSPD itself.
- Model: SaaS per service and municipality + a calibration engagement. CPU-only engine, cached AI: cheap to run.
- Next: calibrate with more public data, add capacity/queues ("why Thursday doesn't matter today"), more services
  (passports, licences; the fuel and medical-exemption sectors each took a day, not a rebuild), more cities (areas + sites +
  anchors).
- **Relatives' answers slide** (if collected): 3–5 anonymised quotes from elderly/no-car relatives in east Amman next
  to the simulated voices. No names.

## 9. Close (6:30–7:00)
- The pitch line again. "Name a policy and we'll test it now."

---

## Backup slides (for Q&A, don't present)
- **B1. What is real, what is assumed** — copy the README section "What is real and what is assumed".
- **B2. Group definitions** — elderly 65+ (65 people) · disabled = limited mobility or wheelchair (69) · low income =
  bottom 30% of synthetic income (300) · offline = no smartphone or low digital skills (204) · no car (534) ·
  workers (320) · students (164).
- **B3. The robustness table** — screenshot of the assumptions modal: 26 constants, all labelled ASSUMPTION, 3 perturbed.
- **B4. Protections instead of vans** — keep the policy, protect people: walk-in for elderly + disabled → 81.6% served;
  + 20 home visits → 83.6%, left out 0.5%; all five levers → 87.1 / 12.6 / 0.3.
- **B5. Honest limits** — no capacity or queue model (days are interchangeable); 8 coarse areas and an east/west bus
  transfer rule; synthetic incomes; in the fuel sector nobody switches mode when prices change, and the map has no pins for
  workplaces or hospitals; in medical exemptions the Royal Court unit's location is approximate and its hours assumed, and
  letting a relative apply changes nobody (relatives work the same hours). Each is the next module, not a hidden flaw.
- **B6. The Royal Court medical exemption (health insurance)** — built as the third sector; who is uninsured in Amman,
  from official figures (**now used by the engine**):
  - DoS, *Health Insurance in Jordan* (Census 2015 analytical paper, ANCHORED): **in Amman, 55.2% of Jordanians are insured
    (44.8% are not)**; 41.2% of the total population (58.8% not); Amman and Zarqa are the least-covered governorates (41%).
  - Nationally: 68.7% of Jordanians and ~56% of all residents insured; every child under 6 is insured by the Ministry of
    Health; the least-covered ages are 15-34; non-Jordanians 25.3% (16.4-16.8% in Amman).
  - JPFHS 2023 (DoS / DHS, ANCHORED): 69% of ever-married women and 59% of men aged 15-49 have any health insurance.
  - **Now used by the engine:** income-band uninsured rates (65 / 45 / 20%, an assumption calibrated to the anchored 44.8%,
    which covers all ages including the fully insured under-6s) give **441 of 1,000 synthetic adults uninsured (44.1%)**; who
    can reach an exemption: the Citizen Services Unit, intake offices, mobile intake days, Sanad, a relative.
  - The process (press reports, CITED): in person with a medical report, a Ministry of Health doctor's review, a return visit
    for the letter. Hours and queue time are not published: labelled assumptions.
  - Numbers: today 0.0 / 74.8 / 25.2; Sanad only 77.6 / 14.1 / 8.4 (364 better, 30 worse); engine fix: left out 8.4 → 0.2.
  - Footnote (say it if asked): we dropped two figures from our desk research, a "76.8% insured" whose own breakdown sums to
    84.9%, and a "38% of non-Jordanians insured" that was a misreading of DoS. Checked figures only.

## Screenshots to take for the slides (production, Arabic, 1280×720, light theme)
1. Baseline map with the synthetic badge visible.
2. The "understood as" list after the stage sentence.
3. Demo-path map with the pulsing rings + the KPI cards (79.6 / 19.5 / 0.9).
4. Dana's card: today → policy, with her voice.
5. Equity bars (elderly, offline).
6. Robustness modal (6/6 and the table).
7. Fixes panel with the engine cards and the AI card ("AI-proposed · verified", 3 changes).
8. After Apply: 92.3% served; Dana's card today → policy → after fix.
9. Fuel sector (`?sector=everyday_travel`, preset fuel +25% with fares): the map and KPI cards (70.2 / 14.6 / 15.2), and
   Issa's card after the top fix (still priced out) for slide 7b.
10. Medical exemptions (`?sector=medical_exemption`, preset Sanad only): the map with the lighter insured dots and the KPI
    cards ("N of 441 uninsured", 77.6 / 14.1 / 8.4), and Salma's card today → Sanad only → after fix, for slide 5 and B6.
