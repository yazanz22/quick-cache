# Nas demo runbook (Day 2, 7 min + 3 min Q&A)

Everything below was verified on the 2026-10-10 build. Numbers are exact engine output; say them as they are.

## Morning checklist (before slides)
1. **Deploy Render by hand** (dashboard → Manual Deploy → latest commit). Auto-deploy does not fire. Then open
   https://nas-rbo5.onrender.com/health and check it says `"warm": true` (new build) — the old build has no `warm` field.
   First visit after sleep takes 30–60 s; press Retry if the UI says it can't reach the engine.
2. **Warm the AI cache, after 10:00 Amman (Gemini reset), on a phone hotspot.** The venue network has a **FortiGate TLS
   interception on googleapis / groq**: AI calls fail there with certificate errors, so don't warm on the venue wifi.
   From `backend/`:
   1. `.venv/Scripts/python -m scripts.warm_cache --service everyday_travel --parse-only` (the 12 rehearsed fuel requests; 12 calls)
   2. `.venv/Scripts/python -m scripts.warm_cache --service everyday_travel` (~12 calls: fixes 1, hero voices 9, reports 2)
   3. optional: `.venv/Scripts/python -m scripts.find_ai_fix --service everyday_travel`, then step 2 again (the AI-fix voices and report)
   4. `.venv/Scripts/python -m scripts.warm_cache --service id_renewal` (Amina's voice after the AI fix; 1 call)
   5. `.venv/Scripts/python -m scripts.find_ai_fix --service medical_exemption` (up to 6 calls), then
      `.venv/Scripts/python -m scripts.warm_cache --service medical_exemption` (~28 calls: 12 parses, 1 fixes, 12 hero voices, 3 reports)
   6. `DEMO_OFFLINE=1 .venv/Scripts/python -m scripts.warm_cache` must end with **"No misses"** (or only what you chose to skip)
   7. `.venv/Scripts/python -m pytest -q` (today: 285 passed, 57 xfailed); warmed entries show as XPASS: drop the travel and
      exemption xfail marks in `tests/test_cache_hits.py` (`travel_pending` / `TRAVEL_PENDING`, `exemption_pending` /
      `EXEMPTION_PENDING`) and Amina from `PENDING_VOICES`
   8. `git add backend/cache backend/tests/test_cache_hits.py && git commit -m "Cache: travel and medical-exemption sectors + Amina's post-fix voice" && git push`, then redeploy Render.
   **Totals:** ID renewal 1 call, fuel ~24 (+ optional find_ai_fix), medical exemptions ~28 (+ up to 6): about 60 calls, so
   spread them over the model chains (Groq can do the parses). Until this runs, the fuel and medical-exemption sectors show
   template voices, explanations and reports (labelled "template", never blank).
3. Open **https://nas-rbo5.onrender.com/?sector=id_renewal** in Arabic on the laptop you'll present with (`?sector=` skips the
   sector list), run the script below once, and **record a backup screen video** of that run. Then open `?sector=everyday_travel`
   and `?sector=medical_exemption` once each and click through their sections below.
4. Decide the connectivity mode (see "If the wifi is bad").

## The script (clicks in order)

| Time | Do | Say (the numbers on screen) |
|---|---|---|
| 0:00 | Baseline map on screen, Arabic UI (opened with `?sector=id_renewal`; without it the app shows the sector list first: click **تجديد الهوية**) | Every new policy in Jordan is tested on real people after launch. Nas reaches the people who fall through the cracks *before* the policy does. |
| 0:45 | Point at the synthetic badge; click **English** then back to **عربي** | 1,000 synthetic citizens of Amman, **AI-voiced**, anchored to published figures where we found them. Today: 88.4% served, 11.5% with hardship, 1 person left out. |
| 1:15 | Click preset **دمج المكاتب** (consolidate) | Keep only Tabarbour and Jabal Amman: served 85.0%, 36 people worse off. |
| 1:45 | Click the first example chip **خلّوا الكاونترات تسكر الساعة 1 الظهر، وما حدا يراجع المكتب إلا بموعد مسبق أونلاين** → "understood as" list → **حلّل / Apply** | The AI turned my sentence into a testable policy; the engine ran all 1,000 people. **79.6 / 19.5 / 0.9**: 93 people worse off, 9 left out, 195 in hardship. (If the parse fails: click preset **الدمج + التحول الرقمي**, same result.) |
| 2:30 | Click hero **دانا** (Dana) | 71, no car, no smartphone, her son helps. Today → policy: served → hardship. Read her voice. |
| 3:00 | Impact tab: equity bars | Elderly hardship 40% → 85%; offline residents 56% → 96%. These are the people who can't complain. |
| 3:30 | Click the robustness badge | "This ranking held in 6 of 6 runs when we moved our uncertain assumptions by ±20%." Click a row: every constant, its tag, its source. Close. |
| 4:15 | **اقترح حلول** (Suggest fixes) | Engine fixes appear instantly, verified: Saturday vans in Sweileh + Downtown: left out 9 → 1, hardship 195 → 90, 2 changes. Then the AI explains them and adds its own idea, also verified by the engine: three Saturday vans, hardship 195 → 76, 3 changes. |
| 5:00 | **طبّق الحل** on the AI card | Green returns: **92.3% served, 1 left out, 130 people better off**. |
| 5:20 | Click **دانا** again | Today → policy → after fix: served → hardship → **served**. Read the new voice. |
| 5:45 | (Optional, or save for Q&A) Protections panel: walk-in for elderly + disabled → served 81.6%; + 20 home visits → 83.6%, left out 0.5% | "Or keep the policy and protect people instead." |
| 5:45 | Slide: who pays, next steps, relatives' answers | Municipalities, ministries, digital-transformation programmes. Next: more services, more cities, better data. |
| 6:30 | Close | *Every policy leaves someone out. Nas shows you who, why, and how to fix it before you launch.* "Name a policy and we'll test it now." |

