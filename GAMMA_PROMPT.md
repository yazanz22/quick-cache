# Gamma prompt for the Nas pitch deck (8 slides, ~60% technical / 40% business)

Paste everything inside the fence into Gamma (set it to 8 slides). Every number is verified in the research notes
(`I'll go claim by claim.txt`), in `anchors.json`, or is engine output (HANDOFF §6, §15, §16). The research notes say
to drop the GovTech TAM, the "10x–100x rework cost" and unsourced margins; this prompt does. Pricing is labelled a hypothesis.

```
Create an 8-slide pitch deck for "Nas (ناس)", a policy simulator for Jordan's public services, built by a team of 3 at the AI Quest hackathon at Al Hussein Technical University. Audience: a judging panel of technologists and public-sector people. Tone: precise, calm, evidence-led; no hype words. Language: English, with the Arabic name ناس on the title. About 60% of the content is technical, 40% business. Use exactly the numbers given below; do not add statistics or market sizes that are not listed. Visual style: white background, near-black text, one accent green (#2E9E6B) taken from the logo, minimal icons, large numbers, short sentences, max ~45 words per slide of body text plus one visual. Where a screenshot is indicated, leave a clearly marked image placeholder.

SLIDE 1 — Title
"ناس · Nas" — a wind tunnel for public services.
Subtitle: Every policy leaves someone out. Nas shows you who, why, and how to fix it — before you launch.
Footer: AI Quest @ HTU · Smart Society & Public Services · Team of 3.

SLIDE 2 — Problem statement
Title: Every public-service policy in Jordan is tested on real people, after launch.
State the problem in three short lines:
1) When an office closes, hours are cut, or an online appointment becomes required, nobody knows in advance who can no longer reach the service. The impact is discovered after launch, through complaints — and the people who fall through are the ones who cannot complain: the elderly, people with disabilities, people without a car, people who cannot use an app alone.
2) The gap is not devices, it is use: 95.6% of Jordanians use the internet and 80.2% of people aged 65+ own a smartphone, yet only 38.1% used any e-government service in 2024, and only 3.7% of people 65+ use a computer (MoDEE Household ICT Survey 2024). With 85.5% of targeted services already digitised and 100% targeted by end of 2026, the next failures are policy failures, not technology failures.
3) Jordan now requires impact assessment before implementation — the Good Regulation and Impact Assessment System No. 16 of 2025, in force since September 2025, 45 studies received by April 2026 — but there is no tool that can tell a ministry, before launch, who a policy leaves out.
Bottom line, in large type: Who does this policy leave out? Today, no one can answer that before it is too late.

SLIDE 3 — What Nas is (technical)
A digital Amman: 1,000 synthetic citizens, AI-voiced (never "AI citizens"), each with age, mobility, car, smartphone, digital skills, work hours, income band and a family helper, anchored to published figures where found (MoDEE 2024; the 7 real Civil Status offices; real road times from OpenStreetMap routing).
An official changes a policy in Arabic or English — a sentence or the controls — and every citizen is run through it. The map lights up: served / served with hardship / left out. Click a citizen and they explain their outcome in Arabic.
Three sectors today: ID renewal, fuel prices (a price shock, not a service), and Royal Court medical exemptions for the uninsured. New sectors are data, not code.
[Image placeholder: screenshot of the map with the three colours and a citizen card]

SLIDE 4 — How it works: the engine decides, the AI explains, the engine verifies (technical)
Three boxes in a row:
1) Deterministic engine (pure Python, ~50 ms for 1,000 citizens): channels, travel time and cost by mode, work-hour conflicts, appointments, protections; searches ~30 candidate fixes; runs a ±20% robustness check on its most uncertain assumptions.
2) AI (free-tier Gemini/Groq, four jobs only): parse free text into a policy, voice a citizen, write the report, explain fixes and propose one more.
3) Verification: a grounding check rejects any AI text containing a number the engine did not compute; every AI-proposed fix is re-run by the engine and shown only if it beats the best engine fix without hurting any group. Every AI task has an offline template fallback; the whole demo runs with no internet.
Footer line: all 35 engine constants are labelled assumptions, frozen before any scenario ran — if a story did not appear, we changed the scenario, never the constants.

SLIDE 5 — What it found (technical, with real engine output)
ID renewal: closing 5 of 7 offices and requiring online appointments moves the population from 88.4% served / 11.5% hardship / 0.1% left out to 79.6% / 19.5% / 0.9%; 93 people worse off; hardship among the elderly rises from 40% to 85%, among offline residents from 56% to 96%. The ranking of who is hit held in 6 of 6 robustness runs. The engine's best fix (two Saturday mobile units) brings left-out from 9 people to 1; the AI's verified proposal (three units) reaches 92.3% served, 130 people better off.
Fuel prices: a +25% rise with fares raised to match pushes 72 people down and priced-out from 10.0% to 15.2%; the engine's best fix (14 JD/month for people without a car plus a bus-fare freeze) helps riders but not middle-income drivers — the tool says so instead of hiding it.
Medical exemptions: today's process (two 2-hour visits to one office) leaves 0% of the 441 uninsured served without hardship (74.8% hardship, 25.2% left out). Applications through Sanad only would serve 77.6% but leave 8.4% out — all offline residents with nobody to help; the engine's fix (intake at the 7 Civil Status offices plus a Saturday intake day in Downtown) brings left-out to 0.2%.
[Image placeholder: before/after map or the fixes panel]

SLIDE 6 — Who pays, and why now (business)
Named first buyer: the Prime Ministry's impact assessment unit (System No. 16 of 2025) and the ministries it now requires to assess policies. Jordan's Digital Transformation Strategy 2026–2028 tracks exactly what Nas measures: use of digital services by vulnerable groups, ease of access to service centres, customer effort — and plans predictive models for policy effectiveness. The Digital Inclusion Policy 2025 names the elderly, people with disabilities, women and remote residents, and plans incentives for startups serving them.
Market: 20+ ministries and 28 government entities in Jordan; central government and donor-funded programmes first (municipal debt exceeds JD 630M against a JD 420M budget, so municipalities come later).
Model: SaaS per service and agency plus a calibration engagement. Pricing hypothesis, unvalidated: $30K–$75K per agency per year, against custom six-figure contracts for enterprise simulation platforms such as Replica. Costs are low: a CPU-only engine and cached AI calls.
How we differ from Replica, UrbanSim, traffic simulators: service access rather than traffic, vulnerability modelled explicitly, Arabic in and out, synthetic data by design (no personal data).

SLIDE 7 — Next, and the ask
Next 90 days: calibrate with DoS and MoDEE microdata; add the capacity/queue model (today, days are interchangeable); more services (first ID at 16, chronic medication pickup, disability card) and more cities — each is areas, sites and anchors, not new code.
Honest limits on the slide: synthetic population; 35 labelled assumptions; no behaviour change modelled (people don't switch modes when prices rise).
The ask: a pilot with the impact assessment unit on one real policy before it launches.
Close with the line: Every policy leaves someone out. Nas shows you who, why, and how to fix it — before you launch.

SLIDE 8 — Team and sources
Left column, "Team": three names with roles, equal weight, no photos:
- Sultan Abbas — Software Engineer
- Yazan Zarka — Software Engineer
- Omar Hawasheen — Data Scientist
Right column, "Sources", small type, one line each:
- MoDEE, Household ICT Usage and Access Survey 2024 (internet 95.6%, smartphones 97.5%, e-government use 38.1%, computer use 3.7% among 65+)
- MoDEE, Jordanian Digital Inclusion Policy 2025
- MoDEE, Digital Transformation Strategy and Implementation Plan 2026–2028
- Prime Ministry, Good Regulation and Impact Assessment System No. 16 of 2025 (in force September 2025)
- Petra News Agency: 85.5% of government services digitised, 100% targeted by end of 2026
- Civil Status and Passports Department, services guide and office list (JD 2 fee, 7 Amman offices)
- Department of Statistics, Health Insurance in Jordan, 2015 census analytical paper (Amman: 44.8% of Jordanians uninsured)
- Department of Statistics / DHS, Population and Family Health Survey 2023
- Fuel Pricing Committee, October 2026 prices (Jordan News, 1 Oct 2026); National Aid Fund fuel support 8–14 JD/month (Ammon News)
- OpenStreetMap and OSRM (road distances and times); map data © OpenStreetMap contributors
- Jordan News: municipal debt exceeds JD 630M
Footer: "Synthetic population — demo data, not real people. All engine constants are labelled assumptions."
```

Screenshots for slides 3 and 5: see `PITCH_OUTLINE.md`, "Screenshots to take" (production URL, Arabic, 1280×720, light theme).
