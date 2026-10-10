# Gamma prompt for the Nas pitch deck (9 slides)

Paste everything inside the fence into Gamma: **Create new → Paste in text → "Preserve" text** (so Gamma keeps every
source tag), 9 cards, 16:9. Every figure carries its source in brackets; the full list with links is on slide 9.
Engine numbers are tagged (Nas simulation). Figures come from `anchors.json`, `data/census/VALIDATION.md`, the research
notes (`I'll go claim by claim.txt`) and engine output (HANDOFF §6, §15, §16). Dropped on purpose: the GovTech TAM,
the "10x–100x rework cost", municipal debt, and the sector results slide (the live demo shows them).

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
6. Ad-Dustour, on the Good Regulation and Impact Assessment System No. 16 of 2025 — https://www.addustour.com/articles/1512441-%D9%82%D8%B1%D8%A7%D8%A1%D8%A9-%D9%81%D9%8A-%D9%86%D8%B8%D8%A7%D9%85-%D8%A7%D9%84%D8%AA%D9%86%D8%B8%D9%8A%D9%85-%D8%A7%D9%84%D8%AC%D9%8A%D8%AF-%D9%88%D8%AA%D9%82%D9%8A%D9%8A%D9%85-%D8%A7%D9%84%D8%A3%D8%AB%D8%B1
7. Petra News Agency, minister urges data-driven legislative reform (impact assessment studies) — https://www.petra.gov.jo/en/news/minister-urges-data-driven-legislative-reform-to-boost-public-trust
8. Prime Ministry, Tawasul consultation on impact assessment instructions — https://tawasal.gov.jo/Consultations/redirect/1275
9. UN General Assembly, Report of the Special Rapporteur on extreme poverty and human rights (digital welfare state), A/74/493, 2019 — https://documents.un.org/doc/undoc/gen/n19/312/13/pdf/n1931213.pdf

Population and places
10. Department of Statistics figures as reported by The Jordan Times (47% women) — https://www.facebook.com/thejordantimes/posts/director-general-of-the-department-of-statistics-dos-haidar-fraihat-said-jordans/1482363837271805/
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

Screenshots for slide 3: see `PITCH_OUTLINE.md`, "Screenshots to take" (production URL, Arabic, 1280×720, light theme).