## Judge requests: all of these are cached (instant, work offline too)
Type them on the demo path (**الدمج + التحول الرقمي** selected), Arabic or English:
- اسكروا المكاتب يوم الخميس / Close all offices on Thursdays → **changes nobody** (say: "Nas doesn't model queues or capacity yet, so days are interchangeable; that's the next module").
- خلّوها مجانية لكبار السن / Make it free for people over 65 → fee effect only, no status change (hardship here comes from appointments and helpers, not cost).
- خلّوا كبار السن وذوي الإعاقة يراجعوا بدون موعد → served 79.6 → 81.6.
- زيارات منزلية لذوي الإعاقة، 30 زيارة / Home visits for people with disabilities, 30 visits → left out drops.
- ادفعوا أجرة التكسي لذوي الدخل المحدود لحد 3 دنانير · نص السعر لذوي الدخل المحدود / Half price for low-income families.
- ضيفوا وحدة متنقلة في ماركا يوم السبت / Add a Saturday mobile van in Marka · افتحوا مكتب جديد في ماركا.
- افتحوا المكاتب يوم السبت / Open the offices on Saturdays · خلّوا المكاتب مفتوحة لحد الساعة 7 المسا / Keep the offices open until 7 PM.
- رجّعوا كل المكاتب / Reopen all the offices · Reopen the Marka office · Close the Tabarbour office · Move the Jabal Amman office to Wehdat / انقلوا مكتب جبل عمان إلى الوحدات.
- Double the fee · Require two visits · Make it free for everyone · Let people apply online and just pick up the card.
- **Unsupported, answered honestly:** Add more staff at the Marka office · زيدوا الباصات / Add more buses · Make it free for pregnant women · سكّروا شارع زهران.
Anything else is parsed live (3–8 s). If the header chip says **AI resting**, say "the AI is rate-limited, so I'll build it by hand" and use the panel.

## Fuel sector (optional, Q&A)
Use it when a judge says "name a policy" and there's time, or asks "only services?". The 7-minute script stays on ID renewal.
Numbers are engine output (`compare(travel_today, preset)`); statuses read **بخير / مضغوطون / عاجزون عن التنقل** (fine / squeezed / priced out).

