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
- One service for the MVP: national ID renewal. Add services and cities by data, not code.
- Then: **switch to the live app.** (Baseline: 88.4% served · 11.5% hardship · 1 person left out.)

## 4. Live: break it (1:15–3:00) — no slide; app on screen
- Consolidate to 2 offices → type the policy in Arabic → the AI's "understood as" list → apply.
- 79.6 / 19.5 / 0.9 · 93 people worse off · 9 left out · 195 in hardship. Dana's voice.

## 5. Live: understand it (3:00–4:15) — no slide
- Elderly hardship 40% → 85%, offline residents 56% → 96%. Robustness badge: ranking held 6/6 at ±20%.

## 6. Live: fix it (4:15–5:45) — no slide
- Engine fixes instantly (Saturday vans Sweileh + Downtown: left out 9 → 1, hardship 195 → 90), AI explains and proposes
  a third van (hardship 195 → 76), engine verifies. Apply: **92.3% served, 130 people better off.** Dana is served.

## 7. How it works (one slide, 5:45) — show while switching back from the app
- Three boxes: **Engine** (deterministic, decides every outcome, searches ~30 candidate fixes, ±20% robustness check) →
  **AI** (parses Arabic/English into a policy, voices citizens in فصحى, explains fixes, proposes one more) → **Engine
  verifies** every AI proposal; a grounding check rejects any AI number the engine didn't compute.
- Footer: every AI task has an offline template fallback; the demo runs with no internet.

## 8. Who pays and what's next (5:45–6:30)
- Buyers: Greater Amman Municipality, ministries running digital-transformation programmes, CSPD itself.
- Model: SaaS per service and municipality + a calibration engagement. CPU-only engine, cached AI: cheap to run.
- Next: calibrate with more public data, add capacity/queues ("why Thursday doesn't matter today"), more services
  (passports, licences), more cities (areas + sites + anchors).
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
  transfer rule; synthetic incomes; one service. Each is the next module, not a hidden flaw.

## Screenshots to take for the slides (production, Arabic, 1280×720, light theme)
1. Baseline map with the synthetic badge visible.
2. The "understood as" list after the stage sentence.
3. Demo-path map with the pulsing rings + the KPI cards (79.6 / 19.5 / 0.9).
4. Dana's card: today → policy, with her voice.
5. Equity bars (elderly, offline).
6. Robustness modal (6/6 and the table).
7. Fixes panel with the engine cards and the AI card ("AI-proposed · verified", 3 changes).
8. After Apply: 92.3% served; Dana's card today → policy → after fix.
