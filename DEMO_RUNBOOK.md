# Nas demo runbook (Day 2, 7 min + 3 min Q&A)

Everything below was verified on the 2026-10-10 build. Numbers are exact engine output; say them as they are.

## Morning checklist (before slides)
1. **Deploy Render by hand** (dashboard → Manual Deploy → latest commit). Auto-deploy does not fire. Then open
   https://nas-rbo5.onrender.com/health and check it says `"warm": true` (new build) — the old build has no `warm` field.
   First visit after sleep takes 30–60 s; press Retry if the UI says it can't reach the engine.
2. **After 10:00 Amman (Gemini reset)**, from `backend/`:
   `.venv/Scripts/python -m scripts.warm_cache` (fills Amina's voice after the AI fix; 1 call), then
   `DEMO_OFFLINE=1 .venv/Scripts/python -m scripts.warm_cache` must end with **"No misses"**, then `pytest -q`, then
   `git add backend/cache && git commit -m "Cache: Amina's post-fix voice" && git push`, then redeploy Render.
3. Open the production URL in Arabic on the laptop you'll present with, run the script below once, and **record a backup
   screen video** of that run.
4. Decide the connectivity mode (see "If the wifi is bad").

## The script (clicks in order)

| Time | Do | Say (the numbers on screen) |
|---|---|---|
| 0:00 | Baseline map on screen, Arabic UI | Every new policy in Jordan is tested on real people after launch. Nas reaches the people who fall through the cracks *before* the policy does. |
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
- Fix titles show Arabic-Indic digits (٩–٢); changing them would invalidate the cached AI fix.
- Three engine refinements are on hold so the rehearsed numbers stay exact (HANDOFF §14).