| Do | Say (the numbers on screen) |
|---|---|
| Open `?sector=everyday_travel` (or the back button → **أسعار المحروقات**) | Same 1,000 synthetic citizens, each with one regular trip: work, university or a public hospital. Today: 72.2% fine, 17.8% squeezed, 10.0% priced out. Low-income daily bus commuters already spend about 30% of their income on the trip. |
| (optional) Preset **رفع الوقود 5%** | This month's real rise, +5 piasters a litre (≈ +5%): 7 people worse off, all drivers: fares are regulated and lag fuel. |
| Preset **رفع الوقود 25% مع رفع الأجور** (`fuel_plus_25_fares`) | Fuel +25% and bus and taxi fares +25%, as after 2012: **70.2 / 14.6 / 15.2**, 72 people worse off, 4.54 JD a month extra on average. Hit hardest: workers, offline, low income. |
| Click **مصطفى** (Mustafa) | 23, low income, two buses to Wehdat every workday: 39 → 48.7 JD a month, 30% → 37.5% of his income. He was priced out before the rise. |
| Click **عيسى** (Issa) | 29, middle income, drives 44 minutes to King Hussein Business Park: 61.5 → 70.7 JD, 17.6% → 20.2%: squeezed → priced out. |
| **اقترح حلول** (Suggest fixes) | Engine fix, verified: **14 JD a month for people without a car + freeze bus fares**: priced out 152 → 80 people (−7.2 points). The fix never touches the fuel price: that's the decision being tested. |
| Robustness badge | Ranking held **5 of 6**: workers are first in every run; second place changes when "squeezed" starts at 12% instead of 10% (no_car instead of offline). We show it, we don't retune it. |
| **طبّق الحل** on the top fix | Mustafa recovers to squeezed (25 JD, 19.2%). **Click Issa: still priced out.** Say it: "Cash for riders doesn't reach a middle-income driver. Nas shows you who the fix still misses." |
| (if asked) Policy panel: cash support for **workers** 14 JD, or the third fix card | Freeze bus fares + 14 JD for workers brings Issa back to squeezed (56.7 JD, 16.2%), at −6.8 points instead of −7.2. |

