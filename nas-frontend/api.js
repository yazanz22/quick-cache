/* Nas frontend: the ONLY file that knows the backend's URLs and JSON shapes.
   Contract: CLAUDE.md §5 (models) and §7 (routes). If the backend differs, adapt it here and
   keep returning the normalised shapes documented above each function. */
(function (root) {
  "use strict";
  const CFG = root.NAS_CONFIG;
  const qs = new URLSearchParams(location.search);
  const BASE = (qs.get("api") || CFG.API_URL).replace(/\/+$/, "");

  class ApiError extends Error {
    constructor(msg, status, path) { super(msg); this.status = status; this.path = path; }
  }

  async function call(method, path, body) {
    const ctrl = new AbortController();
    const timer = setTimeout(function () { ctrl.abort(); }, CFG.TIMEOUT_MS);
    let res;
    try {
      res = await fetch(BASE + path, {
        method: method, signal: ctrl.signal,
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (e) {
      throw new ApiError(e.name === "AbortError" ? "timeout" : "network", 0, path);
    } finally { clearTimeout(timer); }
    if (!res.ok) {
      let detail = "";
      try { detail = JSON.stringify((await res.json()).detail || ""); } catch (e) { /* not json */ }
      throw new ApiError("HTTP " + res.status + (detail ? " " + detail : ""), res.status, path);
    }
    return res.json();
  }
  const get = function (p) { return call("GET", p); };
  const post = function (p, b) { return call("POST", p, b); };

  /* ---------- normalisers (accept a few reasonable variants) ---------- */
  const arr = function (x, key) { return Array.isArray(x) ? x : (x && Array.isArray(x[key]) ? x[key] : null); };

  // Percentages: the contract says 0-100. If a backend sends 0-1 fractions, scale them.
  function pctScale(vals) {
    const nums = vals.filter(function (v) { return typeof v === "number"; });
    return nums.length && nums.every(function (v) { return v <= 1.0001; }) && nums.some(function (v) { return v > 0; }) ? 100 : 1;
  }

  // Citizen[] (§5). Tags are derived here if the backend left them out.
  function normPopulation(raw) {
    const list = arr(raw, "citizens") || arr(raw, "population") || [];
    return list.map(function (c) {
      if (!Array.isArray(c.tags)) {
        c.tags = [];
        if (c.age >= 65) c.tags.push("elderly");
        if (c.mobility && c.mobility !== "none") c.tags.push("disabled");
        if (c.income_band === "low") c.tags.push("low_income");
        if (!c.has_car) c.tags.push("no_car");
        if (!c.has_smartphone || c.digital_literacy === "low") c.tags.push("offline");
        if (c.works) c.tags.push("worker");
      }
      return c;
    });
  }

  // -> { [site_id]: { id, name_ar, name_en, lat, lng, area } }
  function normSites(raw) {
    const out = {};
    const list = arr(raw, "sites") || (raw && typeof raw === "object" ? Object.keys(raw).map(function (k) { return Object.assign({ id: k }, raw[k]); }) : []);
    list.forEach(function (s) {
      const id = s.id || s.site_id;
      out[id] = { id: id, name_ar: s.name_ar || id, name_en: s.name_en || id, lat: +s.lat, lng: +s.lng, area: s.area || s.area_id || null };
    });
    return out;
  }

  // -> { [area_key]: { name_ar, name_en, lat, lng } }
  function normAreas(raw) {
    const out = {};
    const list = arr(raw, "areas");
    if (list) list.forEach(function (a) { const k = a.id || a.key || a.area; out[k] = { name_ar: a.name_ar, name_en: a.name_en, lat: +a.lat, lng: +a.lng }; });
    else if (raw && typeof raw === "object") Object.keys(raw).forEach(function (k) { const a = raw[k]; out[k] = { name_ar: a.name_ar, name_en: a.name_en, lat: +a.lat, lng: +a.lng }; });
    return out;
  }

  // -> [{ id, name_ar, name_en, note_ar, note_en, policy }]  (baseline first)
  function normScenarios(raw) {
    let list = arr(raw, "scenarios");
    if (!list && raw && typeof raw === "object") list = Object.keys(raw).map(function (k) { return Object.assign({ id: k }, raw[k]); });
    list = (list || []).map(function (s) {
      const policy = s.policy || (s.offices ? s : null);
      return { id: s.id || s.key || s.name, name_ar: s.name_ar || s.title_ar || null, name_en: s.name_en || s.title_en || null,
        note_ar: s.description_ar || s.note_ar || null, note_en: s.description_en || s.note_en || null, policy: policy };
    }).filter(function (s) { return s.policy; });
    list.sort(function (a, b) { return (a.id === "baseline" ? -1 : 0) - (b.id === "baseline" ? -1 : 0); });
    return list;
  }

  // -> [{ key, label_ar, label_en, value, tag, rationale_ar, rationale_en, source }]
  function normAssumptions(raw) {
    let list = arr(raw, "assumptions");
    if (!list && raw && typeof raw === "object") list = Object.keys(raw).map(function (k) { const v = raw[k]; return v && typeof v === "object" && "value" in v ? Object.assign({ name: k }, v) : { name: k, value: v }; });
    return (list || []).map(function (a) {
      return { key: a.name || a.key || a.id, label_ar: a.label_ar || null, label_en: a.label_en || null, value: a.value,
        tag: a.tag || (a.anchored ? "ANCHORED" : "ASSUMPTION"), rationale_ar: a.rationale_ar || a.rationale || "", rationale_en: a.rationale_en || a.rationale || "", source: a.source || null };
    });
  }

  // -> [{ id, note_ar, note_en }]
  function normHeroes(raw) {
    const list = arr(raw, "heroes") || [];
    return list.map(function (h) { return typeof h === "string" ? { id: h } : { id: h.id || h.citizen_id, note_ar: h.note_ar || h.note || null, note_en: h.note_en || h.note || null }; });
  }

  // SimResult -> adds .byId, .counts and scaled percentages. Raw outcome objects are kept as-is
  // because /citizen/voice wants the engine's own outcome back.
  function normSim(sim) {
    const k = Object.assign({}, sim.kpis);
    const s = pctScale([k.pct_served, k.pct_hardship, k.pct_left_out]);
    ["pct_served", "pct_hardship", "pct_left_out"].forEach(function (x) { k[x] = (+k[x] || 0) * s; });
    const byId = new Map();
    const counts = { served: 0, hardship: 0, left_out: 0 };
    (sim.outcomes || []).forEach(function (o) { byId.set(o.citizen_id, o); counts[o.status] = (counts[o.status] || 0) + 1; });
    const by_group = {};
    const g = sim.by_group || {};
    const gs = pctScale([].concat.apply([], Object.keys(g).map(function (t) { return [g[t].served, g[t].hardship, g[t].left_out]; })));
    Object.keys(g).forEach(function (t) { by_group[t] = { served: (+g[t].served || 0) * gs, hardship: (+g[t].hardship || 0) * gs, left_out: (+g[t].left_out || 0) * gs }; });
    by_group.all = { served: k.pct_served, hardship: k.pct_hardship, left_out: k.pct_left_out };
    return { raw: sim, kpis: k, counts: counts, byId: byId, by_group: by_group };
  }

  function normCompare(raw) {
    const b = normSim(raw.baseline), s = normSim(raw.scenario);
    const kpi_delta = {};
    ["pct_served", "pct_hardship", "pct_left_out", "avg_hours_lost", "avg_cost_jd"].forEach(function (x) { kpi_delta[x] = (+s.kpis[x] || 0) - (+b.kpis[x] || 0); });
    return { raw: raw, baseline: b, scenario: s, kpi_delta: kpi_delta,
      flipped_worse: raw.flipped_worse || [], flipped_better: raw.flipped_better || [], worst_groups: raw.worst_groups || [] };
  }

  // FixCandidate (§5). Drops are percentage points, as the contract says.
  function normFix(f) {
    return Object.assign({}, f, { title_ar: f.title_ar || f.id, title_en: f.title_en || f.id, source: f.source || "engine_grid",
      left_out_drop: +f.left_out_drop || 0, hardship_drop: +f.hardship_drop || 0 });
  }
  const fixList = function (raw) { return (arr(raw, "fixes") || arr(raw, "top") || arr(raw, "candidates") || []).map(normFix); };

  /* ---------- endpoints ---------- */
  const API = {
    base: BASE,
    ApiError: ApiError,
    population: function () { return get("/population").then(normPopulation); },
    sites: function () { return get("/sites").then(normSites); },
    scenarios: function () { return get("/scenarios").then(normScenarios); },
    assumptions: function () { return get("/assumptions").then(normAssumptions); },
    // Optional extras, not in §7. The UI falls back to config.js if they 404.
    areas: function () { return get("/areas").then(normAreas); },
    heroes: function () { return get("/heroes").then(normHeroes); },

    simulate: function (policy) { return post("/simulate", { policy: policy }).then(normSim); },
    compare: function (baseline, scenario) { return post("/compare", { baseline: baseline, scenario: scenario }).then(normCompare); },
    fixgrid: function (baseline, scenario) { return post("/fixgrid", { baseline: baseline, scenario: scenario }).then(fixList); },
    // -> { fixes: FixCandidate[], source }  (explanations filled; may include one ai_proposed fix)
    fixes: function (baseline, scenario) { return post("/fixes", { baseline: baseline, scenario: scenario }).then(function (r) { return { fixes: fixList(r), source: r.source || null }; }); },
    // -> SensitivityResult (+ optional .detail[] rows if the backend sends them)
    sensitivity: function (baseline, scenario, fix) { return post("/sensitivity", { baseline: baseline, scenario: scenario, fix: fix }); },
    // -> ParseResult
    parse: function (text, policy, lang) { return post("/policy/parse", { text: text, current_policy: policy, lang: lang }); },
    // -> { text_ar, source }
    voice: function (citizenId, outcome) { return post("/citizen/voice", { citizen_id: citizenId, outcome: outcome }); },
    // -> { summary_ar, summary_en, source }
    report: function (compareRaw, sensitivity) { return post("/report", { compare_result: compareRaw, sensitivity: sensitivity }); },
  };
  root.NasAPI = API;
})(window);
