/* Nas frontend: the ONLY file that knows the backend's URLs and JSON shapes.
   Contract: backend/app/models.py (CLAUDE.md §5) and §7 (routes). If the backend differs, adapt it here and
   keep returning the normalised shapes documented above each function. */
(function (root) {
  "use strict";
  const CFG = root.NAS_CONFIG;
  const qs = new URLSearchParams(location.search);
  const BASE = (qs.get("api") || CFG.API_URL).replace(/\/+$/, "");

  // status: HTTP status (0 = network/timeout). detail: the backend's own message (a string), for 4xx.
  class ApiError extends Error {
    constructor(msg, status, path, detail) { super(msg); this.status = status; this.path = path; this.detail = detail || ""; }
  }

  // FastAPI sends detail as a string (our 422s) or as a list of {msg, loc} (Pydantic validation).
  function detailText(d) {
    if (!d) return "";
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map(function (x) { return x && x.msg ? (Array.isArray(x.loc) ? x.loc.slice(1).join(".") + ": " : "") + x.msg : JSON.stringify(x); }).join("; ");
    return JSON.stringify(d);
  }

  const timeoutFor = function (path) { return (CFG.TIMEOUT_AI_MS && CFG.TIMEOUT_AI_MS[path]) || CFG.TIMEOUT_MS; };

  async function call(method, path, body) {
    const ctrl = new AbortController();
    const timer = setTimeout(function () { ctrl.abort(); }, timeoutFor(path));
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
      try { detail = detailText((await res.json()).detail); } catch (e) { /* not json */ }
      throw new ApiError("HTTP " + res.status + (detail ? " " + detail : ""), res.status, path, detail);
    }
    return res.json();
  }
  const get = function (p) { return call("GET", p); };
  const post = function (p, b) { return call("POST", p, b); };

  /* ---------- normalisers (accept a few reasonable variants) ---------- */
  const arr = function (x, key) { return Array.isArray(x) ? x : (x && Array.isArray(x[key]) ? x[key] : null); };

  // Citizen[] (§5). The backend always sends tags (seed.derive_tags), so nothing is derived here.
  function normPopulation(raw) { return arr(raw, "citizens") || arr(raw, "population") || []; }

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

  // -> [{ id, name_ar, name_en, note_ar, note_en, policy, demo }]  (baseline first)
  function normScenarios(raw) {
    let list = arr(raw, "scenarios");
    if (!list && raw && typeof raw === "object") list = Object.keys(raw).map(function (k) { return Object.assign({ id: k }, raw[k]); });
    list = (list || []).map(function (s) {
      const policy = s.policy || (s.offices ? s : null);
      return { id: s.id || s.key || s.name, name_ar: s.name_ar || s.title_ar || null, name_en: s.name_en || s.title_en || null,
        note_ar: s.description_ar || s.note_ar || null, note_en: s.description_en || s.note_en || null, policy: policy, demo: !!s.demo };
    }).filter(function (s) { return s.policy; });
    list.sort(function (a, b) { return (a.id === "baseline" ? -1 : 0) - (b.id === "baseline" ? -1 : 0); });
    return list;
  }

  // -> [{ key, label_ar, label_en, value, unit, tag, rationale_ar, rationale_en, source, source_ar, source_en }]
  function normAssumptions(raw) {
    let list = arr(raw, "assumptions");
    if (!list && raw && typeof raw === "object") list = Object.keys(raw).map(function (k) { const v = raw[k]; return v && typeof v === "object" && "value" in v ? Object.assign({ name: k }, v) : { name: k, value: v }; });
    return (list || []).map(function (a) {
      return { key: a.name || a.key || a.id, label_ar: a.label_ar || null, label_en: a.label_en || null, value: a.value, unit: a.unit || null,
        tag: a.tag || (a.anchored ? "ANCHORED" : "ASSUMPTION"), rationale_ar: a.rationale_ar || a.rationale || "", rationale_en: a.rationale_en || a.rationale || "", source: a.source || null,
        source_ar: a.source_ar || null, source_en: a.source_en || (typeof a.source === "string" ? a.source : null) };
    });
  }

  // -> [{ id, note_ar, note_en }]
  function normHeroes(raw) {
    const list = arr(raw, "heroes") || [];
    return list.map(function (h) { return typeof h === "string" ? { id: h } : { id: h.id || h.citizen_id, note_ar: h.note_ar || h.note || null, note_en: h.note_en || h.note || null }; });
  }

  // kpis: percentages are 0-100 (the backend always sends 0-100, so nothing is rescaled). Adds
  // .counts {served, hardship, left_out} (people) from the n_* keys, or by counting outcomes on an older backend.
  // left_out_by_reason / hardship_by_reason ({reason: n people}) pass through untouched when present.
  function normKpis(kpis, outcomes) {
    const k = Object.assign({}, kpis || {});
    ["pct_served", "pct_hardship", "pct_left_out", "avg_hours_lost", "avg_cost_jd"].forEach(function (x) { k[x] = +k[x] || 0; });
    let counts = null;
    if (k.n_served != null && k.n_hardship != null && k.n_left_out != null) counts = { served: +k.n_served, hardship: +k.n_hardship, left_out: +k.n_left_out };
    else if (outcomes) { counts = { served: 0, hardship: 0, left_out: 0 }; outcomes.forEach(function (o) { counts[o.status] = (counts[o.status] || 0) + 1; }); }
    k.counts = counts;
    if (k.n == null && counts) k.n = counts.served + counts.hardship + counts.left_out;
    return k;
  }

  // SimResult -> { raw, kpis, counts, byId, by_group }. by_group gets an "all" row from the kpis.
  function normSim(sim) {
    const k = normKpis(sim.kpis, sim.outcomes || []);
    const byId = new Map();
    (sim.outcomes || []).forEach(function (o) { byId.set(o.citizen_id, o); });
    const by_group = {};
    const g = sim.by_group || {};
    Object.keys(g).forEach(function (t) { by_group[t] = { served: +g[t].served || 0, hardship: +g[t].hardship || 0, left_out: +g[t].left_out || 0 }; });
    by_group.all = { served: k.pct_served, hardship: k.pct_hardship, left_out: k.pct_left_out };
    return { raw: sim, kpis: k, counts: k.counts, byId: byId, by_group: by_group };
  }

  // CompareResult. kpi_delta: the backend's numbers when present, else scenario minus baseline of the two kpis.
  function normCompare(raw) {
    const b = normSim(raw.baseline), s = normSim(raw.scenario);
    const kpi_delta = {}, D = raw.kpi_delta || {};
    ["pct_served", "pct_hardship", "pct_left_out", "avg_hours_lost", "avg_cost_jd"].forEach(function (x) { kpi_delta[x] = typeof D[x] === "number" ? D[x] : s.kpis[x] - b.kpis[x]; });
    return { raw: raw, baseline: b, scenario: s, kpi_delta: kpi_delta,
      flipped_worse: raw.flipped_worse || [], flipped_better: raw.flipped_better || [], worst_groups: raw.worst_groups || [] };
  }

  // FixCandidate (§5). Drops are percentage points. n_changes (null if missing). kpis = the fix policy's
  // SimResult.kpis, normalised, or null on an older backend (the UI then asks /simulate).
  function normFix(f) {
    const hasK = f.kpis && Object.keys(f.kpis).length;
    return Object.assign({}, f, { title_ar: f.title_ar || f.id, title_en: f.title_en || f.id, source: f.source || "engine_grid",
      left_out_drop: +f.left_out_drop || 0, hardship_drop: +f.hardship_drop || 0, n_changes: f.n_changes == null ? null : +f.n_changes,
      kpis: hasK ? normKpis(f.kpis) : null });
  }
  // SensitivityResult: our backend sends details[] = [{param, factor, top2, fix_still_helps}, ...] with a
  // leading "reference" row; the UI's per-run table wants detail[] = [{key, factor, top2, fixHelps}].
  function normSensitivity(r) {
    if (r && !r.detail && Array.isArray(r.details)) {
      r.detail = r.details.filter(function (d) { return d.param !== "reference"; })
        .map(function (d) { return { key: d.param, factor: d.factor, top2: d.top2 || [], fixHelps: d.fix_still_helps }; });
    }
    return r;
  }

  const fixList = function (raw) { return (arr(raw, "fixes") || arr(raw, "top") || arr(raw, "candidates") || []).map(normFix); };

  // GET /llm/status -> { offline, state: "live" | "offline" | "resting", models: [{provider, slot, model, available, seconds_left}] }
  function normStatus(r) {
    const models = ((r && r.models) || []).map(function (m) {
      return { provider: m.provider, slot: m.slot, model: m.model, available: m.available !== false, seconds_left: (m.cooldown && m.cooldown.seconds_left) || 0 };
    });
    const offline = !!(r && r.offline);
    const state = offline ? "offline" : models.length && !models.some(function (m) { return m.available; }) ? "resting" : "live";
    return { offline: offline, state: state, models: models };
  }

  /* ---------- endpoints ---------- */
  const API = {
    base: BASE,
    ApiError: ApiError,
    population: function () { return get("/population").then(normPopulation); },
    sites: function () { return get("/sites").then(normSites); },
    scenarios: function () { return get("/scenarios").then(normScenarios); },
    assumptions: function () { return get("/assumptions").then(normAssumptions); },
    // Optional extras, not in §7. The UI falls back to config.js (or hides the AI chip) if they 404.
    areas: function () { return get("/areas").then(normAreas); },
    heroes: function () { return get("/heroes").then(normHeroes); },
    llmStatus: function () { return get("/llm/status").then(normStatus); },

    simulate: function (policy) { return post("/simulate", { policy: policy }).then(normSim); },
    compare: function (baseline, scenario) { return post("/compare", { baseline: baseline, scenario: scenario }).then(normCompare); },
    // -> { list: FixCandidate[], scenarioKpis: kpis | null }  (an older backend sends a bare list)
    fixgrid: function (baseline, scenario) {
      return post("/fixgrid", { baseline: baseline, scenario: scenario }).then(function (r) {
        return { list: fixList(r), scenarioKpis: r && r.scenario_kpis && Object.keys(r.scenario_kpis).length ? normKpis(r.scenario_kpis) : null };
      });
    },
    // -> { fixes: FixCandidate[], source, ai_proposal: {status, ...} | null }  (explanations filled; may include one ai_proposed fix)
    fixes: function (baseline, scenario) {
      return post("/fixes", { baseline: baseline, scenario: scenario }).then(function (r) { return { fixes: fixList(r), source: r.source || null, ai_proposal: r.ai_proposal || null }; });
    },
    // -> SensitivityResult (+ .detail[] rows {key, factor, top2, fixHelps} for the per-run table)
    // The backend takes the fix's Policy (models.py SensitivityRequest), so unwrap a FixCandidate here. No fix = ranking only.
    sensitivity: function (baseline, scenario, fix) {
      const fixPolicy = fix && fix.policy ? fix.policy : (fix || null);
      return post("/sensitivity", { baseline: baseline, scenario: scenario, fix: fixPolicy }).then(normSensitivity);
    },
    // -> ParseResult (+ source "ai" | "fallback")
    parse: function (text, policy, lang) { return post("/policy/parse", { text: text, current_policy: policy, lang: lang }).then(function (r) { r.source = r.source || "ai"; return r; }); },
    // -> { text_ar, summary_en, source }. The backend recomputes this citizen's outcome under `policy`.
    voice: function (citizenId, policy) {
      return post("/citizen/voice", { citizen_id: citizenId, policy: policy }).then(function (r) { return { text_ar: r.text_ar || "", summary_en: r.summary_en || "", source: r.source || "ai" }; });
    },
    // -> { summary_ar, summary_en, source }. scenario = the policy before any fix; fix = the applied fix's policy or null.
    report: function (baseline, scenario, fix) { return post("/report", { baseline: baseline, scenario: scenario, fix: fix || null }); },
  };
  root.NasAPI = API;
})(window);