**Rehearsed fuel requests** (`demo_requests.json`; instant and offline **only once the morning warm run is done**, step 2;
before that they parse live in 3-8 s): ارفعوا سعر البنزين 10% / Raise petrol prices by 10% (on today's prices) ·
ارفعوا الوقود 25% وأعطوا الأسر ذات الدخل المحدود 14 ديناراً شهرياً / Raise fuel by 25% but give low-income families 14 dinars a month ·
on the demo preset: جمّدوا أجور الباصات / Freeze bus fares · ادفعوا أجرة الباص للطلاب / Pay the bus fare for students · Give every worker 20 dinars a month ·
**unsupported, answered honestly:** خفّضوا سعر الكهرباء / Lower electricity prices · Raise diesel only (one fuel price change only).

Fuel answers: **"Why are the first people hurt all drivers?"** Fares are regulated and follow fuel only partly, and the riders
were already squeezed (≈30% of income). **"Are the prices real?"** October 2026's prices (90-octane 1.050 JD/L, +0.05) and the
National Aid Fund's 8-14 JD fuel support are from press reports (CITED); the 7 travel constants are labelled assumptions,
committed before any travel scenario ran. **"Do people switch to the bus?"** Not modelled yet: the next module.

## Medical exemptions (optional, Q&A)
Use it when a judge asks about health, "only services?", or "who does going digital leave out?". The 7-minute script stays
on ID renewal. Numbers are engine output (`compare(exemption_today, preset)`), **percentages of the 441 uninsured only**:
insured residents are the lighter dots ("Insured: not applicable"). Status words are ID renewal's.

| Do | Say (the numbers on screen) |
|---|---|
| Open `?sector=medical_exemption` (or the back button → **الإعفاءات الطبية**) | Same 1,000 synthetic citizens; the 441 without health insurance apply for a Royal Court medical exemption. Today: one office in Downtown, two visits, no online channel: **0.0% served, 74.8% hardship, 25.2% left out**. Two visits of about two hours already reach our hardship line: today's process is a hardship for everyone who needs it. |
| Preset **عبر سند فقط** (`exemption_online_only`, Sanad only) | Applications only through Sanad: **77.6 / 14.1 / 8.4**. **364 people better off.** But **30 worse off, all offline residents with nobody to apply for them**: they lose the counter (offline left out 29.3% → 37.4%). Hit hardest: offline, elderly. |
| Click **سلمى** (Salma) | 72, Wehdat, no car, can't use the app alone, nobody to help: today hardship → Sanad only **left out**. Read her voice. |
| Robustness badge | Ranking held **6 of 6** at ±20%. |
| **اقترح حلول** (Suggest fixes) | Engine fix, verified: **exemption intake at the 7 Civil Status offices + a Saturday mobile intake day in Downtown**: left out 37 → 1 person (8.4% → 0.2%). Hardship rises (14.1% → 22.2%) because the people brought back still travel. |
| **طبّق الحل** on the top fix, click **سلمى** again | Today → policy → after fix: hardship → left out → **hardship**: she reaches the Saturday intake day by bus. (Ali, 77 in Marka, comes back through the Marka intake point.) |
| (if asked) Preset **سند ثم استلام الكتاب** (`exemption_hybrid`) | Keep the office and add Sanad with one short visit to collect: 77.6 / 20.9 / 1.6, nobody worse off. |

**Rehearsed exemption requests** (`demo_requests.json`; instant and offline **only once the morning warm run is done**, step 5;
before that they parse live in 3-8 s): on **الوضع الحالي** (today): خلّوا الأقارب يقدّموا بدل المريض (already allowed today) ·
The patient must come in person (= no change in outcomes: relatives work the same hours) · افتحوا استقبال الطلبات في مكاتب الأحوال المدنية ·
Accept applications only through Sanad · خلّوا الناس يقدّموا على سند ويستلموا الكتاب بالمكتب · Add a mobile intake day in Marka on Saturday ·
زيارات منزلية لذوي الإعاقة، 30 زيارة; on **عبر سند فقط**: خلّوا كبار السن يقدّموا بالمكتب / Open the office for people without a smartphone
(both reopen the office **for everyone**: Nas can't limit an office to one group, and the "understood as" list says so);
**unsupported, answered honestly:** Make everyone insured · ارفعوا قيمة الإعفاء · Add more doctors to the committee.

Exemption answers: **"Why is nobody served today?"** Two visits of about two hours each at one office already reach our
hardship line (half a working day); both constants were frozen before any exemption scenario ran and are moved ±20% in the
robustness check. **"So Sanad is good?"** For 364 people, yes; the 30 it leaves out are the point, and the engine finds the
mix that reaches them. **"Does letting a relative apply matter?"** Rarely here: relatives work the same Sun-Thu hours and are
free from 16:00, after the office closes; the switch is there to test a Saturday or evening intake day. **"Is 44% uninsured
real?"** The DoS 2015 census paper: 44.8% of Amman's Jordanians uninsured (all ages, ANCHORED); our 441 of 1,000 (44.1%) come
from income-band rates calibrated to it (an assumption). The process (medical report, doctor's review, return visit) is from
press reports; the hours and queue time are labelled assumptions.

## Answers to have ready
- **Real people?** No. A labelled synthetic population; anchored where we could (MoDEE 2024: 95.6% internet use, 99% smartphone households, 38.1% e-gov use; the 7 real CSPD offices; OSRM road times). Everything else is a labelled assumption. README has the full "what is real, what is assumed" list.
- **Did you tune it?** Assumptions were frozen before any scenario ran, all 26 are labelled, and the ranking holds 6/6 at ±20%. When a story didn't appear we changed the scenario, never the constants.
- **Is the AI making things up?** The engine computes every number. A grounding check rejects AI text with a number the engine didn't produce; every AI fix is re-run by the engine before it's shown; the badge says which fixes are engine-searched and which are AI-proposed.
- **Three vans beat two, of course.** Yes: the AI fix costs 3 changes vs 2, and the card says so. Its value is finding the *third area* (Wehdat) that the grid pairs didn't reach.
- **Why doesn't closing Thursdays change anything?** No capacity or queue model yet: the next module.
- **What is "disabled" / "low income" here?** Disabled = limited mobility or wheelchair (69 people), not the 10.4% survey rate. Low income = bottom 30% of synthetic income, not the 8.3% poverty rate. (Glossary: the "i" next to the equity bars.)
- **Business model?** SaaS per service and municipality plus a calibration engagement. CPU-only engine, cached AI: cheap to run.

## If the wifi is bad
- **No internet at all:** run locally from `backend/` with `DEMO_OFFLINE=1` in `.env` (`.venv/Scripts/python -m uvicorn app.main:app --port 8000`) and open `http://localhost:8000/?offline=1`. Fonts, icons and the map library are vendored; the map shows labelled zones instead of tiles; every cached answer works; anything new gets an honest template.
- **Slow internet:** use the local server without `DEMO_OFFLINE` (AI calls still work) and `?offline=1` to skip map tiles.
- **Render asleep:** open the URL 5 minutes before you're called.

## Known and accepted
- Amina's voice after the **AI fix** is a template until the morning warm run (step 2). The demo reads Dana's.
- The fuel sector's voices, fix explanations and reports are templates until the travel warm run (step 2); its robustness is 5/6, not 6/6 (say why).
- The medical-exemption sector's voices, fix explanations and reports are templates until its warm run (step 5), and no AI fix is
  shown until `find_ai_fix --service medical_exemption` has found one.
- Medical exemptions: the Royal Court unit's coordinates are approximate (±1 km, Raghadan) and its hours (08:00-15:00 Sun-Thu)
  are assumed; "patient must come in person" changes nobody (relatives work the same hours). Both are said, not hidden.
- The fuel map shows citizens only: no pins for workplaces, universities or hospitals.
- Fix titles show Arabic-Indic digits (٩–٢); changing them would invalidate the cached AI fix.
- Three engine refinements are on hold so the rehearsed numbers stay exact (HANDOFF §14).
