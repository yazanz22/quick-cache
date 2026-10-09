/* Nas frontend: UI only. Every number comes from the backend through api.js (CLAUDE.md §7).
   Strings come from i18n.js. Nothing here simulates, scores or ranks. */
(function () {
  "use strict";
  const API = window.NasAPI, DICT = window.NasI18n, CFG = window.NAS_CONFIG;
  const DAYS = ["sat", "sun", "mon", "tue", "wed", "thu", "fri"];
  const GROUP_ORDER = ["elderly", "disabled", "no_car", "offline", "low_income", "worker", "student"];
  const REASON_ICON = { TOO_FAR: "ph-map-pin-line", NO_TRANSPORT: "ph-bus", HOURS_CONFLICT_WORK: "ph-clock-countdown", NO_SMARTPHONE: "ph-device-mobile-slash", LOW_DIGITAL_LITERACY: "ph-cursor-click", NOT_WHEELCHAIR_ACCESSIBLE: "ph-wheelchair", TOO_EXPENSIVE: "ph-coins", OFFICE_CLOSED_ON_AVAILABLE_DAYS: "ph-calendar-x" };
  const MODE_ICON = { car: "ph-car-profile", helper_car: "ph-car-profile", bus: "ph-bus", taxi: "ph-taxi", online: "ph-globe-simple" };

  const $ = function (id) { return document.getElementById(id); };
  const esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (m) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]; }); };
  const f1 = function (x) { return (Math.round((+x || 0) * 10) / 10).toFixed(1); };
  const clone = function (x) { return JSON.parse(JSON.stringify(x)); };
  // Key-order-independent equality, so a backend that reorders JSON keys still matches presets.
  const canon = function (x) { return JSON.stringify(x, function (k, v) { return v && typeof v === "object" && !Array.isArray(v) ? Object.keys(v).sort().reduce(function (o, kk) { o[kk] = v[kk]; return o; }, {}) : v; }); };
  const same = function (a, b) { return canon(a) === canon(b); };
  const store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
  };
  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const sleep = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };

  /* ---------------- state ---------------- */
  const S = {
    lang: store.get("nas.lang") === "en" ? "en" : "ar",
    theme: store.get("nas.theme"),
    // reference data (GET)
    pop: [], byId: new Map(), sites: {}, areas: {}, scenarios: [], assumptions: [], heroes: [],
    baseline: null, policy: null, preset: null,
    prePolicy: null, preKpis: null, appliedFix: null,
    view: "after", reason: null, sel: null, tab: "impact",
    text: "", parse: null,
    cmp: null, cmpFix: null, busy: false,
    fixes: null, sens: null, voices: new Map(),
  };

  function t(k, vars) {
    let s = (DICT[S.lang] && DICT[S.lang][k]) || DICT.en[k] || k;
    if (vars) Object.keys(vars).forEach(function (v) { s = s.split("{" + v + "}").join(vars[v]); });
    return s;
  }
  const loc = function (o, base) { return o ? (o[base + "_" + S.lang] || o[base + "_" + (S.lang === "ar" ? "en" : "ar")] || "") : ""; };
  const areaName = function (k) { return S.areas[k] ? loc(S.areas[k], "name") : k; };
  const siteName = function (id) { return S.sites[id] ? loc(S.sites[id], "name") : id; };
  const dayName = function (d) { return t("day_" + d); };
  const shortDay = function (d) { return S.lang === "ar" ? dayName(d).replace("ال", "").slice(0, 3) : dayName(d).slice(0, 2); };
  const name = function (c) { return (S.lang === "ar" ? c.name_ar : c.name_en) || c.name_ar || c.name_en || c.id; };
  const initial = function (c) { return name(c).replace(/^(أم |أبو |Um |Abu )/, "").charAt(0); };
  const groupLabel = function (g) { return DICT[S.lang]["g_" + g] ? t("g_" + g) : g; };
  const scenarioName = function (sc) { return loc(sc, "name") || (DICT.en["preset_" + sc.id] ? t("preset_" + sc.id) : sc.id); };
  const scenarioPolicy = function () { return S.appliedFix ? S.prePolicy : S.policy; };
  const changed = function () { return S.baseline && S.policy && !same(S.policy, S.baseline); };

  /* ---------------- errors ---------------- */
  let toastTimer = null;
  function toast(err, retry) {
    const msg = err && err.message ? err.message : String(err);
    const el = $("toast");
    el.innerHTML = '<i class="ph-fill ph-warning-circle"></i><span>' + esc(t("request_failed", { msg: msg })) + "</span>" + (retry ? '<button id="toastRetry">' + t("retry") + "</button>" : "");
    el.hidden = false;
    toast.retry = retry || null;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.hidden = true; }, 7000);
  }

  /* ---------------- boot ---------------- */
  function bootScreen(state, err) {
    const b = $("boot");
    if (state === "done") { b.hidden = true; return; }
    b.hidden = false;
    if (state === "loading") b.innerHTML = '<div class="boot-card"><h2><span class="mark" aria-hidden="true" style="width:30px;height:30px;font-size:13px">ناس</span>' + t("loading") + '</h2><div class="bar-load"><i></i></div></div>';
    else b.innerHTML = '<div class="boot-card"><h2><i class="ph-fill ph-plugs" style="color:var(--left)"></i>' + esc(t("backend_down", { url: API.base })) + "</h2><p>" + t("backend_hint") + "</p>" +
      (err ? "<p><code>" + esc(err.path || "") + " " + esc(err.message) + "</code></p>" : "") +
      '<div><button class="btn accent" id="bootRetry"><i class="ph ph-arrow-clockwise"></i>' + t("retry") + '</button> <button class="btn ghost" id="langBtn2">' + t("lang_other") + "</button></div></div>";
  }

  async function boot() {
    renderStatic();
    bootScreen("loading");
    try {
      const opt = function (p, fb) { return p.catch(function (e) { if (e.status === 404 || e.status === 405) return fb; throw e; }); };
      const r = await Promise.all([API.population(), API.sites(), API.scenarios(), opt(API.assumptions(), []), opt(API.areas(), null), opt(API.heroes(), null)]);
      S.pop = r[0]; S.byId = new Map(S.pop.map(function (c) { return [c.id, c]; }));
      S.sites = r[1]; S.scenarios = r[2]; S.assumptions = r[3];
      S.areas = r[4] && Object.keys(r[4]).length ? r[4] : CFG.AREAS;
      S.heroes = (r[5] && r[5].length ? r[5] : CFG.HERO_IDS.map(function (id) { return { id: id }; })).filter(function (h) { return S.byId.has(h.id); });
      if (!S.scenarios.length) throw new API.ApiError("no scenarios", 0, "/scenarios");
      const base = S.scenarios.find(function (s) { return s.id === "baseline"; }) || S.scenarios[0];
      S.baseline = clone(base.policy); S.policy = clone(base.policy);
      initMap();
      await recompute();
      if (!S.cmp) throw new API.ApiError("compare failed", 0, "/compare");
      bootScreen("done");
    } catch (e) {
      console.error(e);
      bootScreen("error", e);
    }
  }

  /* ---------------- compare ---------------- */
  let cmpSeq = 0, cmpTimer = null;
  function scheduleCompare(delay) {
    clearTimeout(cmpTimer);
    cmpTimer = setTimeout(recompute, delay == null ? CFG.COMPARE_DEBOUNCE_MS : delay);
  }
  async function recompute() {
    const seq = ++cmpSeq;
    S.busy = true; renderBusy();
    S.preset = (S.scenarios.find(function (s) { return same(s.policy, S.policy); }) || {}).id || null;
    try {
      const jobs = [API.compare(S.baseline, S.policy)];
      if (S.appliedFix) jobs.push(API.compare(S.prePolicy, S.policy));
      const r = await Promise.all(jobs);
      if (seq !== cmpSeq) return;
      S.cmp = r[0]; S.cmpFix = r[1] || null;
    } catch (e) {
      if (seq !== cmpSeq) return;
      toast(e, recompute);
    } finally {
      if (seq === cmpSeq) { S.busy = false; renderBusy(); }
    }
    if (seq !== cmpSeq || !S.cmp) return;
    scheduleSensitivity();
    renderAll();
    loadVoice(); // the open citizen's outcome may have changed
  }

  function edit(mutator, opts) {
    mutator(S.policy);
    S.appliedFix = null; S.prePolicy = null; S.preKpis = null; S.fixes = null; S.sens = null;
    if (S.tab === "fixes") S.tab = "impact";
    renderPolicy(); renderSteps();
    scheduleCompare(opts && opts.now ? 0 : undefined);
  }

  function loadPreset(id) {
    const sc = S.scenarios.find(function (s) { return s.id === id; });
    if (!sc) return;
    S.policy = clone(sc.policy);
    S.appliedFix = null; S.prePolicy = null; S.preKpis = null; S.fixes = null; S.sens = null; S.parse = null; S.reason = null;
    if (S.tab === "fixes") S.tab = "impact";
    renderPolicy(); renderSteps();
    scheduleCompare(0);
  }

  /* ---------------- robustness ---------------- */
  let sensSeq = 0, sensTimer = null;
  function scheduleSensitivity() {
    clearTimeout(sensTimer);
    if (!changed()) { S.sens = null; return; }
    const fix = S.appliedFix || (S.fixes && S.fixes.list && S.fixes.list[0]) || null;
    const key = canon([scenarioPolicy(), fix && fix.policy]);
    if (S.sens && S.sens.key === key && S.sens.status !== "error") return;
    // The contract takes a fix. Until fixes exist, try without one and accept a refusal.
    S.sens = { status: "checking", key: key };
    const seq = ++sensSeq;
    sensTimer = setTimeout(async function () {
      try {
        const res = await API.sensitivity(S.baseline, scenarioPolicy(), fix);
        if (seq === sensSeq) S.sens = { status: "done", key: key, res: res, hasFix: !!fix };
      } catch (e) {
        if (seq === sensSeq) S.sens = { status: fix ? "error" : "needs_fix", key: key };
      }
      if (seq === sensSeq) renderImpact();
    }, 250);
  }

  /* ---------------- local text fallbacks (only when /citizen/voice fails) ---------------- */
  function fallbackVoiceAr(c, o) {
    const R = new Set(o.reasons || []), h = c.helper_relation_ar;
    const offline = !c.has_smartphone ? "ما عندي هاتف ذكي" : "ما بعرف أتعامل مع التطبيقات";
    if (o.status === "left_out") {
      const p = [];
      if (R.has("NO_SMARTPHONE") || R.has("LOW_DIGITAL_LITERACY")) p.push(offline);
      if (R.has("NOT_WHEELCHAIR_ACCESSIBLE")) p.push("المبنى ما فيه مدخل للكرسي");
      if (R.has("TOO_FAR")) p.push("المكتب بعيد عليّ كثير");
      if (R.has("TOO_EXPENSIVE")) p.push("التكسي أكثر من طاقتي");
      if (R.has("HOURS_CONFLICT_WORK")) p.push("المكتب بسكّر وأنا بالشغل");
      if (R.has("OFFICE_CLOSED_ON_AVAILABLE_DAYS")) p.push("المكتب مسكّر بالأيام اللي بقدر فيها");
      if (R.has("NO_TRANSPORT") && p.length < 2) p.push("ما في إشي يوصلني");
      return "ما قدرت أخلّص المعاملة. " + p.slice(0, 3).join("، و") + ".";
    }
    if (o.mode === "online") return o.status === "hardship" && h ? offline + "، ف" + h + " بخلّصلي ياها أونلاين." : "خلّصتها أونلاين من البيت.";
    const ch = o.channel_name_ar || "", day = o.visit_day ? t("day_" + o.visit_day) : "";
    const lead = o.status === "served" ? "خلّصتها " : "خلّصتها بس بتعب: ";
    return lead + (ch ? "ب" + ch + " " : "") + (day ? "يوم " + DICT.ar["day_" + o.visit_day] : "") + "، وأخذت " + f1(o.hours_lost) + " ساعة و" + f1(o.cost_jd) + " دينار.";
  }
  // English one-liner under the Arabic bubble. Template only, no AI call (CLAUDE.md §8.2).
  function summaryEn(c, o) {
    const R = new Set(o.reasons || []);
    if (o.status === "left_out") {
      const why = [];
      if (R.has("NO_SMARTPHONE") || R.has("LOW_DIGITAL_LITERACY")) why.push(c.has_smartphone ? "can't use apps" : "no smartphone");
      if (R.has("NOT_WHEELCHAIR_ACCESSIBLE")) why.push("building not accessible");
      if (R.has("TOO_FAR")) why.push("too far");
      if (R.has("TOO_EXPENSIVE")) why.push("taxi unaffordable");
      if (R.has("HOURS_CONFLICT_WORK")) why.push("office closes during work");
      if (R.has("OFFICE_CLOSED_ON_AVAILABLE_DAYS")) why.push("closed on their free days");
      if (R.has("NO_TRANSPORT") && why.length < 2) why.push("no transport");
      return "Left out: " + why.slice(0, 3).join(", ") + ".";
    }
    if (o.mode === "online") return o.status === "hardship" ? "Hardship: done online with help from " + (c.helper_relation_en || "a helper") + "." : "Served: done online from home.";
    const m = o.mode === "bus" ? ((o.bus_transfers || 0) + 1) + " bus" + ((o.bus_transfers || 0) ? "es" : "") + ", " + Math.round(o.travel_minutes) + " min each way" : (DICT.en["m_" + o.mode] || o.mode || "").toLowerCase();
    let s = (o.status === "served" ? "Served: " : "Hardship: ") + (o.channel_name_en || "") + (o.visit_day ? " on " + DICT.en["day_" + o.visit_day] : "") + (m ? ", " + m : "");
    if (o.work_hours_missed > 0) s += "; " + f1(o.work_hours_missed) + " h of work missed";
    return s + ". " + f1(o.hours_lost) + " h, " + f1(o.cost_jd) + " JD in total.";
  }

  /* ---------------- header ---------------- */
  function renderStatic() {
    document.documentElement.lang = S.lang;
    document.documentElement.dir = S.lang === "ar" ? "rtl" : "ltr";
    document.querySelectorAll("[data-t]").forEach(function (el) { el.textContent = t(el.getAttribute("data-t")); });
    document.querySelectorAll("[data-t-aria]").forEach(function (el) { el.setAttribute("aria-label", t(el.getAttribute("data-t-aria"))); });
    $("langBtn").textContent = t("lang_other");
    $("themeBtn").innerHTML = '<i class="ph ' + (currentDark() ? "ph-sun" : "ph-moon-stars") + '"></i>';
  }
  function renderBusy() { $("busy").hidden = !S.busy; }

  function renderSteps() {
    const cur = S.appliedFix ? "fix" : changed() ? "scenario" : "baseline";
    const items = [["baseline", "ph-house-line", "step_baseline"], ["scenario", "ph-scales", "step_scenario"], ["fix", "ph-check-circle", "step_fix"]];
    $("steps").innerHTML = items.map(function (it, i) {
      const dis = (it[0] === "scenario" && cur === "baseline") || (it[0] === "fix" && cur !== "fix");
      return (i ? '<i class="ph ph-caret-right step-sep" aria-hidden="true"></i>' : "") +
        '<button class="step" data-step="' + it[0] + '"' + (cur === it[0] ? ' aria-current="step"' : "") + (dis ? " disabled" : "") + '><i class="ph ' + it[1] + '"></i>' + t(it[2]) + "</button>";
    }).join("");
  }

  /* ---------------- policy panel ---------------- */
  function sw(id, on, label, dis) {
    return '<div class="switch-row"><span id="l_' + id + '">' + label + '</span><button class="switch" role="switch" aria-labelledby="l_' + id + '" data-sw="' + id + '" aria-checked="' + !!on + '"' + (dis ? " disabled" : "") + "></button></div>";
  }
  function areaOptions(sel) { return Object.keys(S.areas).map(function (k) { return '<option value="' + esc(k) + '"' + (k === sel ? " selected" : "") + ">" + esc(areaName(k)) + "</option>"; }).join(""); }
  function dayOptions(sel) { return DAYS.map(function (d) { return '<option value="' + d + '"' + (d === sel ? " selected" : "") + ">" + dayName(d) + "</option>"; }).join(""); }

  function renderPolicy() {
    const p = S.policy;
    let h = "";
    h += '<div class="sec"><h3 class="sec-title">' + t("presets") + '</h3><div class="presets">' +
      S.scenarios.map(function (sc) {
        const note = loc(sc, "note");
        return '<button class="preset" data-preset="' + esc(sc.id) + '" aria-pressed="' + (S.preset === sc.id) + '"><b>' + esc(scenarioName(sc)) + "</b>" + (note ? "<small>" + esc(note) + "</small>" : "<small></small>") + '<i class="ph ph-check tick" aria-hidden="true"></i></button>';
      }).join("") + "</div></div>";

    const ex = [1, 2, 3, 4].map(function (i) { return t("example_" + i); });
    h += '<div class="sec"><label class="sec-title" for="nl">' + t("describe") + '</label>' +
      '<textarea class="input" id="nl" rows="3" placeholder="' + esc(t("describe_ph")) + '">' + esc(S.text) + "</textarea>" +
      '<div class="examples">' + ex.map(function (e, i) { return '<button class="ex" data-ex="' + i + '" title="' + esc(e) + '">' + esc(e) + "</button>"; }).join("") + "</div>" +
      '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:10px"><p class="help" style="margin:0">' + t("describe_help") + '</p><button class="btn sm accent" id="parseBtn"' + (S.parse && S.parse.status === "loading" ? " disabled" : "") + '><i class="ph ph-sparkle"></i>' + t("parse") + "</button></div>" +
      renderParse() + "</div>";

    if (!p.online_only) {
      p.offices.forEach(function (o, i) {
        const days = DAYS.filter(function (d) { return o.schedule[d]; });
        const first = days.filter(function (d) { return d !== "thu"; })[0] || days[0];
        const hrs = first ? o.schedule[first] : ["08:00", "15:00"];
        const lateThu = o.schedule.thu && o.schedule.thu[1] === "19:00";
        h += '<div class="sec"><h3 class="sec-title"><span>' + t("office") + (p.offices.length > 1 ? " " + (i + 1) : "") + '</span><i class="ph ph-bank" aria-hidden="true"></i></h3>' +
          '<div class="field"><label class="label" for="site' + i + '">' + t("site") + '</label><select class="input" id="site' + i + '" data-site="' + i + '">' +
          Object.keys(S.sites).map(function (s) { return '<option value="' + esc(s) + '"' + (s === o.site_id ? " selected" : "") + ">" + esc(siteName(s)) + "</option>"; }).join("") +
          '</select><p class="help" style="margin:0">' + t("drag_hint") + "</p></div>" +
          '<div class="field"><span class="label">' + t("days") + '</span><div class="daychips">' +
          DAYS.map(function (d) { return '<button class="daychip" data-day="' + i + ":" + d + '" aria-pressed="' + !!o.schedule[d] + '" title="' + dayName(d) + '">' + shortDay(d) + "</button>"; }).join("") + "</div></div>" +
          '<div class="row2 field"><div class="field" style="margin:0"><label class="label" for="op' + i + '">' + t("opens") + '</label><input class="input num" type="time" step="1800" id="op' + i + '" data-open="' + i + '" value="' + hrs[0] + '"></div>' +
          '<div class="field" style="margin:0"><label class="label" for="cl' + i + '">' + t("closes") + '</label><input class="input num" type="time" step="1800" id="cl' + i + '" data-close="' + i + '" value="' + hrs[1] + '"></div></div>' +
          sw("late:" + i, lateThu, t("late_thu"), !o.schedule.thu) + sw("acc:" + i, o.wheelchair_accessible !== false, t("accessible")) + "</div>";
      });
    }

    h += '<div class="sec"><h3 class="sec-title">' + t("rules") + "</h3>" +
      sw("online", p.online_enabled, t("online_enabled"), p.online_only) + sw("onlineOnly", p.online_only, t("online_only")) + sw("appt", p.appointment_required, t("appointment"), p.online_only) + "</div>";

    const units = p.mobile_units || [];
    h += '<div class="sec"><h3 class="sec-title"><span>' + t("mobile_units") + '</span><button class="btn sm ghost" id="addUnit"' + (p.online_only ? " disabled" : "") + '><i class="ph ph-plus"></i>' + t("add_unit") + "</button></h3>" +
      (units.length ? units.map(function (u, i) {
        return '<div class="unit"><select class="input" data-u="' + i + ':area" aria-label="' + t("area") + '">' + areaOptions(u.area) + '</select><select class="input" data-u="' + i + ':day" aria-label="' + t("day") + '">' + dayOptions(u.day) + "</select>" +
          '<button class="x" data-urm="' + i + '" aria-label="' + t("remove") + '"><i class="ph ph-trash"></i></button>' +
          '<div class="hours"><input class="input num" type="time" step="1800" data-u="' + i + ':open" value="' + u.open + '" aria-label="' + t("opens") + '"><input class="input num" type="time" step="1800" data-u="' + i + ':close" value="' + u.close + '" aria-label="' + t("closes") + '"></div></div>';
      }).join("") : '<div class="empty">' + t("no_units") + "</div>") + "</div>";

    h += '<div class="sec"><div class="row2"><div class="field" style="margin:0"><span class="label">' + t("fee") + '</span><div class="stepper"><button data-fee="-0.5" aria-label="-">−</button><output class="num">' + p.fee_jd + '</output><button data-fee="0.5" aria-label="+">+</button></div></div>' +
      '<div class="field" style="margin:0"><span class="label">' + t("visits") + '</span><div class="stepper"><button data-visits="-1" aria-label="-">−</button><output class="num">' + p.visits_required + '</output><button data-visits="1" aria-label="+">+</button></div></div></div></div>';
    h += '<p class="footnote">' + t("prototype_note") + "</p>";

    const el = $("policyPanel"), sc = el.scrollTop;
    const focusId = document.activeElement && document.activeElement.id;
    el.innerHTML = h; el.scrollTop = sc;
    if (focusId === "nl") { const nl = $("nl"); nl.focus(); nl.setSelectionRange(nl.value.length, nl.value.length); }
  }

  function renderParse() {
    const P = S.parse;
    if (!P) return "";
    if (P.status === "loading") return '<div class="parse"><h4><i class="ph ph-sparkle"></i>' + t("parsing") + '</h4><div class="skel"></div><div class="skel w60"></div></div>';
    if (P.status === "unsupported") return '<div class="parse bad"><h4><i class="ph ph-info"></i>' + t("unsupported") + "</h4><p>" + esc(loc(P, "message")) + '</p><div class="acts"><button class="btn sm ghost" data-parse="cancel">' + t("close") + "</button></div></div>";
    if (P.status !== "ok" || !P.policy) return '<div class="parse bad"><h4><i class="ph ph-question"></i>' + t("not_understood") + '</h4><div class="acts"><button class="btn sm ghost" data-parse="cancel">' + t("close") + "</button></div></div>";
    const list = P["changes_" + S.lang] || P.changes_ar || P.changes_en || [];
    return '<div class="parse"><h4><i class="ph ph-list-checks"></i>' + t("understood") + "</h4><ul>" + list.map(function (c) { return "<li>" + esc(c) + "</li>"; }).join("") +
      '</ul><div class="acts"><button class="btn sm accent" data-parse="apply"><i class="ph ph-check"></i>' + t("apply") + '</button><button class="btn sm ghost" data-parse="cancel">' + t("cancel") + "</button></div></div>";
  }

  async function runParse() {
    const txt = ($("nl") && $("nl").value || S.text || "").trim();
    S.text = txt;
    if (!txt) return;
    S.parse = { status: "loading" }; renderPolicy();
    try { S.parse = await API.parse(txt, S.policy, S.lang); }
    catch (e) { S.parse = { status: "fail" }; toast(e); }
    renderPolicy();
  }

  /* ---------------- map ---------------- */
  let map, tiles, zoom, dotLayer, ringLayer, pinLayer, labelLayer, siteLayer, areaLayer;
  const dots = new Map();
  function currentDark() {
    if (S.theme) return S.theme === "dark";
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }
  function setTiles() {
    if (!map || CFG.OFFLINE_MAP) return;
    if (tiles) map.removeLayer(tiles);
    tiles = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' });
    tiles.on("tileerror", function () { const n = $("mapNote"); if (n.hidden) { n.hidden = false; n.textContent = t("offline_tiles"); } });
    tiles.addTo(map);
  }
  function initMap() {
    if (map) return;
    map = L.map("map", { zoomControl: false, attributionControl: true, minZoom: 10, maxZoom: 17 });
    const pts = S.pop.filter(function (c) { return isFinite(c.lat) && isFinite(c.lng); }).map(function (c) { return [c.lat, c.lng]; });
    if (pts.length) map.fitBounds(L.latLngBounds(pts), { paddingTopLeft: [10, 70], paddingBottomRight: [10, 90], maxZoom: 14 });
    else map.setView([31.975, 35.91], 12);
    setTiles();
    const r = L.svg({ padding: 0.4 });
    areaLayer = L.layerGroup().addTo(map);
    siteLayer = L.layerGroup().addTo(map);
    labelLayer = L.layerGroup().addTo(map);
    dotLayer = L.layerGroup().addTo(map);
    ringLayer = L.layerGroup().addTo(map);
    pinLayer = L.layerGroup().addTo(map);
    if (CFG.OFFLINE_MAP) Object.keys(S.areas).forEach(function (k) { const a = S.areas[k]; L.circle([a.lat, a.lng], { radius: 1600, className: "area-zone", interactive: false, renderer: r }).addTo(areaLayer); });
    const heroIds = new Set(S.heroes.map(function (h) { return h.id; }));
    S.pop.forEach(function (c) {
      const hero = heroIds.has(c.id);
      const m = L.circleMarker([c.lat, c.lng], { radius: hero ? 7 : 4, weight: hero ? 2.5 : 0.8, opacity: 1, fillOpacity: 0.92, className: "dot served", renderer: r, bubblingMouseEvents: false });
      m.on("click", function () { select(c.id); });
      m.addTo(dotLayer); dots.set(c.id, m);
    });
    Object.keys(S.sites).forEach(function (k) {
      const s = S.sites[k];
      L.marker([s.lat, s.lng], { icon: L.divIcon({ className: "", html: '<div class="site-mark"></div>', iconSize: [12, 12], iconAnchor: [6, 6] }), interactive: false, keyboard: false }).addTo(siteLayer);
    });
    renderLabels(); placeZoom();
  }
  function placeZoom() {
    if (!map) return;
    if (zoom) map.removeControl(zoom);
    zoom = L.control.zoom({ position: S.lang === "ar" ? "bottomleft" : "bottomright", zoomInTitle: "+", zoomOutTitle: "-" }).addTo(map);
  }
  // Area labels sit just north of each area's residents.
  function renderLabels() {
    if (!labelLayer) return;
    labelLayer.clearLayers();
    Object.keys(S.areas).forEach(function (k) {
      const a = S.areas[k];
      const mine = S.pop.filter(function (c) { return c.area === k; });
      const top = mine.length ? Math.max.apply(null, mine.map(function (c) { return c.lat; })) + 0.0025 : a.lat + 0.012;
      L.marker([top, a.lng], { icon: L.divIcon({ className: "", html: '<div class="area-label" style="transform:translate(-50%,-50%)">' + esc(areaName(k)) + "</div>", iconSize: [0, 0] }), interactive: false, keyboard: false }).addTo(labelLayer);
    });
  }

  const viewSim = function () { return S.view === "before" ? S.cmp.baseline : S.cmp.scenario; };
  const viewPolicy = function () { return S.view === "before" ? S.baseline : S.policy; };

  function updateMap() {
    if (!S.cmp) return;
    const sim = viewSim();
    S.pop.forEach(function (c) {
      const o = sim.byId.get(c.id), m = dots.get(c.id);
      if (!o || !m) return;
      let cls = "dot " + o.status;
      if (S.reason && !(o.status === "left_out" && (o.reasons || []).indexOf(S.reason) >= 0)) cls += " dim";
      if (S.sel === c.id) cls += " sel";
      if (m._path) m._path.setAttribute("class", cls + " leaflet-interactive");
    });
    ringLayer.clearLayers();
    if (S.view === "after" && !S.reason) {
      const rr = L.svg({ padding: 0.4 });
      const ids = S.cmpFix ? S.cmpFix.flipped_better : S.cmp.flipped_worse;
      ids.forEach(function (id) {
        const c = S.byId.get(id); if (!c) return;
        L.circleMarker([c.lat, c.lng], { radius: S.cmpFix ? 7 : 6, opacity: 1, fill: false, className: S.cmpFix ? "ring better" : "ring", interactive: false, renderer: rr }).addTo(ringLayer);
      });
    }
    pinLayer.clearLayers();
    const p = viewPolicy(), editable = S.view === "after";
    if (p.online_only) return;
    p.offices.forEach(function (o, i) {
      const s = S.sites[o.site_id]; if (!s) return;
      const m = L.marker([s.lat, s.lng], { draggable: editable, autoPan: true, zIndexOffset: 1000, title: siteName(o.site_id),
        icon: L.divIcon({ className: "", html: '<div class="pin' + (pinLayer._snap === i ? " snap" : "") + '"><div class="head"><i class="ph-fill ph-bank"></i></div></div>', iconSize: [40, 48], iconAnchor: [20, 48] }) });
      m.on("dragend", function () {
        const ll = m.getLatLng(); let best = null, bd = Infinity;
        Object.keys(S.sites).forEach(function (k) { const ss = S.sites[k], d = (ss.lat - ll.lat) ** 2 + ((ss.lng - ll.lng) * Math.cos(ll.lat * Math.PI / 180)) ** 2; if (d < bd) { bd = d; best = k; } });
        pinLayer._snap = i;
        m.setLatLng([S.sites[best].lat, S.sites[best].lng]);
        edit(function (pp) { snapOffice(pp.offices[i], best); });
      });
      m.addTo(pinLayer);
    });
    pinLayer._snap = null;
    (p.mobile_units || []).forEach(function (u, i) {
      const a = S.areas[u.area]; if (!a) return;
      const n = p.mobile_units.slice(0, i).filter(function (x) { return x.area === u.area; }).length;
      L.marker([a.lat - 0.0045, a.lng + 0.004 + n * 0.004], { zIndexOffset: 900, keyboard: false,
        icon: L.divIcon({ className: "", html: '<div class="van"><i class="ph-fill ph-van"></i></div>', iconSize: [34, 34], iconAnchor: [17, 17] }) })
        .bindTooltip(esc(areaName(u.area)) + ", " + dayName(u.day) + " " + u.open + "-" + u.close, { direction: "top", offset: [0, -16] }).addTo(pinLayer);
    });
  }
  // Pins snap to sites; the office keeps the site's names so cache keys stay stable (CLAUDE.md §6).
  function snapOffice(o, siteId) {
    const s = S.sites[siteId];
    o.site_id = siteId;
    if (s.area) o.id = "office_" + s.area;
    o.name_ar = s.name_ar; o.name_en = s.name_en;
  }

  function renderMapTools() {
    if (!S.cmp) return;
    $("viewSeg").setAttribute("aria-label", t("map_before") + " / " + t("map_after"));
    $("viewSeg").innerHTML = ["before", "after"].map(function (v) { return '<button data-view="' + v + '" aria-pressed="' + (S.view === v) + '"' + (v === "before" && !changed() ? " disabled" : "") + ">" + t("map_" + v) + "</button>"; }).join("");
    const k = viewSim().counts;
    let rings = "";
    if (S.view === "after" && S.cmpFix && S.cmpFix.flipped_better.length) rings = '<span class="lg-div"></span><span class="lg rings"><span class="sw-ring" style="border-color:var(--served)"></span><b class="num">' + S.cmpFix.flipped_better.length + "</b> " + t("got_better") + "</span>";
    else if (S.view === "after" && S.cmp.flipped_worse.length) rings = '<span class="lg-div"></span><span class="lg rings"><span class="sw-ring"></span><b class="num">' + S.cmp.flipped_worse.length + "</b> " + t("got_worse") + "</span>";
    $("legend").innerHTML = ["served", "hardship", "left_out"].map(function (s) { return '<span class="lg"><span class="sw-dot ' + s + '"></span>' + t(s) + ' <b class="num">' + (k[s] || 0) + "</b></span>"; }).join("") + rings;
    $("filterSlot").innerHTML = S.reason ? '<div class="float filter-chip"><i class="ph ph-funnel"></i>' + t("r_" + S.reason) + '<button data-clear-reason>' + t("clear_filter") + "</button></div>" : "";
    const sim = viewSim();
    $("heroes").hidden = !S.heroes.length;
    $("heroes").innerHTML = '<p class="heroes-title">' + t("heroes") + '</p><div class="hero-list">' + S.heroes.map(function (h) {
      const c = S.byId.get(h.id), o = sim.byId.get(h.id) || { status: "served" };
      return '<button class="hero-btn" data-hero="' + esc(c.id) + '" aria-pressed="' + (S.sel === c.id) + '" title="' + esc(loc(h, "note")) + '"><span class="avatar ' + o.status + '">' + esc(initial(c)) + "</span>" + esc(name(c)) + "</button>";
    }).join("") + "</div>";
  }

  /* ---------------- citizen drawer ---------------- */
  function select(id) { S.sel = id; renderDrawer(); updateMap(); renderMapTools(); loadVoice(); }

  async function loadVoice() {
    if (!S.sel || !S.cmp) return;
    const id = S.sel, o = viewSim().byId.get(id);
    if (!o) return;
    const key = id + "|" + canon(o);
    if (S.voices.has(key)) return;
    S.voices.set(key, { status: "loading" });
    try {
      const r = await API.voice(id, o);
      S.voices.set(key, { status: "done", text_ar: r.text_ar, source: r.source || "ai" });
    } catch (e) {
      S.voices.set(key, { status: "done", text_ar: fallbackVoiceAr(S.byId.get(id), o), source: "fallback" });
    }
    if (S.sel === id) renderDrawer();
  }

  function renderDrawer() {
    const d = $("drawer");
    if (!S.sel || !S.cmp) { d.hidden = true; return; }
    const c = S.byId.get(S.sel);
    const ob = S.cmp.baseline.byId.get(c.id), os = S.cmp.scenario.byId.get(c.id);
    const o = S.view === "before" ? ob : os;
    if (!o) { d.hidden = true; return; }
    const attr = function (icon, txt, neg) { return '<span class="' + (neg ? "neg" : "") + '"><i class="ph ' + icon + '"></i>' + esc(txt) + "</span>"; };
    let h = '<div class="drawer-head"><span class="avatar lg ' + o.status + '">' + esc(initial(c)) + '</span><div><h3>' + esc(name(c)) + '</h3><div class="sub">' + c.age + " " + t("years") + ", " + esc(areaName(c.area)) + '</div></div><button class="icon-btn" data-close-drawer aria-label="' + t("close") + '"><i class="ph ph-x"></i></button></div><div class="drawer-body">';
    h += '<div class="status-flow"><span class="pill ' + ob.status + '">' + t(ob.status) + "</span>" + (changed() ? '<i class="ph ph-arrow-right flip-rtl"></i><span class="pill ' + os.status + '">' + t(os.status) + "</span>" : "") + "</div>";
    h += '<div class="attrs">' +
      attr("ph-car-profile", c.has_car ? t("car") : t("no_car_icon"), !c.has_car) +
      attr(c.has_smartphone ? "ph-device-mobile" : "ph-device-mobile-slash", c.has_smartphone ? t("phone") : t("no_phone"), !c.has_smartphone) +
      attr(c.mobility === "wheelchair" ? "ph-wheelchair" : "ph-person-simple-walk", t("mob_" + (c.mobility || "none")), c.mobility && c.mobility !== "none") +
      attr("ph-cursor-click", c.digital_literacy === "low" ? t("lit_low") : t("lit_ok"), c.digital_literacy === "low") +
      attr("ph-briefcase", c.works ? t("works_hours", { s: c.work_start, e: c.work_end }) : t("not_working")) +
      attr("ph-hand-heart", c.has_helper ? t("helper", { h: (S.lang === "ar" ? c.helper_relation_ar : c.helper_relation_en) || "" }) : t("no_helper"), !c.has_helper) +
      "</div>";
    const v = S.voices.get(c.id + "|" + canon(o));
    const isTpl = v && v.source !== "ai";
    h += '<div class="voice"><div class="voice-meta"><span>' + t("voice_label") + "</span>" + (v && v.status === "done" ? '<span class="src' + (isTpl ? "" : " ai") + '">' + t(isTpl ? "tpl" : "ai") + "</span>" : "") + "</div>" +
      (v && v.status === "done" ? '<p class="voice-text" lang="ar" dir="rtl">' + esc(v.text_ar) + "</p>" : '<div class="skel"></div><div class="skel w60"></div><span class="sr">' + t("voice_loading") + "</span>") +
      (S.lang === "en" ? '<p class="voice-en">' + esc(summaryEn(c, o)) + "</p>" : "") + "</div>";
    if (o.status !== "left_out") {
      const fact = function (k, val) { return '<div class="fact"><small>' + t(k) + "</small><b>" + val + "</b></div>"; };
      const facts = [fact("channel", esc(loc(o, "channel_name") || o.channel || "")),
        fact("mode", '<i class="ph ' + (MODE_ICON[o.mode] || "ph-dot") + '"></i> ' + t("m_" + o.mode) + (o.mode === "bus" ? ' <span class="num">(' + ((o.bus_transfers || 0) + 1) + ")</span>" : ""))];
      if (o.mode !== "online") facts.push(fact("visit_day", o.visit_day ? dayName(o.visit_day) : "-"), fact("travel", '<span class="num">' + Math.round(o.travel_minutes || 0) + "</span> " + t("min")));
      facts.push(fact("hours_lost", '<span class="num">' + f1(o.hours_lost) + "</span> " + t("hrs")), fact("cost", '<span class="num">' + f1(o.cost_jd) + "</span> " + t("jd")));
      h += '<div class="facts">' + facts.join("") + "</div>";
      if (o.work_hours_missed > 0) h += '<div class="facts" style="grid-template-columns:1fr"><div class="fact" style="border:0"><small>' + t("work_missed") + '</small><b><span class="num">' + f1(o.work_hours_missed) + "</span> " + t("hrs") + "</b></div></div>";
    }
    if ((o.reasons || []).length) h += '<div><h4 class="sec-title" style="margin-bottom:8px">' + t("reasons") + '</h4><div class="chips">' + o.reasons.map(function (r) { return '<span class="rchip"><i class="ph ' + (REASON_ICON[r] || "ph-warning") + '"></i>' + t("r_" + r) + "</span>"; }).join("") + "</div></div>";
    h += "</div>";
    d.innerHTML = h; d.hidden = false;
  }

  /* ---------------- impact panel ---------------- */
  function delta(v, lowerIsBetter, unit) {
    if (Math.abs(v) < 0.05) return '<span class="delta flat">' + t("unchanged") + "</span>";
    const bad = lowerIsBetter ? v > 0 : v < 0;
    return '<span class="delta ' + (bad ? "bad" : "good") + '"><i class="ph-fill ' + (v > 0 ? "ph-caret-up" : "ph-caret-down") + '"></i><span class="num">' + f1(Math.abs(v)) + "</span> " + (unit || t("pts")) + "</span>";
  }

  function fixCount() {
    if (!S.fixes || !S.fixes.list) return 0;
    return S.fixes.list.length + (S.fixes.ai && S.fixes.ai.fix ? 1 : 0);
  }
  function renderTabs() {
    const nf = fixCount();
    $("tabs").innerHTML = '<button class="tab" role="tab" data-tab="impact" aria-selected="' + (S.tab === "impact") + '"><i class="ph ph-chart-bar-horizontal"></i>' + t("impact") + "</button>" +
      '<button class="tab" role="tab" data-tab="fixes" aria-selected="' + (S.tab === "fixes") + '"' + (S.fixes ? "" : " disabled") + '><i class="ph ph-wrench"></i>' + t("fixes") + (nf ? ' <span class="count num">' + nf + "</span>" : "") + "</button>";
  }

  function renderImpact() {
    if (!S.cmp) return;
    renderTabs();
    const el = $("impactPanel"), sc = el.scrollTop;
    el.innerHTML = S.tab === "fixes" ? fixesHTML() : impactHTML();
    el.scrollTop = sc;
    renderActions();
  }

  function robustHTML() {
    const R = S.sens;
    const btn = function (cls, icon, title, sub) { return '<button class="robust ' + cls + '" data-modal="assumptions"><i class="' + icon + '"></i><span><b>' + title + "</b><small>" + sub + '</small></span><i class="ph ph-caret-right go flip-rtl"></i></button>'; };
    if (!R || R.status === "checking") return btn("checking", "ph ph-circle-notch", t("robust_checking"), t("robust_hint"));
    if (R.status === "needs_fix") return btn("checking", "ph ph-shield", t("robust_after_fixes"), t("robust_hint"));
    if (R.status === "error") return btn("partial", "ph-fill ph-shield-warning", t("robust_failed"), t("robust_hint"));
    const r = R.res, held = r.ranking_held, n = r.runs;
    return btn(r.passed || (held === n && !R.hasFix) ? "" : "partial", "ph-fill " + (held === n ? "ph-shield-check" : "ph-shield-warning"), t(held === n ? "robust_ok" : "robust_partial", { h: held, n: n }), t("robust_hint"));
  }

  function impactHTML() {
    const cur = viewSim(), b = S.cmp.baseline, K = cur.kpis, D = S.cmp.kpi_delta, showD = S.view === "after" && changed();
    let h = '<div class="sec"><div class="kpis">' + [["pct_served", "served", false], ["pct_hardship", "hardship", true], ["pct_left_out", "left_out", true]].map(function (x) {
      return '<div class="kpi"><div class="kpi-label"><span class="sw-dot ' + x[1] + '"></span>' + t(x[1]) + '</div><div class="kpi-val num">' + f1(K[x[0]]) + "<small>%</small></div>" + (showD ? delta(D[x[0]], x[2]) : '<span class="delta flat">' + (S.view === "before" ? t("step_baseline") : t("vs_baseline")) + "</span>") + "</div>";
    }).join("") + "</div>";
    h += '<div class="kpi-sub"><span>' + t("avg_hours") + ' <b class="num">' + f1(K.avg_hours_lost) + "</b> " + t("hrs") + " " + (showD ? delta(D.avg_hours_lost, true, t("hrs")) : "") + "</span><span>" + t("avg_cost") + ' <b class="num">' + f1(K.avg_cost_jd) + "</b> " + t("jd") + " " + (showD ? delta(D.avg_cost_jd, true, t("jd")) : "") + "</span></div>";
    if (changed()) h += robustHTML();
    h += "</div>";

    // equity bars: groups the backend returned, known groups first, two hardest-hit on top
    const worst = changed() ? S.cmp.worst_groups.slice(0, 2) : [];
    const groups = Object.keys(cur.by_group).filter(function (g) { return g !== "all"; }).sort(function (x, y) {
      const wx = worst.indexOf(x), wy = worst.indexOf(y);
      if (wx >= 0 || wy >= 0) return (wx < 0 ? 9 : wx) - (wy < 0 ? 9 : wy);
      const ox = GROUP_ORDER.indexOf(x), oy = GROUP_ORDER.indexOf(y);
      return (ox < 0 ? 99 : ox) - (oy < 0 ? 99 : oy);
    });
    const row = function (g, cls) {
      const s = cur.by_group[g], bb = b.by_group[g] || s, bad = s.left_out + s.hardship, d = bad - (bb.left_out + bb.hardship);
      return '<div class="eq ' + (cls || "") + '"><span class="name">' + (g === "all" ? t("everyone") : esc(groupLabel(g))) + (worst.indexOf(g) >= 0 && S.view === "after" ? ' <span class="worst-tag">' + t("worst") + "</span>" : "") + "</span>" +
        '<span class="bar" role="img" aria-label="' + f1(s.served) + "% / " + f1(s.hardship) + "% / " + f1(s.left_out) + '%"><i class="s" style="width:' + s.served + '%"></i><i class="h" style="width:' + s.hardship + '%"></i><i class="l" style="width:' + s.left_out + '%"></i></span>' +
        '<span class="v num">' + f1(bad) + "%" + (showD && Math.abs(d) >= 0.05 ? '<small class="' + (d > 0 ? "delta bad" : "delta good") + '">' + (d > 0 ? "+" : "-") + f1(Math.abs(d)) + "</small>" : "") + "</span></div>";
    };
    h += '<div class="sec"><h3 class="sec-title">' + t("equity") + "</h3>" + row("all", "all") + groups.map(function (g) { return row(g); }).join("") +
      '<div class="eq-legend"><span><span class="sw-dot hardship"></span>' + t("hardship") + '</span><span><span class="sw-dot left_out"></span>' + t("left_out") + "</span><span>% = " + t("hardship") + " + " + t("left_out") + "</span></div></div>";

    // who is left out, grouped by reason code
    const counts = {}, tagsBy = {};
    S.pop.forEach(function (c) {
      const o = cur.byId.get(c.id);
      if (!o || o.status !== "left_out") return;
      (o.reasons || []).forEach(function (r) {
        counts[r] = (counts[r] || 0) + 1;
        tagsBy[r] = tagsBy[r] || {};
        (c.tags || []).forEach(function (g) { if (g !== "student") tagsBy[r][g] = (tagsBy[r][g] || 0) + 1; });
      });
    });
    const keys = Object.keys(counts).sort(function (a, b2) { return counts[b2] - counts[a]; });
    h += '<div class="sec"><h3 class="sec-title"><span>' + t("who_left") + '</span><span class="num" style="color:var(--left)">' + (cur.counts.left_out || 0) + " " + t("people") + "</span></h3>";
    if (!keys.length) h += '<div class="ok-note"><i class="ph ph-check-circle"></i>' + t("nobody_left") + "</div>";
    else h += '<div class="reasons">' + keys.map(function (r) {
      const top = Object.keys(tagsBy[r]).sort(function (a, b2) { return tagsBy[r][b2] - tagsBy[r][a]; }).slice(0, 2).map(groupLabel).join(S.lang === "ar" ? "، " : ", ");
      return '<button class="reason" data-reason="' + esc(r) + '" aria-pressed="' + (S.reason === r) + '"><i class="ph ' + (REASON_ICON[r] || "ph-warning") + '"></i><span><b>' + t("r_" + r) + "</b><small>" + esc(top) + '</small></span><span class="n num">' + counts[r] + "</span></button>";
    }).join("") + "</div>";
    return h + "</div>";
  }

  function miniBar(k) {
    const T = (k.pct_served + k.pct_hardship + k.pct_left_out) || 1;
    return '<span class="bar"><i class="s" style="width:' + (k.pct_served / T * 100) + '%"></i><i class="h" style="width:' + (k.pct_hardship / T * 100) + '%"></i><i class="l" style="width:' + (k.pct_left_out / T * 100) + '%"></i></span>';
  }

  function fixCard(fx, i) {
    const F = S.fixes, isAI = fx.source === "ai_proposed", applied = S.appliedFix && S.appliedFix.id === fx.id;
    const ex = loc(fx, "explanation");
    const aiPending = F.ai.status === "thinking";
    const exSrc = fx._explainSource || F.ai.source;
    let exHTML = "";
    if (ex) exHTML = '<p class="explain">' + esc(ex) + '<span class="src' + (exSrc === "fallback" ? "" : " ai") + '">' + t(exSrc === "fallback" ? "tpl" : "ai") + "</span></p>";
    else if (aiPending) exHTML = '<div class="skel"></div><div class="skel w60" style="margin-bottom:12px"></div>';
    const bars = F.scenKpis && fx._after ? '<div class="ba"><span>' + t("map_before") + "</span>" + miniBar(F.scenKpis) + "<span>" + t("map_after") + "</span>" + miniBar(fx._after) + "</div>" : "<span></span>";
    return '<article class="fix' + (isAI ? " ai" : "") + (applied ? " applied" : "") + '" style="animation-delay:' + (i * 70) + 'ms">' +
      '<span class="prov"><i class="ph-fill ' + (isAI ? "ph-sparkle" : "ph-check-circle") + '" style="' + (isAI ? "color:var(--accent)" : "") + '"></i>' + t(isAI ? "badge_ai" : "badge_engine") + "</span>" +
      '<h4 class="fix-title">' + esc(loc(fx, "title")) + "</h4>" +
      '<div class="fix-mid"><div class="drops"><span><b class="num">-' + f1(fx.left_out_drop) + "</b>" + t("pts") + " " + t("left_drop") + '</span><span><b class="num">-' + f1(fx.hardship_drop) + "</b>" + t("pts") + " " + t("hard_drop") + "</span></div>" + bars + "</div>" +
      exHTML +
      '<div class="fix-acts">' + (applied ? '<span class="applied-note"><i class="ph-fill ph-check-circle"></i>' + t("applied") + '</span><button class="btn sm ghost" data-unfix><i class="ph ph-arrow-counter-clockwise"></i>' + t("cancel") + "</button>"
        : '<span></span><button class="btn sm ' + (isAI ? "accent" : "") + '" data-fix="' + esc(fx.id) + '"><i class="ph ph-check"></i>' + t("apply_fix") + "</button>") + "</div></article>";
  }

  function fixesHTML() {
    const F = S.fixes;
    if (!F) return "";
    let h = '<div class="sec">';
    if (F.status === "searching") {
      h += '<div class="fix-status"><i class="ph ph-circle-notch" style="animation:spin 1.2s linear infinite"></i>' + t("fixes_searching") + "</div>";
      for (let i = 0; i < 3; i++) h += '<div class="fix"><div class="skel w60"></div><div class="skel"></div><div class="skel"></div><div class="skel w60"></div></div>';
      return h + "</div>";
    }
    if (F.status === "error") return h + '<div class="ai-hidden">' + t("fixes_error") + ' <button class="btn sm ghost" id="fixBtnRetry">' + t("retry") + "</button></div></div>";
    h += '<div class="fix-status"><i class="ph ph-cpu"></i>' + t("fixes_done_n", { n: F.list.length, s: (F.ms / 1000).toFixed(1) }) + "</div>";
    if (!F.list.length) h += '<div class="ai-hidden">' + t("fixes_none") + "</div>";
    F.list.forEach(function (fx, i) { h += fixCard(fx, i); });
    if (F.ai.status === "thinking") h += '<div class="ai-wait"><i class="ph-fill ph-sparkle"></i>' + t("ai_thinking") + "</div>";
    else if (F.ai.status === "error") h += '<div class="ai-hidden">' + t("ai_failed") + "</div>";
    else if (F.ai.fix) h += fixCard(F.ai.fix, F.list.length);
    else h += '<div class="ai-hidden">' + t("ai_hidden") + "</div>";
    return h + "</div>";
  }

  function renderActions() {
    const can = changed() || S.appliedFix;
    $("actions").innerHTML = '<button class="btn accent" id="fixBtn"' + (can ? "" : " disabled") + '><i class="ph ph-wrench"></i>' + t("suggest_fixes") + "</button>" +
      '<button class="btn ghost" id="reportBtn"' + (can ? "" : " disabled") + '><i class="ph ph-file-text"></i>' + t("report") + "</button>";
  }

  /* ---------------- fixes flow: /fixgrid first (instant), then /fixes (AI) ---------------- */
  async function startFixes(force) {
    const scen = scenarioPolicy(), key = canon(scen);
    S.tab = "fixes";
    if (!force && S.fixes && S.fixes.key === key && S.fixes.status !== "error") { renderImpact(); return; }
    const scenKpis = S.appliedFix ? S.preKpis : S.cmp.scenario.kpis;
    S.fixes = { status: "searching", key: key };
    renderImpact();
    const t0 = performance.now();
    let list;
    try { list = await API.fixgrid(S.baseline, scen); }
    catch (e) { if (S.fixes && S.fixes.key === key) { S.fixes = { status: "error", key: key }; renderImpact(); } toast(e); return; }
    if (!S.fixes || S.fixes.key !== key) return;
    S.fixes = { status: "ready", key: key, list: list, ms: performance.now() - t0, scenKpis: scenKpis, ai: { status: "thinking" } };
    S.sens = null; scheduleSensitivity();
    renderImpact();

    // before/after bars: one /simulate per fix, in parallel; the cards don't wait for them
    const withAfter = function (fx) { return API.simulate(fx.policy).then(function (r) { fx._after = r.kpis; }).catch(function () { /* bars stay hidden */ }); };
    Promise.all(list.map(withAfter)).then(function () { if (S.fixes && S.fixes.key === key) renderImpact(); });

    try {
      const r = await API.fixes(S.baseline, scen);
      if (!S.fixes || S.fixes.key !== key) return;
      r.fixes.forEach(function (ef) {
        const g = list.find(function (x) { return x.id === ef.id; });
        if (g) { g.explanation_ar = ef.explanation_ar; g.explanation_en = ef.explanation_en; g._explainSource = ef.explanation_source || r.source; }
      });
      const ai = r.fixes.find(function (x) { return x.source === "ai_proposed"; }) || null;
      S.fixes.ai = { status: "done", fix: ai, source: r.source };
      renderImpact();
      if (ai) {
        await withAfter(ai);
        renderImpact();
        const card = document.querySelector(".fix.ai");
        if (card && S.tab === "fixes") card.scrollIntoView({ block: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
      }
    } catch (e) {
      if (S.fixes && S.fixes.key === key) { S.fixes.ai = { status: "error" }; renderImpact(); }
    }
  }

  function findFix(id) {
    const F = S.fixes; if (!F || !F.list) return null;
    return F.list.find(function (x) { return x.id === id; }) || (F.ai && F.ai.fix && F.ai.fix.id === id ? F.ai.fix : null);
  }
  function applyFix(id) {
    const fx = findFix(id); if (!fx) return;
    if (!S.appliedFix) { S.prePolicy = clone(S.policy); S.preKpis = S.cmp.scenario.kpis; }
    S.policy = clone(fx.policy); S.appliedFix = fx; S.view = "after"; S.reason = null;
    renderSteps(); renderImpact(); renderPolicy();
    scheduleCompare(0);
  }
  function unapplyFix() {
    if (!S.appliedFix) return;
    S.policy = clone(S.prePolicy); S.appliedFix = null; S.prePolicy = null; S.preKpis = null;
    renderSteps(); renderImpact(); renderPolicy();
    scheduleCompare(0);
  }

  /* ---------------- modals ---------------- */
  function openModal(html) { const m = $("modal"); m.innerHTML = '<div class="modal" role="dialog" aria-modal="true">' + html + "</div>"; m.hidden = false; const b = m.querySelector("[data-close-modal]"); if (b) b.focus(); }
  function closeModal() { $("modal").hidden = true; $("modal").innerHTML = ""; }
  function modalHead(title, sub) { return '<div class="modal-head"><div><h2>' + title + "</h2><p>" + sub + '</p></div><button class="icon-btn" data-close-modal aria-label="' + t("close") + '"><i class="ph ph-x"></i></button></div>'; }
  const fmtVal = function (v) { return v && typeof v === "object" ? Object.keys(v).map(function (k) { return k + " " + v[k]; }).join(" / ") : esc(v); };

  function assumptionsModal() {
    let h = modalHead(t("assumptions"), t("assumptions_sub")) + '<div class="modal-body">';
    const R = S.sens && S.sens.status === "done" && S.sens.res;
    if (R) {
      const yes = function (ok) { return '<span class="' + (ok ? "ok" : "no") + '">'; };
      h += '<section><h3 class="sec-title">' + t("robust_title") + '</h3><p class="help" style="margin:-4px 0 10px">' + t("robust_body") + "</p><table><tbody>" +
        "<tr><td>" + t("sens_ranking") + '</td><td class="num">' + yes(R.ranking_held === R.runs) + R.ranking_held + "/" + R.runs + "</span></td></tr>" +
        (R.fix_still_helps != null && S.sens.hasFix ? "<tr><td>" + t("sens_fix") + '</td><td class="num">' + yes(R.fix_still_helps === R.runs) + R.fix_still_helps + "/" + R.runs + "</span></td></tr>" : "") +
        (R.stable_top_group ? "<tr><td colspan=2>" + t("stable_group", { g: esc(groupLabel(R.stable_top_group)) }) + "</td></tr>" : "") +
        (S.sens.hasFix ? "<tr><td>" + t("sens_result") + "</td><td>" + yes(R.passed) + t(R.passed ? "passed" : "partial") + "</span></td></tr>" : "") +
        "</tbody></table>";
      const detail = R.detail || R.runs_detail;
      if (Array.isArray(detail) && detail.length) {
        h += '<table style="margin-top:10px"><thead><tr><th>' + t("run") + "</th><th>" + t("top2") + "</th><th>" + t("fix_helps") + "</th></tr></thead><tbody>" + detail.map(function (d) {
          const top2 = d.top2 || d.worst_groups || [];
          return "<tr><td>" + esc(d.key || d.constant || "") + ' <span class="num">' + (d.factor ? (d.factor > 1 ? "+" : "-") + Math.round(Math.abs(d.factor - 1) * 100) + "%" : "") + "</span></td><td>" + top2.map(groupLabel).join(S.lang === "ar" ? "، " : ", ") + "</td><td>" + (d.fixHelps == null && d.fix_helps == null ? "-" : t((d.fixHelps || d.fix_helps) ? "yes" : "no")) + "</td></tr>";
        }).join("") + "</tbody></table>";
      }
      h += "</section>";
    }
    if (S.assumptions.length) {
      h += '<section><h3 class="sec-title">' + t("assumptions") + "</h3><table><thead><tr><th>" + t("col_constant") + "</th><th>" + t("col_value") + "</th><th>" + t("col_tag") + "</th><th>" + t("col_why") + "</th></tr></thead><tbody>" +
        S.assumptions.map(function (a) {
          const label = loc(a, "label");
          return "<tr><td>" + (label ? esc(label) + "<br>" : "") + '<code class="num" style="font-size:11px;color:var(--faint)">' + esc(a.key) + '</code></td><td class="num">' + fmtVal(a.value) + '</td><td><span class="tagcell' + (a.tag === "ANCHORED" ? " anch" : "") + '">' + esc(a.tag) + "</span></td><td>" + esc(loc(a, "rationale")) + (a.source ? '<br><small style="color:var(--muted)">' + esc(typeof a.source === "object" ? (a.source.name || "") + " " + (a.source.year || "") : a.source) + "</small>" : "") + "</td></tr>";
        }).join("") + "</tbody></table></section>";
    }
    openModal(h + "</div>");
  }

  async function reportModal() {
    const body = function (inner) { return modalHead(t("report_title"), t("report_sub")) + '<div class="modal-body">' + inner + "</div>"; };
    openModal(body('<div class="report-cols"><div class="report-col"><div class="skel"></div><div class="skel"></div><div class="skel w60"></div></div><div class="report-col"><div class="skel"></div><div class="skel"></div><div class="skel w60"></div></div></div><span class="sr">' + t("report_loading") + "</span>"));
    try {
      const cmp = S.appliedFix ? await API.compare(S.baseline, S.prePolicy) : S.cmp;
      const sens = S.sens && S.sens.status === "done" ? S.sens.res : null;
      const r = await API.report(cmp.raw, sens);
      if ($("modal").hidden) return;
      const paras = function (txt) { return String(txt || "").split(/\n+/).filter(Boolean).map(function (p) { return "<p>" + esc(p) + "</p>"; }).join(""); };
      const tag = function (lang) { return '<span class="src' + (r.source === "fallback" ? "" : " ai") + '">' + DICT[lang][r.source === "fallback" ? "tpl" : "ai"] + "</span>"; };
      openModal(body('<div class="report-cols">' +
        '<div class="report-col" dir="rtl" lang="ar"><h3><span>العربية</span>' + tag("ar") + "</h3>" + paras(r.summary_ar) + "</div>" +
        '<div class="report-col" dir="ltr" lang="en"><h3><span>English</span>' + tag("en") + "</h3>" + paras(r.summary_en) + "</div></div>"));
    } catch (e) {
      if (!$("modal").hidden) openModal(body('<div class="ai-hidden">' + t("report_failed") + " <code>" + esc(e.message) + "</code></div>"));
    }
  }

  /* ---------------- render all ---------------- */
  function renderAll() {
    renderStatic(); renderSteps(); renderPolicy(); renderMapTools(); updateMap(); renderImpact(); renderDrawer();
  }

  /* ---------------- events ---------------- */
  document.addEventListener("click", function (e) {
    const q = function (sel) { return e.target.closest(sel); };
    let el;
    if (q("#bootRetry")) return boot();
    if (q("#toastRetry")) { $("toast").hidden = true; if (toast.retry) toast.retry(); return; }
    if (q("#langBtn") || q("#langBtn2")) {
      S.lang = S.lang === "ar" ? "en" : "ar"; store.set("nas.lang", S.lang);
      if (!S.cmp) { renderStatic(); return $("boot").hidden ? null : bootScreen($("bootRetry") ? "error" : "loading"); }
      renderAll(); renderLabels(); placeZoom(); return;
    }
    if (q("#themeBtn")) {
      S.theme = currentDark() ? "light" : "dark"; store.set("nas.theme", S.theme);
      document.documentElement.setAttribute("data-theme", S.theme); setTiles(); renderStatic(); return;
    }
    if (!S.cmp) return;
    if ((el = q("[data-preset]"))) return loadPreset(el.dataset.preset);
    if ((el = q("[data-step]"))) {
      const s = el.dataset.step;
      if (s === "baseline") return loadPreset((S.scenarios.find(function (x) { return same(x.policy, S.baseline); }) || S.scenarios[0]).id);
      if (s === "scenario" && S.appliedFix) return unapplyFix();
      return;
    }
    if ((el = q("[data-ex]"))) { S.text = t("example_" + (+el.dataset.ex + 1)); renderPolicy(); return runParse(); }
    if (q("#parseBtn")) return runParse();
    if ((el = q("[data-parse]"))) {
      if (el.dataset.parse === "apply" && S.parse && S.parse.policy) { const p = clone(S.parse.policy); S.parse = null; return edit(function (pp) { Object.keys(pp).forEach(function (k) { delete pp[k]; }); Object.assign(pp, p); }, { now: true }); }
      S.parse = null; return renderPolicy();
    }
    if ((el = q("[data-sw]"))) {
      const id = el.dataset.sw, on = el.getAttribute("aria-checked") !== "true";
      return edit(function (p) {
        if (id === "online") p.online_enabled = on;
        else if (id === "onlineOnly") { p.online_only = on; if (on) p.online_enabled = true; }
        else if (id === "appt") p.appointment_required = on;
        else if (id.indexOf("late:") === 0) {
          const o = p.offices[+id.slice(5)];
          if (o.schedule.thu) o.schedule.thu = [o.schedule.thu[0], on ? "19:00" : (Object.keys(o.schedule).filter(function (d) { return d !== "thu"; }).map(function (d) { return o.schedule[d][1]; })[0] || "15:00")];
        }
        else if (id.indexOf("acc:") === 0) p.offices[+id.slice(4)].wheelchair_accessible = on;
      }, { now: true });
    }
    if ((el = q("[data-day]"))) {
      const parts = el.dataset.day.split(":"), i = +parts[0], d = parts[1];
      return edit(function (p) {
        const o = p.offices[i];
        if (o.schedule[d]) delete o.schedule[d];
        else { const ref = DAYS.filter(function (x) { return o.schedule[x] && x !== "thu"; })[0]; o.schedule[d] = ref ? o.schedule[ref].slice() : ["08:00", "15:00"]; }
      });
    }
    if (q("#addUnit")) return edit(function (p) {
      p.mobile_units = p.mobile_units || [];
      const used = p.mobile_units.map(function (u) { return u.area + u.day; });
      const area = Object.keys(S.areas).find(function (a) { return used.indexOf(a + "sat") < 0; }) || Object.keys(S.areas)[0];
      p.mobile_units.push({ area: area, day: "sat", open: "09:00", close: "14:00" });
    }, { now: true });
    if ((el = q("[data-urm]"))) return edit(function (p) { p.mobile_units.splice(+el.dataset.urm, 1); }, { now: true });
    if ((el = q("[data-fee]"))) return edit(function (p) { p.fee_jd = Math.max(0, Math.round((p.fee_jd + +el.dataset.fee) * 10) / 10); });
    if ((el = q("[data-visits]"))) return edit(function (p) { p.visits_required = Math.min(3, Math.max(1, p.visits_required + +el.dataset.visits)); });
    if ((el = q("[data-view]"))) { S.view = el.dataset.view; renderMapTools(); updateMap(); renderImpact(); renderDrawer(); loadVoice(); return; }
    if ((el = q("[data-hero]"))) { const c = S.byId.get(el.dataset.hero); map.flyTo([c.lat, c.lng], Math.max(map.getZoom(), 14), { duration: reduceMotion ? 0 : 0.8 }); return select(c.id); }
    if (q("[data-close-drawer]")) { S.sel = null; renderDrawer(); updateMap(); renderMapTools(); return; }
    if ((el = q("[data-reason]"))) { S.reason = S.reason === el.dataset.reason ? null : el.dataset.reason; renderMapTools(); updateMap(); renderImpact(); return; }
    if (q("[data-clear-reason]")) { S.reason = null; renderMapTools(); updateMap(); renderImpact(); return; }
    if ((el = q("[data-tab]"))) { S.tab = el.dataset.tab; return renderImpact(); }
    if (q("#fixBtn")) return startFixes();
    if (q("#fixBtnRetry")) return startFixes(true);
    if (q("#reportBtn")) return reportModal();
    if ((el = q("[data-fix]"))) return applyFix(el.dataset.fix);
    if (q("[data-unfix]")) return unapplyFix();
    if (q("[data-modal]")) return assumptionsModal();
    if (q("[data-close-modal]") || e.target === $("modal")) return closeModal();
  });

  document.addEventListener("change", function (e) {
    const el = e.target;
    if (!S.cmp) return;
    if (el.dataset.site !== undefined) return edit(function (p) { snapOffice(p.offices[+el.dataset.site], el.value); }, { now: true });
    if (el.dataset.open !== undefined || el.dataset.close !== undefined) {
      const i = +(el.dataset.open !== undefined ? el.dataset.open : el.dataset.close), isOpen = el.dataset.open !== undefined;
      if (!/^\d\d:\d\d$/.test(el.value)) return;
      return edit(function (p) { const o = p.offices[i]; Object.keys(o.schedule).forEach(function (d) { if (isOpen) o.schedule[d][0] = el.value; else if (!(d === "thu" && o.schedule.thu[1] === "19:00")) o.schedule[d][1] = el.value; }); });
    }
    if (el.dataset.u) {
      const parts = el.dataset.u.split(":");
      return edit(function (p) { p.mobile_units[+parts[0]][parts[1]] = el.value; });
    }
  });
  document.addEventListener("input", function (e) { if (e.target.id === "nl") S.text = e.target.value; });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { if (!$("modal").hidden) closeModal(); else if (S.sel) { S.sel = null; renderDrawer(); updateMap(); renderMapTools(); } }
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && e.target.id === "nl") runParse();
  });
  if (window.matchMedia) window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () { if (!S.theme) { setTiles(); renderStatic(); } });

  if (S.theme) document.documentElement.setAttribute("data-theme", S.theme);
  boot();
  window.NasApp = { S: S };
})();
