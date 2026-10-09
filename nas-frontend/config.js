/* Nas frontend config. The only file you should need to edit to point the UI at a backend.
   You can also override the API URL without editing: open index.html?api=http://192.168.1.20:8000 */
window.NAS_CONFIG = {
  // FastAPI backend (CLAUDE.md §7). The backend serves this page itself at http://localhost:8000/,
  // so by default the API is the page's own origin. Opened from a separate static server on
  // port 3000 (or as a file), it falls back to http://localhost:8000.
  API_URL: location.protocol.indexOf("http") === 0 && location.port !== "3000" ? location.origin : "http://localhost:8000",

  // Per-request timeout. AI routes (/policy/parse, /citizen/voice, /report, /fixes) can take a while.
  TIMEOUT_MS: 20000,

  // Debounce before re-running /compare after an edit or a pin drag (CLAUDE.md §9.2).
  COMPARE_DEBOUNCE_MS: 300,

  // true = no map tiles (no internet at the venue); areas are drawn as labelled circles instead.
  // Also switchable per visit with ?offline=1
  OFFLINE_MAP: new URLSearchParams(location.search).get("offline") === "1" || false,

  // Hero citizens to show as quick buttons. Used only if GET /heroes doesn't exist.
  HERO_IDS: [],

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
