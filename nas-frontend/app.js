/* Nas frontend: UI only. Every number comes from the backend through api.js (CLAUDE.md §7).
   Strings come from i18n.js. Nothing here simulates, scores or ranks. */
(function () {
  "use strict";
  const API = window.NasAPI, DICT = window.NasI18n, CFG = window.NAS_CONFIG;
  const DAYS = ["sat", "sun", "mon", "tue", "wed", "thu", "fri"];
  const GROUP_ORDER = ["elderly", "disabled", "no_car", "offline", "low_income", "worker", "student"];
  const REASON_ICON = { TOO_FAR: "ph-map-pin-line", NO_TRANSPORT: "ph-bus", HOURS_CONFLICT_WORK: "ph-clock-countdown", NO_SMARTPHONE: "ph-device-mobile-slash", LOW_DIGITAL_LITERACY: "ph-cursor-click", NOT_WHEELCHAIR_ACCESSIBLE: "ph-wheelchair", TOO_EXPENSIVE: "ph-coins", OFFICE_CLOSED_ON_AVAILABLE_DAYS: "ph-calendar-x",
    TRANSPORT_OVER_BUDGET: "ph-wallet", FUEL_COST: "ph-gas-pump", FARE_COST: "ph-ticket" };
  const MODE_ICON = { car: "ph-car-profile", helper_car: "ph-car-profile", bus: "ph-bus", taxi: "ph-taxi", online: "ph-globe-simple", home: "ph-house-line" };
  const PURPOSE_ICON = { work: "ph-briefcase", university: "ph-graduation-cap", hospital: "ph-first-aid-kit" };
  const PROTECT_GROUPS = GROUP_ORDER;
  const TRAVEL = "everyday_travel";
  // The ID-renewal panel sections, used when GET /services doesn't say (an older backend).
  const ID_LEVERS = ["offices", "online", "appointments", "mobile_units", "fee", "visits", "protections"];

  const $ = function (id) { return document.getElementById(id); };
  const esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (m) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[m]; }); };
  const f1 = function (x) { return (Math.round((+x || 0) * 10) / 10).toFixed(1); };
  const int = function (x) { return Math.round(+x || 0).toLocaleString("en-US"); };
  const clone = function (x) { return JSON.parse(JSON.stringify(x)); };
  // Key-order-independent equality, so a backend that reorders JSON keys still matches presets.
  const canon = function (x) { return JSON.stringify(x, function (k, v) { return v && typeof v === "object" && !Array.isArray(v) ? Object.keys(v).sort().reduce(function (o, kk) { o[kk] = v[kk]; return o; }, {}) : v; }); };
  const same = function (a, b) { return canon(a) === canon(b); };
  const store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode */ } },
  };
  const reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------- state ---------------- */
  const S = {
    lang: store.get("nas.lang") === "en" ? "en" : "ar",
    theme: store.get("nas.theme"),
    // reference data (GET)
    pop: [], byId: new Map(), sites: {}, areas: {}, scenarios: [], assumptions: [], heroes: [],
    // services (GET /services): S.scenarios holds the current service's presets, S.allScenarios every service's.
    service: null, services: [], allScenarios: [], heroCache: {},
    feePct: 100, voucherJd: 3, newOfficeArea: null,
    fareCustom: { bus: 10, taxi: 10 }, cashJd: 14, reasonSt: "left_out",
    baseline: null, policy: null, preset: null,
    prePolicy: null, preKpis: null, appliedFix: null,
    view: "after", reason: null, sel: null, tab: "impact", deltaRef: "prefix",
    text: "", parse: null,
    cmp: null, cmpFix: null, busy: false,
    undo: null,              // state before the edits since the last good /compare (restored on a 4xx)
    fixes: null, sens: null, voices: new Map(), report: null, llm: null,
    modal: null, kpiPrev: {},
  };

  function t(k, vars) {
    let s = (DICT[S.lang] && DICT[S.lang][k] != null) ? DICT[S.lang][k] : (DICT.en[k] != null ? DICT.en[k] : k);
    if (vars) Object.keys(vars).forEach(function (v) { s = s.split("{" + v + "}").join(vars[v]); });
    return s;
  }
  // Plural-aware: picks key_zero/_one/_two/_few/_many/_other by the language's plural rules; {n} is the count.
  const plural = {};
  function tp(k, n) {
    const pr = plural[S.lang] || (plural[S.lang] = new Intl.PluralRules(S.lang));
    const d = DICT[S.lang];
    const cat = n === 0 && d[k + "_zero"] != null ? "zero" : pr.select(n);
    return t(d[k + "_" + cat] != null ? k + "_" + cat : k + "_other", { n: int(n) });
  }
  // Service-aware string: "<key>_<service id>" when the dictionary has it (e.g. served_everyday_travel = "Fine"),
  // else the plain key. ID renewal has no overrides, so its strings are exactly as before.
  function ts(k, vars) { return DICT.en[k + "_" + S.service] != null ? t(k + "_" + S.service, vars) : t(k, vars); }
  const svcInfo = function () { return S.services.find(function (v) { return v.id === S.service; }) || null; };
  const isTravel = function () { return S.service === TRAVEL; };
  function levers() {
    const v = svcInfo();
    if (v && v.levers.length) return v.levers;
    return isTravel() ? ["fuel", "fares", "cash_support", "transport_vouchers"] : ID_LEVERS;
  }
  const lever = function (x) { return levers().indexOf(x) >= 0; };
  const loc = function (o, base) { return o ? (o[base + "_" + S.lang] || o[base + "_" + (S.lang === "ar" ? "en" : "ar")] || "") : ""; };
  const areaName = function (k) { return S.areas[k] ? loc(S.areas[k], "name") : k; };
  const siteName = function (id) { return S.sites[id] ? loc(S.sites[id], "name") : id; };
  const dayName = function (d) { return t("day_" + d); };
  const shortDay = function (d) { return S.lang === "ar" ? dayName(d).replace("ال", "").slice(0, 3) : dayName(d).slice(0, 2); };
  const name = function (c) { return (S.lang === "ar" ? c.name_ar : c.name_en) || c.name_ar || c.name_en || c.id; };
  const initial = function (c) { return name(c).replace(/^(أم |أبو |Um |Abu )/, "").charAt(0); };
  const groupLabel = function (g) { return DICT[S.lang]["g_" + g] ? t("g_" + g) : g; };
  const gk = function (base, c) { return base + "_" + (c && c.gender === "f" ? "f" : "m"); };   // gendered key
  const scenarioName = function (sc) { return loc(sc, "name") || (DICT.en["preset_" + sc.id] ? t("preset_" + sc.id) : sc.id); };
  const scenarioPolicy = function () { return S.appliedFix ? S.prePolicy : S.policy; };
  const changed = function () { return S.baseline && S.policy && !same(S.policy, S.baseline); };
  // Opening hours the engine accepts: HH:MM, closing at least an hour after opening (backend validate.py).
  const mins = function (s) { return +s.slice(0, 2) * 60 + +s.slice(3, 5); };
  const hoursOk = function (op, cl) { return /^\d\d:\d\d$/.test(op) && /^\d\d:\d\d$/.test(cl) && mins(cl) - mins(op) >= 60; };
  const heroOf = function (id) { return S.heroes.find(function (h) { return h.id === id; }) || null; };

  /* ---------------- toasts ---------------- */
  let toastTimer = null;
  function toastMsg(text, retry) {
    const el = $("toast");
    el.innerHTML = '<i class="ph-fill ph-warning-circle"></i><span>' + esc(text) + "</span>" + (retry ? '<button id="toastRetry">' + t("retry") + "</button>" : "");
    el.hidden = false;
    toastMsg.retry = retry || null;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.hidden = true; }, retry ? 9000 : 7000);
  }
  // Retry is offered only for network errors and 5xx; a 4xx won't succeed by retrying.
  function toastErr(err, retry) {
    const is4xx = err && err.status >= 400 && err.status < 500;
    toastMsg(t("request_failed", { msg: err && err.message ? err.message : String(err) }), is4xx ? null : retry);
  }
  // The backend's 422 text is technical English; show a translated hint instead (raw text goes to the console).
  function rejectReason(detail) {
    const d = String(detail || "").toLowerCase();
    if (d.indexOf("hours") >= 0 || d.indexOf("shorter than one visit") >= 0) return t("err_hours");
    if (d.indexOf("site") >= 0 || d.indexOf("area") >= 0) return t("err_site");
    return t("err_other");
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

  const opt = function (p, fb) { return p.catch(function (e) { if (e.status === 404 || e.status === 405) return fb; throw e; }); };

  // The current service's presets (its baseline first), heroes and baseline policy. The compare baseline is
  // always the current service's baseline_scenario. Heroes are fetched once per service.
  async function loadService() {
    const v = svcInfo();
    S.scenarios = S.allScenarios.filter(function (s) { return s.service === S.service; });
    if (!S.scenarios.length) throw new API.ApiError("no scenarios for " + S.service, 0, "/scenarios");
    const baseId = (v && v.baseline_scenario) || (S.service === "id_renewal" ? "baseline" : null);
    const base = S.scenarios.find(function (s) { return s.id === baseId; }) || S.scenarios[0];
    S.scenarios.sort(function (a, b) { return (a === base ? -1 : 0) - (b === base ? -1 : 0); });
    S.baseline = clone(base.policy); S.policy = clone(base.policy);
    if (!S.heroCache[S.service]) {
      const fb = S.service === "id_renewal" ? CFG.HERO_IDS.map(function (id) { return { id: id }; }) : [];
      const h = await opt(API.heroes(S.service), null);
      S.heroCache[S.service] = (h && h.length ? h : fb).filter(function (x) { return S.byId.has(x.id); });
    }
    S.heroes = S.heroCache[S.service];
  }

  // Everything a sector carries is dropped when entering or leaving one: fixes, robustness, report, parse,
  // drawer, reason filter, applied fix.
  function resetSectorState() {
    clearTimeout(cmpTimer); ++cmpSeq; ++sensSeq;
    S.appliedFix = null; S.prePolicy = null; S.preKpis = null; S.cmp = null; S.cmpFix = null; S.fixes = null; S.sens = null; S.report = null;
    S.parse = null; S.text = ""; S.reason = null; S.reasonSt = "left_out"; S.sel = null; S.view = "after"; S.tab = "impact"; S.deltaRef = "prefix";
    S.undo = null; S.kpiPrev = {}; S.busy = false; renderBusy();
    if (S.modal) closeModal();
  }

  // Choose a sector from the start list (or ?sector= on load): its baseline, presets and heroes, then /compare.
  let svcSeq = 0;
  async function chooseSector(id) {
    if (!S.services.some(function (v) { return v.id === id; })) return;
    const seq = ++svcSeq;
    resetSectorState();
    S.service = id;
    try { await loadService(); }
    catch (e) { console.error(e); if (seq === svcSeq) { S.service = null; renderHome(); toastErr(e); } return; }
    if (seq !== svcSeq) return;
    document.body.classList.remove("home");
    styleDots();
    renderStatic(); renderSteps(); renderPolicy(); renderDrawer();
    await recompute();
  }

  // Start state: the sector list on the left, every resident as a neutral dot, no pins, rings, heroes or steps,
  // a note instead of KPIs, and no /compare.
  function goHome() {
    ++svcSeq;
    resetSectorState();
    S.service = null; S.scenarios = []; S.heroes = []; S.baseline = null; S.policy = null; S.preset = null;
    styleDots();
    renderHome();
  }
  function renderHome() {
    document.body.classList.add("home");
    renderStatic();
    $("steps").hidden = true;
    $("policyHead").className = "panel-head";
    $("policyHead").innerHTML = '<h2 class="panel-title" id="policyTitle">' + t("choose_sector") + "</h2>";
    $("policyPanel").innerHTML = '<div class="sec"><div class="sectors">' + S.services.map(function (v) {
      const nm = DICT.en["svc_name_" + v.id] ? t("svc_name_" + v.id) : loc(v, "name"), desc = loc(v, "description");
      return '<button class="sector" data-sector="' + esc(v.id) + '"><i class="ph ' + (v.id === TRAVEL ? "ph-gas-pump" : "ph-identification-card") + '" aria-hidden="true"></i><b>' + esc(nm) + "</b>" +
        '<small title="' + esc(desc) + '">' + esc(desc) + '</small><i class="ph ph-caret-right go flip-rtl" aria-hidden="true"></i></button>';
    }).join("") + '</div></div><p class="footnote">' + t("prototype_note") + "</p>";
    $("viewSeg").hidden = true; $("legend").hidden = true; $("filterSlot").innerHTML = "";
    $("heroes").hidden = true; syncHeroesHeight();
    $("drawer").hidden = true;
    $("tabs").hidden = true; $("actions").hidden = true;
    $("impactPanel").innerHTML = '<div class="sec"><div class="home-note"><i class="ph ph-hand-pointing" aria-hidden="true"></i><span>' + t("choose_sector_note") + "</span></div></div>";
    if (map) {
      ringLayer.clearLayers(); pinLayer.clearLayers();
      dots.forEach(function (m) { if (m._path) m._path.setAttribute("class", "dot idle leaflet-interactive"); });
      declutterLabels();
    }
  }
  // The sector panel head: a back button to the list, and the sector name as the title.
  function renderPolicyHead() {
    const v = svcInfo(), nm = DICT.en["svc_name_" + S.service] ? t("svc_name_" + S.service) : loc(v, "name");
    $("policyHead").className = "panel-head sector-head";
    $("policyHead").innerHTML = '<button class="back-btn" data-home><i class="ph ph-arrow-left flip-rtl" aria-hidden="true"></i>' + t("sectors") + '</button><h2 class="panel-title" id="policyTitle">' + esc(nm) + "</h2>";
  }

  async function boot() {
    renderStatic();
    bootScreen("loading");
    try {
      const r = await Promise.all([API.population(), API.sites(), API.scenarios(), opt(API.assumptions(), []), opt(API.areas(), null), opt(API.services(), null)]);
      S.pop = r[0]; S.byId = new Map(S.pop.map(function (c) { return [c.id, c]; }));
      S.sites = r[1]; S.allScenarios = r[2]; S.assumptions = r[3];
      S.areas = r[4] && Object.keys(r[4]).length ? r[4] : CFG.AREAS;
      S.services = (r[5] && r[5].length ? r[5] : CFG.SERVICES).filter(function (v) { return S.allScenarios.some(function (s) { return s.service === v.id; }); });
      if (!S.services.length) throw new API.ApiError("no scenarios", 0, "/scenarios");
      initMap();
      // ?sector=id_renewal|everyday_travel skips the list (used on stage); otherwise the start state, every time.
      const want = new URLSearchParams(location.search).get("sector");
      if (want && S.services.some(function (v) { return v.id === want; })) {
        await chooseSector(want);
        if (!S.cmp) throw new API.ApiError("compare failed", 0, "/compare");
      } else goHome();
      bootScreen("done");
      refreshLlm();
    } catch (e) {
      console.error(e);
      bootScreen("error", e);
    }
  }

  /* ---------------- AI status chip (GET /llm/status) ---------------- */
  let llmSeq = 0;
  function refreshLlm() {
    const seq = ++llmSeq;
    API.llmStatus().then(function (s) { if (seq === llmSeq) { S.llm = s; renderChip(); } })
      .catch(function () { if (seq === llmSeq) { S.llm = null; renderChip(); } });
  }
  function renderChip() {
    const el = $("aiChip");
    if (!S.llm) { el.hidden = true; return; }
    const st = S.llm.state, key = st === "offline" ? "ai_cache" : st === "resting" ? "ai_resting" : "ai_live";
    el.hidden = false;
    el.className = "ai-chip " + st;
    el.innerHTML = '<span class="ai-dot" aria-hidden="true"></span><span class="ai-txt">' + t(key) + "</span>";
    el.setAttribute("aria-label", t(key) + " · " + t("ai_models_title"));
    el.title = t(key);
  }
  function llmModal() {
    const L = S.llm;
    let h = modalHead(t("ai_models_title"), t("ai_models_sub")) + '<div class="modal-body">';
    if (L && L.offline) h += '<p class="help" style="margin:0">' + t("ai_offline_note") + "</p>";
    if (L && L.models.length) h += "<table><thead><tr><th>" + t("col_provider") + "</th><th>" + t("col_slot") + "</th><th>" + t("col_model") + "</th><th>" + t("col_state") + "</th></tr></thead><tbody>" +
      L.models.map(function (m) {
        return "<tr><td>" + esc(m.provider) + "</td><td>" + esc(DICT.en["slot_" + m.slot] ? t("slot_" + m.slot) : m.slot) + '</td><td><code class="num">' + esc(m.model) + "</code></td><td>" +
          (m.available ? '<span class="ok">' + t("st_available") + "</span>" : '<span class="no">' + t("st_cooldown", { s: int(m.seconds_left) }) + "</span>") + "</td></tr>";
      }).join("") + "</tbody></table>";
    openModal(h + "</div>", "llm");
  }

  /* ---------------- compare ---------------- */
  let cmpSeq = 0, cmpTimer = null;
  function scheduleCompare(delay) {
    clearTimeout(cmpTimer);
    cmpTimer = setTimeout(recompute, delay == null ? CFG.COMPARE_DEBOUNCE_MS : delay);
  }
  function updatePreset() { S.preset = (S.scenarios.find(function (s) { return same(s.policy, S.policy); }) || {}).id || null; }
  // Remember the state of the last good /compare before the first edit after it, so a policy the engine
  // rejects (4xx) can be undone without losing the applied fix, the fixes or the robustness result.
  function snapshot() {
    if (S.undo || !S.cmp) return;
    S.undo = { policy: clone(S.policy), appliedFix: S.appliedFix, prePolicy: S.prePolicy && clone(S.prePolicy), preKpis: S.preKpis,
      fixes: S.fixes, sens: S.sens, tab: S.tab, cmpFix: S.cmpFix };
  }
  function restoreUndo() {
    const u = S.undo; S.undo = null;
    S.policy = u.policy; S.appliedFix = u.appliedFix; S.prePolicy = u.prePolicy; S.preKpis = u.preKpis;
    S.fixes = u.fixes; S.sens = u.sens; S.tab = u.tab; S.cmpFix = u.cmpFix;
    updatePreset();
  }
  async function recompute() {
    const seq = ++cmpSeq;
    S.busy = true; renderBusy();
    updatePreset();
    let failed = null;
    try {
      const jobs = [API.compare(S.baseline, S.policy)];
      if (S.appliedFix) jobs.push(API.compare(S.prePolicy, S.policy));
      const r = await Promise.all(jobs);
      if (seq !== cmpSeq) return;
      S.cmp = r[0]; S.cmpFix = r[1] || null; S.undo = null;
    } catch (e) {
      if (seq !== cmpSeq) return;
      failed = e;
    } finally {
      if (seq === cmpSeq) { S.busy = false; renderBusy(); }
    }
    if (failed) {
      const is4xx = failed.status >= 400 && failed.status < 500;
      if (is4xx && S.undo && S.cmp) {
        console.warn("policy rejected by the engine:", failed.detail || failed.message);
        restoreUndo();
        toastMsg(t("policy_rejected", { reason: rejectReason(failed.detail) }));
        renderAll();
        return;
      }
      toastErr(failed, recompute);
      return;
    }
    if (!S.cmp) return;
    autoSensitivity();
    renderAll();
    loadVoice(); // the open citizen's outcome may have changed
  }

  function edit(mutator, opts) {
    snapshot();
    mutator(S.policy);
    S.appliedFix = null; S.prePolicy = null; S.preKpis = null; S.cmpFix = null; S.fixes = null; S.sens = null;
    if (S.tab === "fixes") S.tab = "impact";
    renderPolicy(); renderSteps();
    scheduleCompare(opts && opts.now ? 0 : undefined);
  }

  function loadPreset(id) {
    const sc = S.scenarios.find(function (s) { return s.id === id; });
    if (!sc) return;
    snapshot();
    S.policy = clone(sc.policy);
    S.appliedFix = null; S.prePolicy = null; S.preKpis = null; S.cmpFix = null; S.fixes = null; S.sens = null; S.parse = null; S.reason = null;
    if (S.tab === "fixes") S.tab = "impact";
    renderPolicy(); renderSteps();
    scheduleCompare(0);
  }

  /* ---------------- robustness (POST /sensitivity) ----------------
     Not run on every edit: on a badge click (ranking only, unless fixes exist), automatically once fixes have
     loaded (with the top fix), and after a fix is applied (with that fix). The backend caches the demo path. */
  let sensSeq = 0;
  function sensFix() {
    if (S.appliedFix) return S.appliedFix;
    const F = S.fixes;
    return F && F.status === "ready" && F.key === canon(scenarioPolicy()) && F.list[0] ? F.list[0] : null;
  }
  function sensKey() { const f = sensFix(); return canon([S.baseline, scenarioPolicy(), f && f.policy]); }
  function currentSens() { return S.sens && S.sens.key === sensKey() ? S.sens : null; }
  function runSensitivity() {
    if (!changed()) return Promise.resolve();
    const cur = currentSens();
    if (cur && (cur.status === "done" || cur.status === "checking")) return cur.promise || Promise.resolve();
    const fix = sensFix(), key = sensKey(), seq = ++sensSeq;
    const entry = { status: "checking", key: key };
    S.sens = entry;
    entry.promise = API.sensitivity(S.baseline, scenarioPolicy(), fix).then(function (res) {
      if (seq === sensSeq) S.sens = { status: "done", key: key, res: res, hasFix: !!fix && res.fix_checked !== false, promise: entry.promise };
    }, function (e) {
      console.warn("sensitivity failed", e);
      if (seq === sensSeq) S.sens = { status: "error", key: key };
    }).then(function () {
      if (seq !== sensSeq) return;
      renderImpact();
      if (S.modal === "assumptions") assumptionsModal(true);
    });
    renderImpact();
    return entry.promise;
  }
  function autoSensitivity() {
    if (!changed()) { S.sens = null; return; }
    if (currentSens()) return;
    if (sensFix()) runSensitivity();
  }

  /* ---------------- header ---------------- */
  function renderStatic() {
    document.documentElement.lang = S.lang;
    document.documentElement.dir = S.lang === "ar" ? "rtl" : "ltr";
    document.title = t("doc_title");
    document.querySelectorAll("[data-t]").forEach(function (el) { el.textContent = t(el.getAttribute("data-t")); });
    document.querySelectorAll("[data-t-aria]").forEach(function (el) { el.setAttribute("aria-label", t(el.getAttribute("data-t-aria"))); });
    $("langBtn").textContent = t("lang_other");
    $("themeBtn").innerHTML = '<i class="ph ' + (currentDark() ? "ph-sun" : "ph-moon-stars") + '"></i>';
    renderChip();
  }
  function renderBusy() { $("busy").hidden = !S.busy; }

  function renderSteps() {
    if (!S.service) { $("steps").hidden = true; return; }
    $("steps").hidden = false;
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
  // A stepper with meaningful labels for its two buttons ("Decrease: Fee (JD)").
  function stepper(attr, val, unit, label, step) {
    const s = step || 1;
    return '<div class="stepper"><button ' + attr + '="-' + s + '" aria-label="' + esc(t("dec_x", { x: label })) + '">−</button><output class="num">' + val + (unit || "") +
      '</output><button ' + attr + '="' + s + '" aria-label="' + esc(t("inc_x", { x: label })) + '">+</button></div>';
  }

  function renderPolicy() {
    if (!S.service || !S.policy) return;
    renderPolicyHead();
    const p = S.policy;
    let h = "";
    h += '<div class="sec"><h3 class="sec-title">' + t("presets") + '</h3><div class="presets">' +
      S.scenarios.map(function (sc) {
        const note = loc(sc, "note");
        return '<button class="preset" data-preset="' + esc(sc.id) + '" aria-pressed="' + (S.preset === sc.id) + '"><b>' + esc(scenarioName(sc)) + "</b>" + (note ? "<small>" + esc(note) + "</small>" : "<small></small>") + '<i class="ph ph-check tick" aria-hidden="true"></i></button>';
      }).join("") + "</div></div>";

    const ex = [1, 2, 3, 4].map(function (i) { return ts("example_" + i); });
    h += '<div class="sec"><label class="sec-title" for="nl">' + t("describe") + '</label>' +
      '<textarea class="input" id="nl" rows="3" placeholder="' + esc(ts("describe_ph")) + '">' + esc(S.text) + "</textarea>" +
      '<div class="examples">' + ex.map(function (e, i) { return '<button class="ex" data-ex="' + i + '" title="' + esc(e) + '">' + esc(e) + "</button>"; }).join("") + "</div>" +
      '<div class="parse-row"><p class="help" style="margin:0">' + t("describe_help") + '</p><button class="btn sm accent" id="parseBtn"' + (S.parse && S.parse.status === "loading" ? " disabled" : "") + '><i class="ph ph-sparkle"></i>' + t("parse") + "</button></div>" +
      renderParse() + "</div>";

    if (lever("offices") && !p.online_only) {
      p.offices.forEach(function (o, i) {
        const days = DAYS.filter(function (d) { return o.schedule[d]; });
        const first = days.filter(function (d) { return d !== "thu"; })[0] || days[0];
        const hrs = first ? o.schedule[first] : ["08:00", "15:00"];
        const lateThu = o.schedule.thu && o.schedule.thu[1] === "19:00";
        h += '<div class="sec"><h3 class="sec-title"><span><i class="ph ph-bank" aria-hidden="true"></i> ' + t("office") + (p.offices.length > 1 ? " " + (i + 1) : "") + '</span><button class="x" data-orm="' + i + '" aria-label="' + t("remove_office") + '" title="' + t("remove_office") + '"><i class="ph ph-trash"></i></button></h3>' +
          '<div class="field"><label class="label" for="site' + i + '">' + t("site") + '</label><select class="input" id="site' + i + '" data-site="' + i + '">' +
          Object.keys(S.sites).map(function (s) { return '<option value="' + esc(s) + '"' + (s === o.site_id ? " selected" : "") + ">" + esc(siteName(s)) + "</option>"; }).join("") +
          '</select><p class="help" style="margin:0">' + t("drag_hint") + "</p></div>" +
          '<div class="field"><span class="label">' + t("days") + '</span><div class="daychips">' +
          DAYS.map(function (d) { return '<button class="daychip" data-day="' + i + ":" + d + '" aria-pressed="' + !!o.schedule[d] + '" title="' + dayName(d) + '" aria-label="' + dayName(d) + '">' + shortDay(d) + "</button>"; }).join("") + "</div></div>" +
          '<div class="row2 field"><div class="field" style="margin:0"><label class="label" for="op' + i + '">' + t("opens") + '</label><input class="input num" type="time" step="1800" id="op' + i + '" data-open="' + i + '" value="' + hrs[0] + '"></div>' +
          '<div class="field" style="margin:0"><label class="label" for="cl' + i + '">' + t("closes") + '</label><input class="input num" type="time" step="1800" id="cl' + i + '" data-close="' + i + '" value="' + hrs[1] + '"></div></div>' +
          sw("late:" + i, lateThu, t("late_thu"), !o.schedule.thu) + sw("acc:" + i, o.wheelchair_accessible !== false, t("accessible")) + "</div>";
      });
      h += '<div class="sec"><div class="addoffice">' + (p.offices.length ? "" : '<div class="empty" style="grid-column:1/-1">' + t("no_offices") + "</div>") +
        '<select class="input" id="newOfficeArea" aria-label="' + t("add_office_in") + '">' + areaOptions(S.newOfficeArea) + '</select>' +
        '<button class="btn sm ghost" id="addOffice"><i class="ph ph-plus"></i>' + t("add_office") + "</button></div></div>";
    }

    if (lever("online") || lever("appointments")) h += '<div class="sec"><h3 class="sec-title">' + t("rules") + "</h3>" +
      sw("online", p.online_enabled, t("online_enabled"), p.online_only) + sw("onlineOnly", p.online_only, t("online_only")) + sw("appt", p.appointment_required, t("appointment"), p.online_only) + "</div>";

    if (lever("protections")) h += protectHTML(p);

    const units = p.mobile_units || [];
    if (lever("mobile_units")) h += '<div class="sec"><h3 class="sec-title"><span>' + t("mobile_units") + '</span><button class="btn sm ghost" id="addUnit"' + (p.online_only ? " disabled" : "") + '><i class="ph ph-plus"></i>' + t("add_unit") + "</button></h3>" +
      (units.length ? units.map(function (u, i) {
        return '<div class="unit"><select class="input" data-u="' + i + ':area" aria-label="' + t("area") + '">' + areaOptions(u.area) + '</select><select class="input" data-u="' + i + ':day" aria-label="' + t("day") + '">' + dayOptions(u.day) + "</select>" +
          '<button class="x" data-urm="' + i + '" aria-label="' + t("remove") + '"><i class="ph ph-trash"></i></button>' +
          '<div class="hours"><input class="input num" type="time" step="1800" data-u="' + i + ':open" value="' + u.open + '" aria-label="' + t("opens") + '"><input class="input num" type="time" step="1800" data-u="' + i + ':close" value="' + u.close + '" aria-label="' + t("closes") + '"></div></div>';
      }).join("") : '<div class="empty">' + t("no_units") + "</div>") + "</div>";

    if (lever("fee") || lever("visits")) h += '<div class="sec"><div class="row2"><div class="field" style="margin:0"><span class="label">' + t("fee") + "</span>" + stepper("data-fee", p.fee_jd, "", t("fee"), 0.5) + "</div>" +
      '<div class="field" style="margin:0"><span class="label">' + t("visits") + "</span>" + stepper("data-visits", p.visits_required, "", t("visits")) + "</div></div></div>";
    if (lever("fuel") || lever("fares") || lever("cash_support")) h += travelPolicyHTML(p);
    else if (lever("transport_vouchers")) h += '<div class="sec">' + voucherHTML(p, true) + "</div>";
    h += '<p class="footnote">' + t("prototype_note") + "</p>";

    const el = $("policyPanel"), sc = el.scrollTop;
    const focusId = document.activeElement && document.activeElement.id;
    el.innerHTML = h; el.scrollTop = sc;
    if (focusId === "nl") { const nl = $("nl"); nl.focus(); nl.setSelectionRange(nl.value.length, nl.value.length); }
  }

  // Group chips for one protection; `on` is the list of selected groups.
  function groupChips(kind, on, dis) {
    return '<div class="gchips">' + PROTECT_GROUPS.map(function (g) {
      return '<button class="gchip" data-gx="' + kind + ":" + g + '" aria-pressed="' + (on.indexOf(g) >= 0) + '"' + (dis ? " disabled" : "") + ">" + esc(groupLabel(g)) + "</button>";
    }).join("") + "</div>";
  }
  function protectHTML(p) {
    const fd = p.fee_discounts || {}, fdGroups = Object.keys(fd), pct = fdGroups.length ? fd[fdGroups[0]] : S.feePct;
    const hv = p.home_visits, inPerson = !p.online_only;
    const pick = '<p class="help" style="margin:0">' + t("pick_group_first") + "</p>";
    let h = '<div class="sec"><h3 class="sec-title"><span><i class="ph ph-hand-heart" aria-hidden="true"></i> ' + t("protect") + "</span></h3>" +
      '<p class="help" style="margin:-4px 0 10px">' + t("protect_help") + "</p>";
    h += '<div class="field"><span class="label">' + t("walkin") + "</span>" + groupChips("exempt", p.appointment_exempt_groups || [], !p.appointment_required || !inPerson) +
      (p.appointment_required ? "" : '<p class="help" style="margin:0">' + t("walkin_help") + "</p>") + "</div>";
    h += '<div class="field"><span class="label">' + t("fee_off") + "</span>" + groupChips("fee", fdGroups) +
      '<div class="row2"><span class="label" style="align-self:center">' + t("fee_pct") + "</span>" + stepper("data-feepct", pct, "%", t("fee_pct")) + "</div>" + (fdGroups.length ? "" : pick) + "</div>";
    h += voucherHTML(p, inPerson);
    h += sw("home", !!hv, t("home_visits"), !inPerson);
    if (hv) h += '<div class="field">' + groupChips("home", hv.groups || []) +
      '<div class="row2"><span class="label" style="align-self:center">' + t("home_slots") + "</span>" + stepper("data-hslots", hv.slots, "", t("home_slots")) + "</div>" +
      '<p class="help" style="margin:0">' + t("home_help") + "</p></div>";
    h += sw("hybrid", !!p.hybrid_pickup, t("hybrid"), !inPerson) + '<p class="help" style="margin:0">' + t("hybrid_help") + "</p>";
    return h + "</div>";
  }

  // Transport voucher (both services): group chips + a JD-per-round-trip stepper; the panel shows the first voucher.
  function voucherHTML(p, enabled) {
    const v = (p.transport_vouchers || [])[0], vGroups = v ? v.groups : [], amt = v ? v.amount_jd : S.voucherJd;
    const pick = '<p class="help" style="margin:0">' + t("pick_group_first") + "</p>";
    return '<div class="field"><span class="label">' + t("voucher") + "</span>" + groupChips("voucher", vGroups, !enabled) +
      '<div class="row2"><span class="label" style="align-self:center">' + t("voucher_amt") + "</span>" + stepper("data-vjd", amt, "", t("voucher_amt")) + "</div>" + (vGroups.length || !enabled ? "" : pick) + "</div>";
  }

  // Everyday travel: fuel price, bus and taxi fares (follow fuel = null, freeze = 0, custom %), cash support, voucher.
  // The pump price line is display only (config.js FUEL_PRICE_90_JD x the change); the engine uses the percentage.
  const signed = function (x) { return (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x); };
  function travelPolicyHTML(p) {
    let h = "";
    if (lever("fuel")) {
      const pct = +p.fuel_price_change_pct || 0, base = CFG.FUEL_PRICE_90_JD || 1.05;
      h += '<div class="sec"><h3 class="sec-title"><span><i class="ph ph-gas-pump" aria-hidden="true"></i> ' + t("fuel") + "</span></h3>" +
        '<div class="row2 field"><span class="label" style="align-self:center">' + t("fuel_change") + "</span>" + stepper("data-fuel", signed(pct), "%", t("fuel_change"), 5) + "</div>" +
        '<p class="fuel-line"><span>' + t("fuel_price_line", { a: '<b class="num">' + base.toFixed(3) + "</b>", arrow: t("arrow"), b: '<b class="num">' + (base * (1 + pct / 100)).toFixed(3) + "</b>" }) + "</span><small>" + t("fuel_price_note") + "</small></p>" +
        '<p class="help" style="margin:0">' + t("fuel_help") + "</p></div>";
    }
    if (lever("fares")) {
      h += '<div class="sec"><h3 class="sec-title"><span><i class="ph ph-bus" aria-hidden="true"></i> ' + t("fares") + "</span></h3>";
      ["bus", "taxi"].forEach(function (m) {
        const v = p[m + "_fare_change_pct"], mode = v == null ? "follow" : +v === 0 ? "freeze" : "custom";
        h += '<div class="field"><span class="label" id="fl_' + m + '">' + t("fare_" + m) + '</span><div class="seg3" role="group" aria-labelledby="fl_' + m + '">' +
          ["follow", "freeze", "custom"].map(function (k) { return '<button data-fare="' + m + ":" + k + '" aria-pressed="' + (mode === k) + '">' + t("fare_" + k) + "</button>"; }).join("") + "</div>" +
          (mode === "custom" ? '<div class="row2"><span class="label" style="align-self:center">' + t("fare_pct") + "</span>" + stepper("data-farepct=\"" + m + "\" data-fstep", signed(+v), "%", t("fare_" + m) + ": " + t("fare_pct"), 5) + "</div>" : "") + "</div>";
      });
      h += '<p class="help" style="margin:0">' + t("fares_help") + "</p></div>";
    }
    if (lever("cash_support") || lever("transport_vouchers")) {
      h += '<div class="sec"><h3 class="sec-title"><span><i class="ph ph-hand-heart" aria-hidden="true"></i> ' + t("protect") + "</span></h3>";
      if (lever("cash_support")) {
        const c = (p.cash_support || [])[0], cGroups = c ? c.groups : [], amt = c ? c.amount_jd_month : S.cashJd;
        h += '<div class="field"><span class="label">' + t("cash") + "</span>" + groupChips("cash", cGroups) +
          '<div class="row2"><span class="label" style="align-self:center">' + t("cash_amt") + "</span>" + stepper("data-cash", amt, "", t("cash_amt"), 2) + "</div>" +
          (cGroups.length ? "" : '<p class="help" style="margin:0">' + t("pick_group_first") + "</p>") + '<p class="help" style="margin:0">' + t("cash_help") + "</p></div>";
      }
      if (lever("transport_vouchers")) h += voucherHTML(p, true);
      h += "</div>";
    }
    return h;
  }

  function renderParse() {
    const P = S.parse;
    if (!P) return "";
    if (P.status === "loading") return '<div class="parse"><h4><i class="ph ph-sparkle"></i>' + t("parsing") + '</h4><div class="skel"></div><div class="skel w60"></div></div>';
    const tpl = P.source === "fallback" ? '<span class="src">' + t("tpl") + "</span>" : "";
    const closeBtn = '<div class="acts"><button class="btn sm ghost" data-parse="cancel">' + t("close") + "</button></div>";
    // A template answer (AI unavailable or not understood): the backend's message says which, so the heading stays neutral.
    if (P.status === "unsupported" && P.source === "fallback") return '<div class="parse bad"><h4><i class="ph ph-info"></i>' + t("parse_note") + tpl + "</h4><p>" + esc(loc(P, "message") || t("not_understood")) + "</p>" + closeBtn + "</div>";
    if (P.status === "unsupported") return '<div class="parse bad"><h4><i class="ph ph-info"></i>' + t("unsupported") + "</h4><p>" + esc(loc(P, "message")) + "</p>" + closeBtn + "</div>";
    if (P.status !== "ok" || !P.policy) return '<div class="parse bad"><h4><i class="ph ph-question"></i>' + t("not_understood") + "</h4>" + closeBtn + "</div>";
    const list = P["changes_" + S.lang] || P.changes_ar || P.changes_en || [];
    return '<div class="parse"><h4><i class="ph ph-list-checks"></i>' + t("understood") + tpl + "</h4><ul>" + list.map(function (c) { return "<li>" + esc(c) + "</li>"; }).join("") +
      '</ul><div class="acts"><button class="btn sm accent" data-parse="apply"><i class="ph ph-check"></i>' + t("apply") + '</button><button class="btn sm ghost" data-parse="cancel">' + t("cancel") + "</button></div></div>";
  }

  async function runParse() {
    const txt = ($("nl") && $("nl").value || S.text || "").trim();
    S.text = txt;
    if (!txt) return;
    S.parse = { status: "loading" }; renderPolicy();
    try { S.parse = await API.parse(txt, S.policy, S.lang); }
    catch (e) { S.parse = { status: "fail" }; toastErr(e); }
    renderPolicy();
    refreshLlm();
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
  // Map framing: the central ~90% of residents (5th-95th percentile of lat and lng), so a few far homes
  // don't shrink the city. Falls back to the area centroids.
  function homeBounds() {
    const lat = [], lng = [];
    S.pop.forEach(function (c) { if (isFinite(c.lat) && isFinite(c.lng)) { lat.push(c.lat); lng.push(c.lng); } });
    if (lat.length < 20) {
      const pts = Object.keys(S.areas).map(function (k) { return [S.areas[k].lat, S.areas[k].lng]; });
      return pts.length ? L.latLngBounds(pts).pad(0.15) : null;
    }
    const q = function (a, p) { a.sort(function (x, y) { return x - y; }); return a[Math.min(a.length - 1, Math.max(0, Math.round(p * (a.length - 1))))]; };
    return L.latLngBounds([q(lat, 0.05), q(lng, 0.05)], [q(lat, 0.95), q(lng, 0.95)]);
  }
  function initMap() {
    if (map) return;
    map = L.map("map", { zoomControl: false, attributionControl: true, minZoom: 10, maxZoom: 17 });
    const b = homeBounds();
    if (b) map.fitBounds(b, { paddingTopLeft: [10, 70], paddingBottomRight: [10, 90], maxZoom: 14 });
    else map.setView([31.975, 35.91], 12);
    setTiles();
    const r = L.svg({ padding: 0.4 });
    areaLayer = L.layerGroup().addTo(map);
    siteLayer = L.layerGroup().addTo(map);
    labelLayer = L.layerGroup().addTo(map);
    dotLayer = L.layerGroup().addTo(map);
    ringLayer = L.layerGroup().addTo(map);
    pinLayer = L.layerGroup().addTo(map);
    // Offline: no tiles, so each area gets a visible 1.6 km zone (drawn first, below the dots).
    if (CFG.OFFLINE_MAP) Object.keys(S.areas).forEach(function (k) { const a = S.areas[k]; L.circle([a.lat, a.lng], { radius: 1600, className: "area-zone", interactive: false, renderer: r }).addTo(areaLayer); });
    const heroIds = new Set(S.heroes.map(function (h) { return h.id; }));
    S.pop.forEach(function (c) {
      const hero = heroIds.has(c.id);
      const m = L.circleMarker([c.lat, c.lng], { radius: hero ? 7 : 4, weight: hero ? 2.5 : 0.8, opacity: 1, fillOpacity: 0.92, className: "dot served", renderer: r, bubblingMouseEvents: false });
      m.on("click", function () { if (S.service) select(c.id); });
      m.addTo(dotLayer); dots.set(c.id, m);
    });
    Object.keys(S.sites).forEach(function (k) {
      const s = S.sites[k];
      L.marker([s.lat, s.lng], { icon: L.divIcon({ className: "", html: '<div class="site-mark"></div>', iconSize: [12, 12], iconAnchor: [6, 6] }), interactive: false, keyboard: false }).addTo(siteLayer);
    });
    if (S.service !== "id_renewal") map.removeLayer(siteLayer);   // office sites: ID renewal only
    map.on("zoomend", declutterLabels);
    renderLabels(); placeZoom();
  }
  // After a service switch: the hero dots of the new service are drawn larger, and office sites show only for ID renewal.
  function styleDots() {
    if (!map) return;
    const heroIds = new Set(S.heroes.map(function (h) { return h.id; }));
    dots.forEach(function (m, id) { const hero = heroIds.has(id); m.setRadius(hero ? 7 : 4); m.setStyle({ weight: hero ? 2.5 : 0.8 }); });
    if (S.service !== "id_renewal") map.removeLayer(siteLayer); else if (!map.hasLayer(siteLayer)) siteLayer.addTo(map);
  }
  function placeZoom() {
    if (!map) return;
    if (zoom) map.removeControl(zoom);
    zoom = L.control.zoom({ position: S.lang === "ar" ? "bottomleft" : "bottomright", zoomInTitle: t("zoom_in"), zoomOutTitle: t("zoom_out") }).addTo(map);
  }
  // Area labels sit just below the area's centroid or its southernmost office site, whichever is lower:
  // office pins grow upwards from their site, so they don't cover the label.
  function renderLabels() {
    if (!labelLayer) return;
    labelLayer.clearLayers();
    Object.keys(S.areas).forEach(function (k) {
      const a = S.areas[k];
      const lat = Object.keys(S.sites).reduce(function (m, s) { return S.sites[s].area === k ? Math.min(m, S.sites[s].lat) : m; }, a.lat);
      L.marker([lat, a.lng], { icon: L.divIcon({ className: "", html: '<div class="area-label">' + esc(areaName(k)) + "</div>", iconSize: [0, 0] }), interactive: false, keyboard: false, zIndexOffset: -500 }).addTo(labelLayer);
    });
    declutterLabels();
  }

  // Layout only: nudge an area label downwards while it overlaps an office pin or another label.
  function declutterLabels() {
    const hit = function (a, b) { return !(a.right < b.left || a.left > b.right || a.bottom < b.top || a.top > b.bottom); };
    const pins = Array.prototype.map.call(document.querySelectorAll("#map .pin, #map .van"), function (e) { return e.getBoundingClientRect(); });
    const placed = [];
    document.querySelectorAll("#map .area-label").forEach(function (el) {
      let dy = 10;
      el.style.transform = "translate(-50%, " + dy + "px)";
      for (let i = 0; i < 6; i++) {
        const r = el.getBoundingClientRect();
        if (!pins.concat(placed).some(function (p) { return hit(p, r); })) break;
        dy += 16; el.style.transform = "translate(-50%, " + dy + "px)";
      }
      placed.push(el.getBoundingClientRect());
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
      if (S.reason && !(o.status === S.reasonSt && (o.reasons || []).indexOf(S.reason) >= 0)) cls += " dim";
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
    // Everyday travel has no pins: the dots are the story (offices and vans are ID-renewal levers).
    if (isTravel()) return declutterLabels();
    if (p.online_only) return declutterLabels();
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
        .bindTooltip(esc(t("van_tip", { area: areaName(u.area), day: dayName(u.day), open: u.open, close: u.close })), { direction: "top", offset: [0, -16] }).addTo(pinLayer);
    });
    declutterLabels();
  }
  // Pins snap to sites; the office keeps the site's names so cache keys stay stable (CLAUDE.md §6).
  function snapOffice(o, siteId) {
    const s = S.sites[siteId];
    o.site_id = siteId;
    if (s.area) o.id = "office_" + s.area;
    o.name_ar = s.name_ar; o.name_en = s.name_en;
  }

  // The drawer is capped above the hero bar so the heroes stay clickable (CSS reads --heroes-h).
  function syncHeroesHeight() {
    const hb = $("heroes"), mw = $("mapwrap");
    mw.style.setProperty("--heroes-h", (hb.hidden ? 0 : hb.offsetHeight) + "px");
  }

  function renderMapTools() {
    if (!S.cmp) return;
    $("viewSeg").hidden = false; $("legend").hidden = false;
    $("viewSeg").setAttribute("aria-label", t("map_before") + " / " + t("map_after"));
    $("viewSeg").innerHTML = ["before", "after"].map(function (v) { return '<button data-view="' + v + '" aria-pressed="' + (S.view === v) + '"' + (v === "before" && !changed() ? " disabled" : "") + ">" + t("map_" + v) + "</button>"; }).join("");
    const k = viewSim().counts;
    let rings = "";
    if (S.view === "after" && S.cmpFix && S.cmpFix.flipped_better.length) rings = '<span class="lg-div"></span><span class="lg rings"><span class="sw-ring" style="border-color:var(--served)"></span><b class="num">' + S.cmpFix.flipped_better.length + "</b> " + t("got_better") + "</span>";
    else if (S.view === "after" && S.cmp.flipped_worse.length) rings = '<span class="lg-div"></span><span class="lg rings"><span class="sw-ring"></span><b class="num">' + S.cmp.flipped_worse.length + "</b> " + t("got_worse") + "</span>";
    $("legend").innerHTML = ["served", "hardship", "left_out"].map(function (s) { return '<span class="lg"><span class="sw-dot ' + s + '"></span>' + ts(s) + ' <b class="num">' + int(k[s] || 0) + "</b></span>"; }).join("") + rings;
    $("filterSlot").innerHTML = S.reason ? '<div class="float filter-chip"><i class="ph ph-funnel"></i>' + (isTravel() ? ts(S.reasonSt) + ": " : "") + t("r_" + S.reason) + '<button data-clear-reason>' + t("clear_filter") + "</button></div>" : "";
    const sim = viewSim();
    $("heroes").hidden = !S.heroes.length;
    $("heroes").innerHTML = '<p class="heroes-title">' + t("heroes") + '</p><div class="hero-list">' + S.heroes.map(function (h) {
      const c = S.byId.get(h.id), o = sim.byId.get(h.id) || { status: "served" };
      return '<button class="hero-btn" data-hero="' + esc(c.id) + '" aria-pressed="' + (S.sel === c.id) + '" title="' + esc(loc(h, "note")) + '"><span class="avatar ' + o.status + '">' + esc(initial(c)) + "</span>" + esc(name(c)) + "</button>";
    }).join("") + "</div>";
    syncHeroesHeight();
  }

  /* ---------------- citizen drawer ---------------- */
  function select(id) { S.sel = id; renderDrawer(); updateMap(); renderMapTools(); loadVoice(); }

  const voiceKey = function (id, o) { return id + "|" + canon(o); };
  // POST /citizen/voice with the policy whose outcome the card shows; the backend recomputes the outcome.
  // A failure is shown with a Retry button and is not kept: the next load tries again.
  async function loadVoice() {
    if (!S.sel || !S.cmp) return;
    const id = S.sel, o = viewSim().byId.get(id);
    if (!o) return;
    const key = voiceKey(id, o), cur = S.voices.get(key);
    if (cur && cur.status !== "error") return;
    S.voices.set(key, { status: "loading" });
    if (cur) renderDrawer();
    try {
      const r = await API.voice(id, viewPolicy());
      S.voices.set(key, { status: "done", text_ar: r.text_ar, summary_en: r.summary_en, source: r.source });
    } catch (e) {
      console.warn("voice failed", e);
      S.voices.set(key, { status: "error" });
    }
    if (S.sel === id) renderDrawer();
    refreshLlm();
  }

  function statusPill(o, label, current) {
    return '<span class="flow-step' + (current ? " cur" : "") + '"><small>' + label + '</small><span class="pill ' + o.status + '">' + ts(o.status) + "</span></span>";
  }

  // Everyday travel: the citizen's regular trip, every number as the engine sent it (null fields are hidden).
  function tripHTML(o) {
    if (o.channel === "no_regular_trip" || (!o.purpose && !o.channel)) return '<div class="note"><i class="ph ph-info"></i><span>' + t("no_trip") + "</span></div>";
    const fact = function (k, val) { return '<div class="fact"><small>' + t(k) + "</small><b>" + val + "</b></div>"; };
    const has = function (x) { return x != null && isFinite(x); };
    const jd = function (x) { return '<span class="num">' + (+x).toFixed(2) + "</span> " + t("jd"); };
    const facts = [];
    if (o.purpose) facts.push(fact("purpose", '<i class="ph ' + (PURPOSE_ICON[o.purpose] || "ph-dot") + '"></i> ' + t("pur_" + o.purpose)));
    if (loc(o, "channel_name")) facts.push(fact("hub", esc(loc(o, "channel_name"))));
    if (o.mode) facts.push(fact("mode", '<i class="ph ' + (MODE_ICON[o.mode] || "ph-dot") + '"></i> ' + ts("m_" + o.mode) + (o.mode === "bus" ? " <small class=\"num-ish\">(" + tp("transfers", o.bus_transfers || 0) + ")</small>" : "")));
    if (has(o.days_per_week)) facts.push(fact("days_week", '<span class="num">' + o.days_per_week + "</span>"));
    facts.push(fact("travel", '<span class="num">' + Math.round(o.travel_minutes || 0) + "</span> " + t("min")));
    if (has(o.income_share_pct)) facts.push(fact("income_share", '<span class="num">' + f1(o.income_share_pct) + "%</span>"));
    let h = '<div><h4 class="sec-title" style="margin-bottom:8px">' + t("trip") + '</h4><div class="facts">' + facts.join("") + "</div></div>";
    // Monthly cost: before -> after (the extra, signed), as computed by the engine.
    const before = has(o.monthly_cost_before_jd) ? o.monthly_cost_before_jd : null, extra = has(o.extra_jd_month) ? o.extra_jd_month : null;
    let cost = before != null ? '<span class="flow">' + (+before).toFixed(2) + " " + t("arrow") + " " + (+o.cost_jd).toFixed(2) + "</span> " + t("jd") : jd(o.cost_jd);
    if (extra != null && Math.abs(extra) >= 0.005) cost += ' <span class="delta ' + (extra > 0 ? "bad" : "good") + '"><span class="num">' + (extra > 0 ? "+" : "−") + Math.abs(extra).toFixed(2) + "</span></span>";
    const rows = [fact("month_cost", cost)];
    if (has(o.cash_support_jd_month) && o.cash_support_jd_month > 0) rows.push(fact("cash_got", jd(o.cash_support_jd_month)));
    return h + '<div class="facts one">' + rows.join("") + "</div>";
  }

  function renderDrawer() {
    const d = $("drawer");
    if (!S.sel || !S.cmp) { d.hidden = true; return; }
    const c = S.byId.get(S.sel);
    const o = viewSim().byId.get(c.id);
    if (!o) { d.hidden = true; return; }
    // Three steps: today (baseline) -> the policy -> after the fix (when one is applied).
    const oToday = S.cmp.baseline.byId.get(c.id);
    const oPolicy = S.cmpFix ? S.cmpFix.baseline.byId.get(c.id) : S.cmp.scenario.byId.get(c.id);
    const oFix = S.cmpFix ? S.cmpFix.scenario.byId.get(c.id) : null;
    const arrow = '<i class="ph ph-arrow-right flip-rtl" aria-hidden="true"></i>';
    const steps = [statusPill(oToday, t("flow_today"), S.view === "before")];
    if (changed() && oPolicy) steps.push(statusPill(oPolicy, t("flow_policy"), S.view === "after" && !oFix));
    if (oFix) steps.push(statusPill(oFix, t("flow_fix"), S.view === "after"));
    const hero = heroOf(c.id), note = loc(hero, "note");
    const attr = function (icon, txt, neg) { return '<span class="' + (neg ? "neg" : "") + '"><i class="ph ' + icon + '"></i>' + esc(txt) + "</span>"; };
    let h = '<div class="drawer-head"><span class="avatar lg ' + o.status + '">' + esc(initial(c)) + '</span><div><h3>' + esc(name(c)) + '</h3><div class="sub">' + esc(t("age_area", { age: c.age, area: areaName(c.area) })) + "</div>" +
      (note ? '<div class="hero-note">' + esc(note) + "</div>" : "") + '</div><button class="icon-btn" data-close-drawer aria-label="' + t("close") + '"><i class="ph ph-x"></i></button></div><div class="drawer-body">';
    h += '<div class="status-flow">' + steps.join(arrow) + "</div>";
    h += '<div class="attrs">' +
      attr("ph-car-profile", c.has_car ? t("car") : t("no_car_icon"), !c.has_car) +
      attr(c.has_smartphone ? "ph-device-mobile" : "ph-device-mobile-slash", c.has_smartphone ? t("phone") : t("no_phone"), !c.has_smartphone) +
      attr(c.mobility === "wheelchair" ? "ph-wheelchair" : "ph-person-simple-walk", t("mob_" + (c.mobility || "none")), c.mobility && c.mobility !== "none") +
      attr("ph-cursor-click", c.digital_literacy === "low" ? t("lit_low") : t("lit_ok"), c.digital_literacy === "low") +
      attr("ph-briefcase", c.works ? t("works_hours", { s: c.work_start, e: c.work_end }) : t("not_working")) +
      attr("ph-hand-heart", c.has_helper ? t("helper", { h: (S.lang === "ar" ? c.helper_relation_ar : c.helper_relation_en) || "" }) : t("no_helper"), !c.has_helper) +
      "</div>";
    const v = S.voices.get(voiceKey(c.id, o));
    const isTpl = v && v.source !== "ai";
    let body;
    if (v && v.status === "done") body = '<p class="voice-text" lang="ar" dir="rtl">' + esc(v.text_ar) + "</p>" + (S.lang === "en" && v.summary_en ? '<p class="voice-en">' + esc(v.summary_en) + "</p>" : "");
    else if (v && v.status === "error") body = '<div class="voice-err"><span>' + t(gk("voice_failed", c)) + '</span><button class="btn sm ghost" data-voice-retry><i class="ph ph-arrow-clockwise"></i>' + t("retry") + "</button></div>";
    else body = '<div class="skel"></div><div class="skel w60"></div><span class="sr">' + t(gk("voice_loading", c)) + "</span>";
    h += '<div class="voice" aria-live="polite"><div class="voice-meta"><span>' + t(gk("voice_label", c)) + "</span>" + (v && v.status === "done" ? '<span class="src' + (isTpl ? "" : " ai") + '">' + t(isTpl ? "tpl" : "ai") + "</span>" : "") + "</div>" + body + "</div>";
    if (isTravel()) h += tripHTML(o);
    else if (o.status !== "left_out") {
      const fact = function (k, val) { return '<div class="fact"><small>' + t(k) + "</small><b>" + val + "</b></div>"; };
      const facts = [fact("channel", esc(loc(o, "channel_name") || o.channel || "")),
        fact("mode", '<i class="ph ' + (MODE_ICON[o.mode] || "ph-dot") + '"></i> ' + t("m_" + o.mode) + (o.mode === "bus" ? ' <span class="num">(' + ((o.bus_transfers || 0) + 1) + ")</span>" : ""))];
      if (o.mode !== "online" && o.mode !== "home") facts.push(fact("visit_day", o.visit_day ? dayName(o.visit_day) : "-"), fact("travel", '<span class="num">' + Math.round(o.travel_minutes || 0) + "</span> " + t("min")));
      facts.push(fact("hours_lost", '<span class="num">' + f1(o.hours_lost) + "</span> " + t("hrs")), fact("cost", '<span class="num">' + f1(o.cost_jd) + "</span> " + t("jd")));
      h += '<div class="facts">' + facts.join("") + "</div>";
      if (o.work_hours_missed > 0) h += '<div class="facts" style="grid-template-columns:1fr"><div class="fact" style="border:0"><small>' + t("work_missed") + '</small><b><span class="num">' + f1(o.work_hours_missed) + "</span> " + t("hrs") + "</b></div></div>";
    }
    if ((o.reasons || []).length) h += '<div><h4 class="sec-title" style="margin-bottom:8px">' + t("reasons") + '</h4><div class="chips">' + o.reasons.map(function (r) { return '<span class="rchip"><i class="ph ' + (REASON_ICON[r] || "ph-warning") + '"></i>' + t("r_" + r) + "</span>"; }).join("") + "</div></div>";
    h += "</div>";
    const bodyEl = d.querySelector(".drawer-body"), sc = bodyEl ? bodyEl.scrollTop : 0, sameCitizen = d.dataset.cid === c.id;
    d.innerHTML = h; d.hidden = false; d.dataset.cid = c.id;
    if (sameCitizen) d.querySelector(".drawer-body").scrollTop = sc;
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
    const tab = function (id, icon, label, dis, extra) {
      return '<button class="tab" role="tab" id="tab-' + id + '" data-tab="' + id + '" aria-controls="impactPanel" aria-selected="' + (S.tab === id) + '" tabindex="' + (S.tab === id ? 0 : -1) + '"' + (dis ? " disabled" : "") + '><i class="ph ' + icon + '"></i>' + label + (extra || "") + "</button>";
    };
    $("tabs").hidden = false;
    $("tabs").innerHTML = tab("impact", "ph-chart-bar-horizontal", t("impact")) + tab("fixes", "ph-wrench", t("fixes"), !S.fixes, nf ? ' <span class="count num">' + nf + "</span>" : "");
    $("impactPanel").setAttribute("aria-labelledby", "tab-" + S.tab);
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
    const R = currentSens();
    const btn = function (cls, icon, title, sub) { return '<button class="robust ' + cls + '" data-modal="assumptions"><i class="' + icon + '"></i><span><b>' + title + "</b><small>" + sub + '</small></span><i class="ph ph-caret-right go flip-rtl"></i></button>'; };
    if (!R) return btn("idle", "ph ph-shield", t("robust_check"), t("robust_check_sub"));
    if (R.status === "checking") return btn("checking", "ph ph-circle-notch", t("robust_checking"), t("robust_check_sub"));
    if (R.status === "error") return btn("partial", "ph-fill ph-shield-warning", t("robust_failed"), t("robust_hint"));
    const r = R.res, held = r.ranking_held, n = r.runs;
    let title = t(held === n ? "robust_ok" : "robust_partial", { h: held, n: n });
    if (R.hasFix) title += " " + t("robust_fix", { f: r.fix_still_helps, n: n });
    let sub = R.hasFix ? t("robust_hint") : t("robust_rank_only");
    if (held < n && !r.stable_top_group && r.stable_top2 && r.stable_top2.length === 2) sub = t("robust_pair", { a: groupLabel(r.stable_top2[0]), b: groupLabel(r.stable_top2[1]) });
    const ok = R.hasFix ? r.passed : held === n;
    return btn(ok ? "" : "partial", "ph-fill " + (ok ? "ph-shield-check" : "ph-shield-warning"), title, sub);
  }

  // KPI value with a short pulse when it changed since the last render (CSS respects reduced motion).
  function kpiVal(id, txt) {
    const k = S.view + "|" + id, prev = S.kpiPrev[k];
    S.kpiPrev[k] = txt;
    return '<div class="kpi-val num' + (prev != null && prev !== txt ? " bump" : "") + '">' + txt + "<small>%</small></div>";
  }

  function impactHTML() {
    const cur = viewSim(), K = cur.kpis, after = S.view === "after", showD = after && changed();
    // After a fix: deltas against the policy before the fix (default), or against today.
    const vsFix = after && !!S.cmpFix && S.deltaRef === "prefix";
    const D = vsFix ? S.cmpFix.kpi_delta : S.cmp.kpi_delta, ref = vsFix ? S.cmpFix.baseline : S.cmp.baseline;
    const n = K.n || (cur.counts ? cur.counts.served + cur.counts.hardship + cur.counts.left_out : 0);
    let h = '<div class="sec"><div class="kpis" aria-live="polite">' + [["pct_served", "served", false], ["pct_hardship", "hardship", true], ["pct_left_out", "left_out", true]].map(function (x) {
      const cnt = cur.counts ? '<div class="kpi-n">' + t("kpi_of", { n: int(cur.counts[x[1]]), t: int(n) }) + "</div>" : "";
      return '<div class="kpi"><div class="kpi-label"><span class="sw-dot ' + x[1] + '"></span>' + ts(x[1]) + "</div>" + kpiVal(x[0], f1(K[x[0]])) + cnt +
        (showD ? delta(D[x[0]], x[2]) : '<span class="delta flat">' + (S.view === "before" ? t("step_baseline") : t("vs_baseline")) + "</span>") + "</div>";
    }).join("") + "</div>";
    if (showD && S.cmpFix) h += '<div class="delta-ref"><span>' + t(vsFix ? "vs_prefix" : "vs_baseline") + '</span><button class="linkbtn" data-delta-ref="' + (vsFix ? "baseline" : "prefix") + '">' + t(vsFix ? "show_vs_today" : "show_vs_prefix") + "</button></div>";
    const hvNow = viewPolicy().home_visits;
    if (hvNow) h += '<div class="kpi-sub kpi-note"><span><i class="ph ph-house-line"></i> ' + t("home_used") + ' <b class="num">' + (K.n_home_visits || 0) + "</b> / " + hvNow.slots + "</span></div>";
    if (isTravel()) h += travelKpisHTML(K, D, showD);
    else h += '<div class="kpi-sub"><span>' + t("avg_hours") + ' <b class="num">' + f1(K.avg_hours_lost) + "</b> " + t("hrs") + " " + (showD ? delta(D.avg_hours_lost, true, t("hrs")) : "") + "</span><span>" + t("avg_cost") + ' <b class="num">' + f1(K.avg_cost_jd) + "</b> " + t("jd") + " " + (showD ? delta(D.avg_cost_jd, true, t("jd")) : "") + "</span></div>";
    // A policy that moves nobody: say so plainly (Nas has no queues or capacity).
    const B = S.cmp.baseline.kpis;
    if (showD && !S.appliedFix && !S.cmp.flipped_worse.length && !S.cmp.flipped_better.length &&
        ["pct_served", "pct_hardship", "pct_left_out"].every(function (x) { return Math.abs(K[x] - B[x]) < 1e-9; }))
      h += '<div class="note"><i class="ph ph-info"></i><span>' + ts("no_change") + "</span></div>";
    if (changed()) h += robustHTML();
    h += "</div>";

    // equity bars: groups the backend returned, known groups first, two hardest-hit on top (the backend's order)
    const worst = changed() ? S.cmp.worst_groups.slice(0, 2) : [];
    const groups = Object.keys(cur.by_group).filter(function (g) { return g !== "all"; }).sort(function (x, y) {
      const wx = worst.indexOf(x), wy = worst.indexOf(y);
      if (wx >= 0 || wy >= 0) return (wx < 0 ? 9 : wx) - (wy < 0 ? 9 : wy);
      const ox = GROUP_ORDER.indexOf(x), oy = GROUP_ORDER.indexOf(y);
      return (ox < 0 ? 99 : ox) - (oy < 0 ? 99 : oy);
    });
    const row = function (g, cls) {
      const s = cur.by_group[g], bb = ref.by_group[g] || s, bad = s.left_out + s.hardship, d = bad - (bb.left_out + bb.hardship);
      return '<div class="eq ' + (cls || "") + '"><span class="name">' + (g === "all" ? t("everyone") : esc(groupLabel(g))) + (worst.indexOf(g) >= 0 && after ? ' <span class="worst-tag">' + t("worst") + "</span>" : "") + "</span>" +
        '<span class="bar" role="img" aria-label="' + f1(s.served) + "% / " + f1(s.hardship) + "% / " + f1(s.left_out) + '%"><i class="s" style="width:' + s.served + '%"></i><i class="h" style="width:' + s.hardship + '%"></i><i class="l" style="width:' + s.left_out + '%"></i></span>' +
        '<span class="v num">' + f1(bad) + "%" + (showD && Math.abs(d) >= 0.05 ? '<small class="' + (d > 0 ? "delta bad" : "delta good") + '">' + (d > 0 ? "+" : "−") + f1(Math.abs(d)) + "</small>" : "") + "</span></div>";
    };
    h += '<div class="sec"><h3 class="sec-title"><span>' + t("equity") + '</span><button class="info-btn" data-glossary aria-label="' + esc(t("glossary_btn")) + '" title="' + esc(t("glossary_btn")) + '"><i class="ph ph-info"></i></button></h3>' + row("all", "all") + groups.map(function (g) { return row(g); }).join("") +
      '<div class="eq-legend"><span><span class="sw-dot hardship"></span>' + ts("hardship") + '</span><span><span class="sw-dot left_out"></span>' + ts("left_out") + "</span><span>% = " + ts("hardship") + " + " + ts("left_out") + "</span></div></div>";

    // Who is left out, by reason. Everyday travel lists the priced out and the squeezed, each by reason.
    if (!isTravel()) return h + '<div class="sec"><h3 class="sec-title"><span>' + t("who_left") + '</span><span class="num-ish" style="color:var(--left-ink)">' + tp("people", cur.counts ? cur.counts.left_out : 0) + "</span></h3>" + reasonsHTML(cur, "left_out") + "</div>";
    const nL = cur.counts ? cur.counts.left_out : 0, nH = cur.counts ? cur.counts.hardship : 0;
    h += '<div class="sec"><h3 class="sec-title"><span>' + ts("who_left") + "</span></h3>";
    if (!nL && !nH && !Object.keys(K.left_out_by_reason || {}).length && !Object.keys(K.hardship_by_reason || {}).length) h += '<div class="ok-note"><i class="ph ph-check-circle"></i>' + ts("nobody_left") + "</div>";
    else [["left_out", nL, "--left-ink"], ["hardship", nH, "--hardship-ink"]].forEach(function (x) {
      h += '<h4 class="sub-title"><span><span class="sw-dot ' + x[0] + '"></span>' + ts(x[0]) + '</span><span class="num-ish" style="color:var(' + x[2] + ')">' + tp("people", x[1]) + "</span></h4>" + reasonsHTML(cur, x[0], true);
    });
    if (Object.keys(K.left_out_by_reason || {}).length || Object.keys(K.hardship_by_reason || {}).length) h += '<p class="help">' + t("several_reasons") + "</p>";
    h += breakdownHTML(K);
    return h + "</div>";
  }

  // Reasons for one status, from the backend's kpis.<status>_by_reason (people per reason; an older backend:
  // counted from the outcomes). The small line under each reason names the two groups most present among
  // those people (a display count, not a score). Clicking a reason filters the map.
  function reasonsHTML(cur, status, quiet) {
    const K = cur.kpis, byReason = K[status + "_by_reason"];
    const counts = {}, tagsBy = {};
    S.pop.forEach(function (c) {
      const o = cur.byId.get(c.id);
      if (!o || o.status !== status) return;
      (o.reasons || []).forEach(function (r) {
        if (!byReason) counts[r] = (counts[r] || 0) + 1;   // older backend: count here
        tagsBy[r] = tagsBy[r] || {};
        (c.tags || []).forEach(function (g) { if (g !== "student") tagsBy[r][g] = (tagsBy[r][g] || 0) + 1; });
      });
    });
    if (byReason) Object.keys(byReason).forEach(function (r) { if (+byReason[r] > 0) counts[r] = +byReason[r]; });
    const keys = Object.keys(counts).sort(function (a, b2) { return counts[b2] - counts[a] || (a < b2 ? -1 : 1); });
    const n = cur.counts ? cur.counts[status] : 0;
    if (!keys.length) return quiet ? "" : '<div class="ok-note"><i class="ph ph-check-circle"></i>' + t("nobody_left") + "</div>";
    let h = '<div class="reasons">' + keys.map(function (r) {
      const tb = tagsBy[r] || {};
      const top = Object.keys(tb).sort(function (a, b2) { return tb[b2] - tb[a]; }).slice(0, 2).map(groupLabel).join(t("list_sep"));
      return '<button class="reason" data-reason="' + esc(r) + '" data-rst="' + status + '" aria-pressed="' + (S.reason === r && S.reasonSt === status) + '"><i class="ph ' + (REASON_ICON[r] || "ph-warning") + '"></i><span><b>' + t("r_" + r) + "</b><small>" + esc(top) + '</small></span><span class="n num">' + int(counts[r]) + "</span></button>";
    }).join("") + "</div>";
    const sum = keys.reduce(function (a, r) { return a + counts[r]; }, 0);
    if (sum > n && !quiet) h += '<p class="help">' + t("several_reasons") + "</p>";
    return h;
  }

  // Everyday-travel money readouts, each shown only when the kpis carry it.
  function travelKpisHTML(K, D, showD) {
    const has = function (x) { return typeof K[x] === "number" && isFinite(K[x]); };
    const dd = function (x, unit) { return showD && typeof D[x] === "number" ? " " + delta(D[x], true, unit) : ""; };
    const items = [];
    if (has("avg_monthly_cost_jd")) items.push("<span>" + t("avg_month_cost") + ' <b class="num">' + f1(K.avg_monthly_cost_jd) + "</b> " + t("jd_month") + dd("avg_monthly_cost_jd", t("jd")) + "</span>");
    else items.push("<span>" + t("avg_month_cost") + ' <b class="num">' + f1(K.avg_cost_jd) + "</b> " + t("jd_month") + (showD ? " " + delta(D.avg_cost_jd, true, t("jd")) : "") + "</span>");
    if (has("avg_extra_jd_month") && showD) items.push("<span>" + t("extra_month") + ' <b class="num">' + (K.avg_extra_jd_month > 0.005 ? "+" : K.avg_extra_jd_month < -0.005 ? "−" : "") + Math.abs(K.avg_extra_jd_month).toFixed(2) + "</b> " + t("jd") +
      (has("total_extra_jd_month") && Math.abs(K.total_extra_jd_month) >= 0.5 ? ' <small class="num-ish">(' + t("total_extra", { x: (K.total_extra_jd_month > 0 ? "+" : "−") + int(Math.abs(K.total_extra_jd_month)) }) + ")</small>" : "") + "</span>");
    if (has("avg_income_share_pct")) items.push("<span>" + t("avg_share") + ' <b class="num">' + f1(K.avg_income_share_pct) + "%</b>" + dd("avg_income_share_pct") + "</span>");
    const cs = viewPolicy().cash_support || [];
    if (has("n_cash_support") && (K.n_cash_support > 0 || cs.length)) items.push('<span><i class="ph ph-hand-coins"></i> ' + t("n_support") + ' <b class="num">' + int(K.n_cash_support) + "</b></span>");
    return '<div class="kpi-sub wrap">' + items.join("") + "</div>";
  }

  // kpis.by_purpose / by_mode: {key: {served, hardship, left_out}} (percent, drawn as bars) or {key: number}
  // (shown as is). Unknown shapes are skipped.
  function breakdownHTML(K) {
    let h = "";
    [["by_purpose", "pur_"], ["by_mode", "m_"]].forEach(function (b) {
      const src = K[b[0]];
      if (!src || typeof src !== "object") return;
      const rows = Object.keys(src).map(function (k) {
        const v = src[k], label = DICT.en[b[1] + k] ? ts(b[1] + k) : k;
        if (typeof v === "number") return '<div class="eq"><span class="name">' + esc(label) + '</span><span></span><span class="v num">' + int(v) + "</span></div>";
        if (!v || typeof v !== "object" || !("served" in v || "hardship" in v || "left_out" in v)) return "";
        const s = +v.served || 0, hd = +v.hardship || 0, l = +v.left_out || 0, pct = Math.abs(s + hd + l - 100) < 1.5;
        const tot = s + hd + l || 1, w = function (x) { return pct ? x : x / tot * 100; };
        const n = v.n != null ? +v.n : pct ? null : s + hd + l;
        return '<div class="eq"><span class="name">' + esc(label) + (n != null ? ' <small class="num-ish">' + int(n) + "</small>" : "") + '</span><span class="bar"><i class="s" style="width:' + w(s) + '%"></i><i class="h" style="width:' + w(hd) + '%"></i><i class="l" style="width:' + w(l) + '%"></i></span>' +
          '<span class="v num">' + f1(w(hd) + w(l)) + "%</span></div>";
      }).join("");
      if (rows) h += '<h4 class="sub-title"><span>' + t(b[0]) + "</span></h4>" + rows;
    });
    return h;
  }

  // "left out 9 → 1" (the arrow follows the reading direction; the span is bidi-isolated).
  const flow = function (a, b) { return '<span class="flow">' + int(a) + " " + t("arrow") + " " + int(b) + "</span>"; };
  // A drop in percentage points: positive = fewer people (good, shown with a minus), negative = a rise.
  function dropHTML(d, label) {
    const v = Math.abs(d) < 0.05 ? 0 : d;
    const cls = v > 0 ? "good" : v < 0 ? "bad" : "flat";
    return '<span><b class="num ' + cls + '">' + (v > 0 ? "−" : v < 0 ? "+" : "") + f1(Math.abs(v)) + "</b>" + t("pts") + " " + label + "</span>";
  }
  // The AI fix's explanation: the backend appends its template sentence after " — "; show only the AI's rationale.
  const aiRationale = function (s) { const i = String(s || "").indexOf(" — "); return i > 0 ? s.slice(0, i) : s; };

  function fixCard(fx, i) {
    const F = S.fixes, isAI = fx.source === "ai_proposed", applied = S.appliedFix && S.appliedFix.id === fx.id;
    const ex = isAI ? aiRationale(loc(fx, "explanation")) : loc(fx, "explanation");
    const aiPending = F.ai.status === "thinking";
    const exSrc = fx._explainSource || F.ai.source;
    let exHTML = "";
    if (ex) exHTML = '<p class="explain">' + esc(ex) + '<span class="src' + (exSrc === "fallback" ? "" : " ai") + '">' + t(exSrc === "fallback" ? "tpl" : "ai") + "</span></p>";
    else if (aiPending) exHTML = '<div class="skel"></div><div class="skel w60" style="margin-bottom:12px"></div>';
    const a = F.scenKpis && F.scenKpis.counts, b = fx.kpis && fx.kpis.counts;
    const counts = a && b ? '<div class="fix-counts"><span>' + ts("left_out") + " " + flow(a.left_out, b.left_out) + '</span><span class="dotsep" aria-hidden="true">·</span><span>' + ts("hardship") + " " + flow(a.hardship, b.hardship) + "</span></div>" : "";
    const nch = fx.n_changes ? '<span class="nchg">' + tp("changes", fx.n_changes) + "</span>" : "";
    return '<article class="fix' + (isAI ? " ai" : "") + (applied ? " applied" : "") + '" style="animation-delay:' + (i * 70) + 'ms">' +
      '<div class="fix-top"><span class="prov"><i class="ph-fill ' + (isAI ? "ph-sparkle" : "ph-check-circle") + '"></i>' + t(isAI ? "badge_ai" : "badge_engine") + "</span>" + nch + "</div>" +
      '<h4 class="fix-title">' + esc(loc(fx, "title")) + "</h4>" +
      '<div class="drops">' + dropHTML(fx.left_out_drop, ts("left_drop")) + dropHTML(fx.hardship_drop, ts("hard_drop")) + "</div>" + counts +
      exHTML +
      '<div class="fix-acts">' + (applied ? '<span class="applied-note"><i class="ph-fill ph-check-circle"></i>' + t("applied") + '</span><button class="btn sm ghost" data-unfix><i class="ph ph-arrow-counter-clockwise"></i>' + t("cancel") + "</button>"
        : '<span></span><button class="btn sm ' + (isAI ? "accent" : "") + '" data-fix="' + esc(fx.id) + '"><i class="ph ph-check"></i>' + t("apply_fix") + "</button>") + "</div></article>";
  }

  // What happened to the AI's own idea, from /fixes ai_proposal.status. Never "didn't beat" when the AI never answered.
  function aiNoteHTML(F) {
    if (F.ai.status === "thinking") return '<div class="ai-wait"><i class="ph-fill ph-sparkle"></i>' + t("ai_thinking") + "</div>";
    if (F.ai.status === "error") return '<div class="ai-hidden">' + t("ai_failed") + "</div>";
    if (F.ai.fix) return fixCard(F.ai.fix, F.list.length);
    const st = F.ai.proposal && F.ai.proposal.status;
    if (st === "shown") return "";
    if (st && DICT.en["ai_st_" + st]) return '<div class="ai-hidden">' + t("ai_st_" + st) + "</div>";
    // An older backend without ai_proposal: a template answer means the AI never answered.
    return '<div class="ai-hidden">' + t(F.ai.source === "fallback" ? "ai_st_ai_unavailable" : "ai_st_hidden_not_better") + "</div>";
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
    if (!F.list.length) return h + '<div class="ai-hidden">' + t(scenarioPolicy().online_only ? "fixes_online_only" : "fixes_none") + "</div></div>";
    h += '<div class="fix-status"><i class="ph ph-cpu"></i>' + t("fixes_done_n", { n: F.list.length, s: (F.ms / 1000).toFixed(1) }) + "</div>";
    F.list.forEach(function (fx, i) { h += fixCard(fx, i); });
    h += aiNoteHTML(F);
    return h + "</div>";
  }

  function renderActions() {
    const can = changed() || S.appliedFix;
    $("actions").hidden = false;
    $("actions").innerHTML = '<button class="btn accent" id="fixBtn"' + (can ? "" : " disabled") + '><i class="ph ph-wrench"></i>' + t("suggest_fixes") + "</button>" +
      '<button class="btn ghost" id="reportBtn"' + (can ? "" : " disabled") + '><i class="ph ph-file-text"></i>' + t("report") + "</button>";
  }

  /* ---------------- fixes flow: /fixgrid first (instant), then /fixes (AI) ---------------- */
  async function startFixes(force) {
    const scen = scenarioPolicy(), key = canon(scen);
    S.tab = "fixes";
    if (!force && S.fixes && S.fixes.key === key && S.fixes.status !== "error") { renderImpact(); return; }
    const localKpis = S.appliedFix ? S.preKpis : S.cmp.scenario.kpis;
    S.fixes = { status: "searching", key: key };
    renderImpact();
    const t0 = performance.now();
    let g;
    try { g = await API.fixgrid(S.baseline, scen); }
    catch (e) { if (S.fixes && S.fixes.key === key) { S.fixes = { status: "error", key: key }; renderImpact(); } toastErr(e); return; }
    if (!S.fixes || S.fixes.key !== key) return;
    const list = g.list;
    S.fixes = { status: "ready", key: key, list: list, ms: performance.now() - t0, scenKpis: g.scenarioKpis || localKpis, ai: { status: "thinking" } };
    autoSensitivity();
    renderImpact();
    if (!list.length) { S.fixes.ai = { status: "done", fix: null, proposal: { status: "no_grid_fixes" } }; return; }

    // Before/after counts come with each fix (fix.kpis). An older backend leaves them out: ask /simulate then.
    const withKpis = function (fx) { return fx.kpis ? Promise.resolve() : API.simulate(fx.policy).then(function (r) { fx.kpis = r.kpis; }).catch(function () { /* counts stay hidden */ }); };
    if (list.some(function (fx) { return !fx.kpis; })) Promise.all(list.map(withKpis)).then(function () { if (S.fixes && S.fixes.key === key) renderImpact(); });

    try {
      const r = await API.fixes(S.baseline, scen);
      if (!S.fixes || S.fixes.key !== key) return;
      r.fixes.forEach(function (ef) {
        const gf = list.find(function (x) { return x.id === ef.id; });
        if (gf) { gf.explanation_ar = ef.explanation_ar; gf.explanation_en = ef.explanation_en; gf._explainSource = ef.explanation_source || r.source; }
      });
      const ai = r.fixes.find(function (x) { return x.source === "ai_proposed"; }) || null;
      S.fixes.ai = { status: "done", fix: ai, source: r.source, proposal: r.ai_proposal };
      renderImpact();
      if (ai) {
        await withKpis(ai);
        renderImpact();
        const card = document.querySelector(".fix.ai");
        if (card && S.tab === "fixes") card.scrollIntoView({ block: "nearest", behavior: reduceMotion ? "auto" : "smooth" });
      }
    } catch (e) {
      console.warn("fixes failed", e);
      if (S.fixes && S.fixes.key === key) { S.fixes.ai = { status: "error" }; renderImpact(); }
    }
    refreshLlm();
  }

  function findFix(id) {
    const F = S.fixes; if (!F || !F.list) return null;
    return F.list.find(function (x) { return x.id === id; }) || (F.ai && F.ai.fix && F.ai.fix.id === id ? F.ai.fix : null);
  }
  function applyFix(id) {
    const fx = findFix(id); if (!fx) return;
    snapshot();
    if (!S.appliedFix) { S.prePolicy = clone(S.policy); S.preKpis = S.cmp.scenario.kpis; }
    S.policy = clone(fx.policy); S.appliedFix = fx; S.view = "after"; S.reason = null; S.deltaRef = "prefix";
    renderSteps(); renderImpact(); renderPolicy();
    scheduleCompare(0);
  }
  function unapplyFix() {
    if (!S.appliedFix) return;
    snapshot();
    S.policy = clone(S.prePolicy); S.appliedFix = null; S.prePolicy = null; S.preKpis = null; S.cmpFix = null;
    renderSteps(); renderImpact(); renderPolicy();
    scheduleCompare(0);
  }

  /* ---------------- modals (focus trapped, focus returns to the opener) ---------------- */
  let modalOpener = null;
  function openModal(html, kind, refresh) {
    const m = $("modal");
    if (m.hidden && !modalOpener) modalOpener = document.activeElement;
    const old = m.querySelector(".modal"), sc = refresh && old ? old.scrollTop : 0;
    m.innerHTML = '<div class="modal" role="dialog" aria-modal="true" aria-labelledby="modalTitle">' + html + "</div>";
    m.hidden = false; S.modal = kind;
    if (refresh) m.querySelector(".modal").scrollTop = sc;
    if (!refresh || !m.contains(document.activeElement)) { const b = m.querySelector("[data-close-modal]"); if (b) b.focus(); }
  }
  function closeModal() {
    $("modal").hidden = true; $("modal").innerHTML = ""; S.modal = null;
    // The opener may have been re-rendered while the modal was open: find its replacement by id or data-* attribute.
    let el = modalOpener;
    if (el && !document.contains(el)) {
      const attr = el.id ? null : Array.prototype.find.call(el.attributes, function (a) { return a.name.indexOf("data-") === 0; });
      el = el.id ? $(el.id) : attr ? document.querySelector("[" + attr.name + (attr.value ? '="' + attr.value + '"' : "") + "]") : null;
    }
    if (el) el.focus();
    modalOpener = null;
  }
  function trapFocus(e) {
    const m = $("modal");
    if (m.hidden) return;
    const f = Array.prototype.filter.call(m.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'), function (x) { return !x.disabled; });
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (!m.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
    else if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  function modalHead(title, sub) { return '<div class="modal-head"><div><h2 id="modalTitle">' + title + "</h2><p>" + sub + '</p></div><button class="icon-btn" data-close-modal aria-label="' + t("close") + '"><i class="ph ph-x"></i></button></div>'; }
  // Assumption values: dicts keyed by income band get translated band labels; units come from i18n.
  const fmtVal = function (v, unit) {
    const u = unit && DICT.en["u_" + unit] != null ? t("u_" + unit) : (unit || "");
    const one = function (x) { return esc(x) + (u ? " " + esc(u) : ""); };
    if (v && typeof v === "object") return Object.keys(v).map(function (k) { return esc(DICT.en["band_" + k] ? t("band_" + k) : k) + ": " + one(v[k]); }).join("<br>");
    return one(v);
  };
  const assumptionLabel = function (key) { const a = S.assumptions.find(function (x) { return x.key === key; }); return a ? (loc(a, "label") || key) : key; };

  function assumptionsModal(refresh) {
    let h = modalHead(t("assumptions"), t("assumptions_sub")) + '<div class="modal-body">';
    const cur = currentSens(), R = cur && cur.status === "done" && cur.res;
    if (cur && cur.status === "checking") h += '<section><h3 class="sec-title">' + t("robust_title") + '</h3><div class="skel"></div><div class="skel w60"></div><span class="sr">' + t("robust_checking") + "</span></section>";
    else if (cur && cur.status === "error") h += '<section><h3 class="sec-title">' + t("robust_title") + '</h3><div class="ai-hidden">' + t("robust_failed") + "</div></section>";
    if (R) {
      const yes = function (ok) { return '<span class="' + (ok ? "ok" : "no") + '">'; };
      h += '<section><h3 class="sec-title">' + t("robust_title") + '</h3><p class="help" style="margin:-4px 0 10px">' + t("robust_body") + "</p><table><tbody>" +
        "<tr><td>" + t("sens_ranking") + '</td><td class="num">' + yes(R.ranking_held === R.runs) + R.ranking_held + "/" + R.runs + "</span></td></tr>" +
        (cur.hasFix ? "<tr><td>" + t("sens_fix") + '</td><td class="num">' + yes(R.fix_still_helps === R.runs) + R.fix_still_helps + "/" + R.runs + "</span></td></tr>" : "<tr><td colspan=2>" + t("robust_rank_only") + "</td></tr>") +
        (R.stable_top_group ? "<tr><td colspan=2>" + t("stable_group", { g: esc(groupLabel(R.stable_top_group)) }) + "</td></tr>" : "") +
        (!R.stable_top_group && R.ranking_held < R.runs && R.stable_top2 && R.stable_top2.length === 2 ? "<tr><td colspan=2>" + t("robust_pair", { a: esc(groupLabel(R.stable_top2[0])), b: esc(groupLabel(R.stable_top2[1])) }) + "</td></tr>" : "") +
        (cur.hasFix ? "<tr><td>" + t("sens_result") + "</td><td>" + yes(R.passed) + t(R.passed ? "passed" : "partial") + "</span></td></tr>" : "") +
        "</tbody></table>";
      const detail = R.detail;
      if (Array.isArray(detail) && detail.length) {
        h += '<table style="margin-top:10px"><thead><tr><th>' + t("run") + "</th><th>" + t("top2") + "</th><th>" + t("fix_helps") + "</th></tr></thead><tbody>" + detail.map(function (d) {
          return "<tr><td>" + esc(assumptionLabel(d.key)) + ' <span class="num">' + (d.factor ? (d.factor > 1 ? "+" : "−") + Math.round(Math.abs(d.factor - 1) * 100) + "%" : "") + "</span></td><td>" + (d.top2 || []).map(groupLabel).join(t("list_sep")) + "</td><td>" + (!cur.hasFix || d.fixHelps == null ? "-" : t(d.fixHelps ? "yes" : "no")) + "</td></tr>";
        }).join("") + "</tbody></table>";
      }
      h += "</section>";
    }
    // Only this service's constants and the shared ones (an older backend sends no service tag: all are shown).
    const rows = S.assumptions.filter(function (a) { return !a.service || a.service === "shared" || a.service === S.service; });
    if (rows.length) {
      h += '<section><h3 class="sec-title">' + t("assumptions") + "</h3><table><thead><tr><th>" + t("col_constant") + "</th><th>" + t("col_value") + "</th><th>" + t("col_tag") + "</th><th>" + t("col_why") + "</th></tr></thead><tbody>" +
        rows.map(function (a) {
          const label = loc(a, "label");
          return "<tr><td>" + (label ? esc(label) + "<br>" : "") + '<code class="num" style="font-size:11px;color:var(--faint)">' + esc(a.key) + '</code></td><td class="num-ish">' + fmtVal(a.value, a.unit) + '</td><td><span class="tagcell' + (a.tag === "ANCHORED" ? " anch" : "") + '">' + esc(a.tag) + "</span></td><td>" + esc(loc(a, "rationale")) + (a.source ? '<br><small style="color:var(--muted)">' + esc(typeof a.source === "object" ? (a.source.name || "") + " " + (a.source.year || "") : (loc(a, "source") || a.source)) + "</small>" : "") + "</td></tr>";
        }).join("") + "</tbody></table></section>";
    }
    openModal(h + "</div>", "assumptions", refresh);
  }

  // Group definitions, with how many synthetic residents carry each tag.
  function glossaryModal() {
    let h = modalHead(t("glossary_title"), t("glossary_sub")) + '<div class="modal-body"><dl class="gloss">';
    GROUP_ORDER.forEach(function (g) {
      // Group sizes come from the backend (by_group[g].n); the population is only a fallback for an old backend.
      const bg = S.cmp && S.cmp.baseline && S.cmp.baseline.by_group && S.cmp.baseline.by_group[g];
      const n = bg && isFinite(bg.n) ? bg.n : S.pop.filter(function (c) { return (c.tags || []).indexOf(g) >= 0; }).length;
      h += "<dt>" + esc(groupLabel(g)) + ' <small class="num-ish">' + tp("people", n) + "</small></dt><dd>" + t("gl_" + g) + "</dd>";
    });
    h += "</dl>";
    // Everyday travel: the two frozen thresholds behind fine / squeezed / priced out (values from /assumptions).
    if (isTravel()) {
      const pct = function (key, fb) { const a = S.assumptions.find(function (x) { return x.key === key; }); return a && isFinite(+a.value) ? String(Math.round(+a.value * 1000) / 10) : fb; };
      const sq = pct("TRANSPORT_SHARE_SQUEEZED", "10"), po = pct("TRANSPORT_SHARE_PRICED_OUT", "20");
      h += '<section><h3 class="sec-title">' + t("gl_thresholds") + '</h3><dl class="gloss">' +
        [["served", t("gl_fine", { p: sq })], ["hardship", t("gl_squeezed", { a: sq, b: po })], ["left_out", t("gl_priced", { p: po })]].map(function (x) {
          return '<dt><span class="sw-dot ' + x[0] + '" style="display:inline-block;margin-inline-end:6px"></span>' + ts(x[0]) + "</dt><dd>" + esc(x[1]) + "</dd>";
        }).join("") + "</dl></section>";
    }
    openModal(h + "</div>", "glossary");
  }

  // POST /report with {baseline, scenario: the policy before the fix, fix: the applied fix's policy or null}.
  // The answer is kept per policy pair; if another modal is open when it arrives, it waits for the next click.
  function reportBody(r, withFix) {
    const paras = function (txt) { return String(txt || "").split(/\n+/).filter(Boolean).map(function (p) { return "<p>" + esc(p) + "</p>"; }).join(""); };
    const tag = function (lang) { return '<span class="src' + (r.source === "fallback" ? "" : " ai") + '">' + DICT[lang][r.source === "fallback" ? "tpl" : "ai"] + "</span>"; };
    return (withFix ? '<p class="help" style="margin:0"><i class="ph ph-check-circle"></i> ' + t("report_with_fix") + "</p>" : "") + '<div class="report-cols">' +
      '<div class="report-col" dir="rtl" lang="ar"><h3><span>' + DICT.ar.lang_self + "</span>" + tag("ar") + "</h3>" + paras(r.summary_ar) + "</div>" +
      '<div class="report-col" dir="ltr" lang="en"><h3><span>' + DICT.en.lang_self + "</span>" + tag("en") + "</h3>" + paras(r.summary_en) + "</div></div>";
  }
  async function reportModal() {
    const scen = scenarioPolicy(), fixP = S.appliedFix ? S.policy : null, key = canon([S.baseline, scen, fixP]);
    const show = function (inner) { openModal(modalHead(ts("report_title"), t("report_sub")) + '<div class="modal-body">' + inner + "</div>", "report", S.modal === "report"); };
    if (S.report && S.report.key === key && S.report.r) return show(reportBody(S.report.r, !!fixP));
    show('<div class="report-cols"><div class="report-col"><div class="skel"></div><div class="skel"></div><div class="skel w60"></div></div><div class="report-col"><div class="skel"></div><div class="skel"></div><div class="skel w60"></div></div></div><span class="sr">' + t("report_loading") + "</span>");
    if (S.report && S.report.key === key && S.report.pending) return;   // already on its way; it renders when it lands
    const entry = { key: key, pending: true };
    S.report = entry;
    try {
      entry.r = await API.report(S.baseline, scen, fixP);
      entry.pending = false;
      if (S.report === entry && S.modal === "report") show(reportBody(entry.r, !!fixP));
    } catch (e) {
      if (S.report === entry) S.report = null;   // a failure isn't kept
      if (S.modal === "report") show('<div class="ai-hidden">' + t("report_failed") + " <code>" + esc(e.message) + "</code></div>");
    }
    refreshLlm();
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
    if (q("#toastRetry")) { $("toast").hidden = true; if (toastMsg.retry) toastMsg.retry(); return; }
    if (q("#langBtn") || q("#langBtn2")) {
      S.lang = S.lang === "ar" ? "en" : "ar"; store.set("nas.lang", S.lang);
      if (!S.service && $("boot").hidden) { renderHome(); renderLabels(); placeZoom(); return; }
      if (!S.cmp) { renderStatic(); renderPolicy(); return $("boot").hidden ? null : bootScreen($("bootRetry") ? "error" : "loading"); }
      renderAll(); renderLabels(); placeZoom();
      if (S.modal === "assumptions") assumptionsModal(true); else if (S.modal === "glossary") glossaryModal(); else if (S.modal === "llm") llmModal(); else if (S.modal === "report") reportModal();
      return;
    }
    if (q("#themeBtn")) {
      S.theme = currentDark() ? "light" : "dark"; store.set("nas.theme", S.theme);
      document.documentElement.setAttribute("data-theme", S.theme); setTiles(); renderStatic(); return;
    }
    if (q("[data-close-modal]") || e.target === $("modal")) return closeModal();
    if (q("#aiChip")) return llmModal();
    if ((el = q("[data-sector]"))) return chooseSector(el.dataset.sector);
    if (q("[data-home]")) return goHome();
    if (!S.cmp) return;
    if ((el = q("[data-preset]"))) return loadPreset(el.dataset.preset);
    if ((el = q("[data-step]"))) {
      const s = el.dataset.step;
      if (s === "baseline") return loadPreset((S.scenarios.find(function (x) { return same(x.policy, S.baseline); }) || S.scenarios[0]).id);
      if (s === "scenario" && S.appliedFix) return unapplyFix();
      return;
    }
    if ((el = q("[data-ex]"))) { S.text = ts("example_" + (+el.dataset.ex + 1)); renderPolicy(); return runParse(); }
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
        else if (id === "home") p.home_visits = on ? { groups: ["disabled", "elderly"], slots: 20 } : null;
        else if (id === "hybrid") p.hybrid_pickup = on;
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
    if ((el = q("[data-gx]"))) {
      const parts = el.dataset.gx.split(":"), kind = parts[0], g = parts[1];
      const toggle = function (list) { const i = list.indexOf(g); if (i >= 0) list.splice(i, 1); else list.push(g); return list; };
      if (kind === "home" && S.policy.home_visits && (S.policy.home_visits.groups || []).length === 1 && S.policy.home_visits.groups[0] === g) return;   // keep at least one group, no re-run
      return edit(function (p) {
        if (kind === "exempt") p.appointment_exempt_groups = toggle((p.appointment_exempt_groups || []).slice());
        else if (kind === "fee") {
          const fd = p.fee_discounts || {}, pct = Object.keys(fd).length ? fd[Object.keys(fd)[0]] : S.feePct;
          if (fd[g] != null) delete fd[g]; else fd[g] = pct;
          p.fee_discounts = fd;
        } else if (kind === "voucher") {
          const v = (p.transport_vouchers || [])[0], gs = toggle(v ? v.groups.slice() : []);
          p.transport_vouchers = gs.length ? [{ groups: gs, amount_jd: v ? v.amount_jd : S.voucherJd }] : [];
        } else if (kind === "cash") {
          const c = (p.cash_support || [])[0], gs = toggle(c ? c.groups.slice() : []);
          p.cash_support = gs.length ? [{ groups: gs, amount_jd_month: c ? c.amount_jd_month : S.cashJd }] : [];
        } else if (kind === "home" && p.home_visits) {
          p.home_visits.groups = toggle((p.home_visits.groups || []).slice());
        }
      }, { now: true });
    }
    // Steppers: with no group chosen (or at a limit) nothing changes, so the policy isn't re-run and an applied fix stays.
    if ((el = q("[data-feepct]"))) {
      const fd = S.policy.fee_discounts || {}, keys = Object.keys(fd), cur = keys.length ? fd[keys[0]] : S.feePct;
      const next = Math.min(100, Math.max(25, cur + 25 * Math.sign(+el.dataset.feepct)));
      S.feePct = next;
      if (!keys.length || next === cur) return renderPolicy();
      return edit(function (p) { Object.keys(p.fee_discounts).forEach(function (g) { p.fee_discounts[g] = next; }); });
    }
    if ((el = q("[data-vjd]"))) {
      const v = (S.policy.transport_vouchers || [])[0], cur = v ? v.amount_jd : S.voucherJd;
      const next = Math.min(20, Math.max(1, cur + Math.sign(+el.dataset.vjd)));
      S.voucherJd = next;
      if (!v || next === cur) return renderPolicy();
      return edit(function (p) { p.transport_vouchers = [{ groups: p.transport_vouchers[0].groups, amount_jd: next }].concat(p.transport_vouchers.slice(1)); });
    }
    // Everyday travel: fuel -50..+100 % (step 5), fares follow / freeze / custom % (custom skips 0, which is a freeze),
    // cash support 0..50 JD a month (step 2; with no group chosen it only sets the next value).
    if ((el = q("[data-fuel]"))) {
      const cur = +S.policy.fuel_price_change_pct || 0, next = Math.min(100, Math.max(-50, cur + 5 * Math.sign(+el.dataset.fuel)));
      if (next === cur) return;
      return edit(function (p) { p.fuel_price_change_pct = next; });
    }
    if ((el = q("[data-fare]"))) {
      const parts = el.dataset.fare.split(":"), m = parts[0], key = m + "_fare_change_pct", cur = S.policy[key] == null ? null : +S.policy[key];
      const next = parts[1] === "follow" ? null : parts[1] === "freeze" ? 0 : (cur != null && cur !== 0 ? cur : S.fareCustom[m] || 10);
      if (next === cur) return;
      return edit(function (p) { p[key] = next; }, { now: true });
    }
    if ((el = q("[data-farepct]"))) {
      const m = el.dataset.farepct, key = m + "_fare_change_pct", cur = +S.policy[key] || 0, step = 5 * Math.sign(+el.dataset.fstep);
      let next = Math.min(100, Math.max(-50, cur + step));
      if (next === 0) next = cur + 2 * step >= -50 && cur + 2 * step <= 100 ? cur + 2 * step : cur;
      if (next === cur) return;
      S.fareCustom[m] = next;
      return edit(function (p) { p[key] = next; });
    }
    if ((el = q("[data-cash]"))) {
      const c = (S.policy.cash_support || [])[0], cur = c ? c.amount_jd_month : S.cashJd;
      const next = Math.min(50, Math.max(0, cur + 2 * Math.sign(+el.dataset.cash)));
      S.cashJd = next;
      if (!c || next === cur) return renderPolicy();
      return edit(function (p) { p.cash_support = [{ groups: p.cash_support[0].groups, amount_jd_month: next }].concat(p.cash_support.slice(1)); });
    }
    if ((el = q("[data-hslots]"))) {
      const hv = S.policy.home_visits; if (!hv) return;
      const next = Math.min(200, Math.max(10, hv.slots + 10 * Math.sign(+el.dataset.hslots)));
      if (next === hv.slots) return;
      return edit(function (p) { p.home_visits.slots = next; });
    }
    if ((el = q("[data-fee]"))) {
      const next = Math.max(0, Math.round((S.policy.fee_jd + +el.dataset.fee) * 10) / 10);
      if (next === S.policy.fee_jd) return;
      return edit(function (p) { p.fee_jd = next; });
    }
    if ((el = q("[data-visits]"))) {
      const next = Math.min(3, Math.max(1, S.policy.visits_required + Math.sign(+el.dataset.visits)));
      if (next === S.policy.visits_required) return;
      return edit(function (p) { p.visits_required = next; });
    }
    if (q("#addOffice")) return edit(function (p) {
      const area = ($("newOfficeArea") && $("newOfficeArea").value) || Object.keys(S.areas)[0];
      S.newOfficeArea = area;
      const ids = Object.keys(S.sites).filter(function (k) { return S.sites[k].area === area; });
      const site = ids.find(function (k) { return k.indexOf("cspd_") === 0; }) || ids[0];
      const ref = p.offices[0];
      const o = { id: "", name_ar: "", name_en: "", site_id: site, wheelchair_accessible: true,
        schedule: ref ? clone(ref.schedule) : { sun: ["08:30", "15:30"], mon: ["08:30", "15:30"], tue: ["08:30", "15:30"], wed: ["08:30", "15:30"], thu: ["08:30", "15:30"] } };
      snapOffice(o, site);
      let id = o.id, n = 2;
      while (p.offices.some(function (x) { return x.id === id; })) id = o.id + "_" + (n++);
      o.id = id;
      p.offices.push(o);
    }, { now: true });
    if ((el = q("[data-orm]"))) return edit(function (p) { p.offices.splice(+el.dataset.orm, 1); }, { now: true });
    if (q("#addUnit")) return edit(function (p) {
      p.mobile_units = p.mobile_units || [];
      const used = p.mobile_units.map(function (u) { return u.area + u.day; });
      const area = Object.keys(S.areas).find(function (a) { return used.indexOf(a + "sat") < 0; }) || Object.keys(S.areas)[0];
      p.mobile_units.push({ area: area, day: "sat", open: "09:00", close: "14:00" });
    }, { now: true });
    if ((el = q("[data-urm]"))) return edit(function (p) { p.mobile_units.splice(+el.dataset.urm, 1); }, { now: true });
    if ((el = q("[data-view]"))) { S.view = el.dataset.view; renderMapTools(); updateMap(); renderImpact(); renderDrawer(); loadVoice(); return; }
    if ((el = q("[data-hero]"))) { const c = S.byId.get(el.dataset.hero); map.flyTo([c.lat, c.lng], Math.max(map.getZoom(), 14), { duration: reduceMotion ? 0 : 0.8 }); return select(c.id); }
    if (q("[data-close-drawer]")) { S.sel = null; renderDrawer(); updateMap(); renderMapTools(); return; }
    if (q("[data-voice-retry]")) return loadVoice();
    if ((el = q("[data-reason]"))) {
      const st = el.dataset.rst || "left_out";
      S.reason = S.reason === el.dataset.reason && S.reasonSt === st ? null : el.dataset.reason; S.reasonSt = st;
      renderMapTools(); updateMap(); renderImpact(); return;
    }
    if (q("[data-clear-reason]")) { S.reason = null; renderMapTools(); updateMap(); renderImpact(); return; }
    if ((el = q("[data-delta-ref]"))) { S.deltaRef = el.dataset.deltaRef; return renderImpact(); }
    if ((el = q("[data-tab]"))) { S.tab = el.dataset.tab; return renderImpact(); }
    if (q("#fixBtn")) return startFixes();
    if (q("#fixBtnRetry")) return startFixes(true);
    if (q("#reportBtn")) return reportModal();
    if ((el = q("[data-fix]"))) return applyFix(el.dataset.fix);
    if (q("[data-unfix]")) return unapplyFix();
    if (q("[data-glossary]")) return glossaryModal();
    if ((el = q("[data-modal]"))) { if ($("modal").hidden) modalOpener = el; runSensitivity(); return assumptionsModal(); }
  });

  document.addEventListener("change", function (e) {
    const el = e.target;
    if (!S.cmp) return;
    if (el.id === "newOfficeArea") { S.newOfficeArea = el.value; return; }
    if (el.dataset.site !== undefined) return edit(function (p) { snapOffice(p.offices[+el.dataset.site], el.value); }, { now: true });
    if (el.dataset.open !== undefined || el.dataset.close !== undefined) {
      const i = +(el.dataset.open !== undefined ? el.dataset.open : el.dataset.close), isOpen = el.dataset.open !== undefined;
      if (!/^\d\d:\d\d$/.test(el.value)) return;
      // The engine rejects a day shorter than an hour (422): check here and keep the old hours instead.
      const sched = clone(S.policy.offices[i].schedule);
      Object.keys(sched).forEach(function (d) { if (isOpen) sched[d][0] = el.value; else if (!(d === "thu" && sched.thu[1] === "19:00")) sched[d][1] = el.value; });
      if (Object.keys(sched).some(function (d) { return !hoursOk(sched[d][0], sched[d][1]); })) { renderPolicy(); return toastMsg(t("err_hours_panel")); }
      return edit(function (p) { p.offices[i].schedule = sched; });
    }
    if (el.dataset.u) {
      const parts = el.dataset.u.split(":"), u = S.policy.mobile_units[+parts[0]];
      if (parts[1] === "open" || parts[1] === "close") {
        if (!/^\d\d:\d\d$/.test(el.value)) return;
        const op = parts[1] === "open" ? el.value : u.open, cl = parts[1] === "close" ? el.value : u.close;
        if (!hoursOk(op, cl)) { renderPolicy(); return toastMsg(t("err_hours_panel")); }
      }
      return edit(function (p) { p.mobile_units[+parts[0]][parts[1]] = el.value; });
    }
  });
  document.addEventListener("input", function (e) { if (e.target.id === "nl") S.text = e.target.value; });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") { if (!$("modal").hidden) closeModal(); else if (S.sel) { S.sel = null; renderDrawer(); updateMap(); renderMapTools(); } }
    if (e.key === "Tab") trapFocus(e);
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && e.target.id === "nl") runParse();
    // Tabs: arrow keys move between them (tablist pattern).
    if ((e.key === "ArrowLeft" || e.key === "ArrowRight") && e.target.getAttribute && e.target.getAttribute("role") === "tab") {
      const tabs = Array.prototype.filter.call(document.querySelectorAll('[role="tab"]'), function (x) { return !x.disabled; });
      if (tabs.length < 2) return;
      const i = tabs.indexOf(e.target), fwd = (e.key === "ArrowRight") !== (S.lang === "ar");
      const next = tabs[(i + (fwd ? 1 : tabs.length - 1)) % tabs.length];
      S.tab = next.dataset.tab; renderImpact();
      const nt = $("tab-" + S.tab); if (nt) nt.focus();
      e.preventDefault();
    }
  });
  window.addEventListener("resize", function () { if (S.cmp) syncHeroesHeight(); });
  if (window.matchMedia) window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () { if (!S.theme) { setTiles(); renderStatic(); } });

  if (S.theme) document.documentElement.setAttribute("data-theme", S.theme);
  boot();
  window.NasApp = { S: S };
})();
