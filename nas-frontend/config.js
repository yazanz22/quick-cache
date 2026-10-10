/* Nas frontend config. The only file you should need to edit to point the UI at a backend.
   You can also override the API URL without editing: open index.html?api=http://192.168.1.20:8000 */
window.NAS_CONFIG = {
  // FastAPI backend (CLAUDE.md §7). The backend serves this page itself at http://localhost:8000/,
  // so by default the API is the page's own origin. Opened from a separate static server on
  // port 3000 (or as a file), it falls back to http://localhost:8000.
  API_URL: location.protocol.indexOf("http") === 0 && location.port !== "3000" ? location.origin : "http://localhost:8000",

  // Default per-request timeout (engine routes answer in well under a second).
  TIMEOUT_MS: 20000,
  // AI routes can take a while (the backend tries several models before its template). Per route, in ms.
  TIMEOUT_AI_MS: { "/fixes": 30000, "/report": 30000, "/policy/parse": 25000, "/citizen/voice": 25000 },
  // Debounce before re-running /compare after an edit or a pin drag (CLAUDE.md §9.2).
  COMPARE_DEBOUNCE_MS: 300,

  // true = no map tiles (no internet at the venue); areas are drawn as labelled circles instead.
  // Also switchable per visit with ?offline=1
  OFFLINE_MAP: new URLSearchParams(location.search).get("offline") === "1" || false,

  // Hero citizens to show as quick buttons. Used only if GET /heroes doesn't exist.
  HERO_IDS: [],

  // Everyday travel: today's 90-octane pump price (JD per litre, Oct 2026), shown next to the fuel stepper as
  // "1.050 JD/L -> X". Display only: the engine works from fuel_price_change_pct, never from this number.
  FUEL_PRICE_90_JD: 1.050,

  // Office sites that belong to one service only: hidden from the other services' site lists, pins and map marks
  // (the Royal Court's Citizen Services Unit takes medical-exemption applications, not ID renewals).
  SERVICE_ONLY_SITES: { royal_court_csu: "medical_exemption" },

  // Used only if GET /services doesn't exist: one service, so the switcher stays hidden.
  SERVICES: [{ id: "id_renewal", name_ar: "تجديد الهوية", name_en: "ID renewal", levers: ["offices", "online", "appointments", "mobile_units", "fee", "visits", "protections"], baseline_scenario: "baseline", demo_scenario: null }],

  // Used only if GET /areas doesn't exist. Approximate centroids from CLAUDE.md §6.
  AREAS: {
    downtown:  { name_ar: "وسط البلد", name_en: "Downtown", lat: 31.951, lng: 35.934 },
    abdali:    { name_ar: "العبدلي", name_en: "Abdali", lat: 31.962, lng: 35.910 },
    jabal_al_hussein: { name_ar: "جبل الحسين", name_en: "Jabal Al-Hussein", lat: 31.968, lng: 35.920 },
    marka:     { name_ar: "ماركا", name_en: "Marka", lat: 31.975, lng: 35.985 },
    wehdat:    { name_ar: "الوحدات", name_en: "Wehdat", lat: 31.935, lng: 35.940 },
    tabarbour: { name_ar: "طبربور", name_en: "Tabarbour", lat: 32.000, lng: 35.940 },
    sweileh:   { name_ar: "صويلح", name_en: "Sweileh", lat: 32.020, lng: 35.840 },
    khalda:    { name_ar: "خلدا", name_en: "Khalda", lat: 31.995, lng: 35.835 },
  },
};
