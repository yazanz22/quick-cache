// Mirrors backend/app/models.py (the API contract). Keep in sync manually.
// Fields marked "extra" were added beyond CLAUDE.md §5.

export type Day = "sat" | "sun" | "mon" | "tue" | "wed" | "thu" | "fri";
export type Status = "served" | "hardship" | "left_out";
export type ReasonCode =
  | "TOO_FAR" | "NO_TRANSPORT" | "HOURS_CONFLICT_WORK" | "NO_SMARTPHONE"
  | "LOW_DIGITAL_LITERACY" | "NOT_WHEELCHAIR_ACCESSIBLE" | "TOO_EXPENSIVE" | "OFFICE_CLOSED_ON_AVAILABLE_DAYS";
export type Tag = "elderly" | "disabled" | "low_income" | "no_car" | "offline" | "worker" | "student";
export type Source = "ai" | "fallback";

export interface Citizen {
  id: string; name_ar: string; name_en: string; age: number; gender: "m" | "f";
  area: string; lat: number; lng: number;
  mobility: "none" | "limited" | "wheelchair";
  has_car: boolean; has_smartphone: boolean; digital_literacy: "low" | "medium" | "high";
  works: boolean; work_start: string | null; work_end: string | null;
  income_band: "low" | "middle" | "high";
  has_helper: boolean; helper_relation_ar: string | null; helper_relation_en: string | null;
  tags: Tag[];
}

// extra: GET /areas, GET /sites
export interface Area { id: string; name_ar: string; name_en: string; lat: number; lng: number; side: "east" | "west"; weight: number }
export interface Site { id: string; area: string; name_ar: string; name_en: string; lat: number; lng: number }

export interface Office {
  id: string; name_ar: string; name_en: string; site_id: string;
  schedule: Partial<Record<Day, [string, string]>>;
  wheelchair_accessible: boolean;
}
export interface MobileUnit { area: string; day: Day; open: string; close: string }
export interface Policy {
  service: string; offices: Office[]; online_enabled: boolean; online_only: boolean;
  mobile_units: MobileUnit[]; appointment_required: boolean; fee_jd: number; visits_required: number;
}

// extra: GET /scenarios returns these (sorted by order)
export interface Scenario {
  id: string; order: number; name_ar: string; name_en: string;
  description_ar: string; description_en: string; policy: Policy;
}

export interface CitizenOutcome {
  citizen_id: string; status: Status;
  channel: string | null; channel_name_ar: string | null; channel_name_en: string | null;
  mode: "car" | "helper_car" | "bus" | "taxi" | "online" | null;
  bus_transfers: number; visit_day: Day | null;
  travel_minutes: number;   // one way
  cost_jd: number; hours_lost: number; work_hours_missed: number;
  reasons: ReasonCode[];
}

export interface Kpis {
  pct_served: number; pct_hardship: number; pct_left_out: number;
  avg_hours_lost: number; avg_cost_jd: number;
  n: number; n_served: number; n_hardship: number; n_left_out: number;  // extra counts
}
export interface GroupStats { served: number; hardship: number; left_out: number; n: number }
// by_group keys: "all" + every Tag
export interface SimResult { outcomes: CitizenOutcome[]; kpis: Kpis; by_group: Record<string, GroupStats> }

export interface CompareResult {
  baseline: SimResult; scenario: SimResult;
  flipped_worse: string[]; flipped_better: string[];
  kpi_delta: Partial<Kpis>;
  worst_groups: string[];   // the 6 equity groups, worst first
}

export interface FixCandidate {
  id: string; title_ar: string; title_en: string; policy: Policy;
  source: "engine_grid" | "ai_proposed";
  left_out_drop: number; hardship_drop: number; worsens_any_group: boolean;
  explanation_ar: string | null; explanation_en: string | null;
}

export interface ParseResult {
  status: "ok" | "unsupported"; policy: Policy | null;
  changes_ar: string[]; changes_en: string[];
  message_ar: string | null; message_en: string | null;
  source: Source;  // extra
}

export interface SensitivityResult {
  runs: number; ranking_held: number; fix_still_helps: number;
  stable_top_group: string | null;
  stable_top2: string[] | null;   // extra: same top-2 set in every run (order may flip)
  passed: boolean;
  details: Record<string, unknown>[];  // extra: one row per run
}

// Request / response bodies
export interface CompareRequest { baseline: Policy; scenario: Policy }       // /compare, /fixgrid, /fixes
export interface SensitivityRequest { baseline: Policy; scenario: Policy; fix: Policy }
export interface ParseRequest { text: string; current_policy: Policy; lang: "ar" | "en" }
export interface VoiceRequest { citizen_id: string; outcome: CitizenOutcome }
export interface VoiceResponse { text_ar: string; summary_en: string; source: Source }  // summary_en: extra
export interface ReportRequest { compare_result: CompareResult; sensitivity: SensitivityResult | null }
export interface ReportResponse { summary_ar: string; summary_en: string; source: Source }

export type AiProposalStatus =
  | "shown" | "hidden_not_better" | "hidden_worsens_a_group" | "hidden_duplicate_of_grid"
  | "hidden_no_change" | "invalid" | "ai_unavailable" | "no_grid_fixes" | "none";
export interface FixesResponse {
  fixes: FixCandidate[]; source: Source;
  ai_proposal: { status: AiProposalStatus; title_en?: string; left_out_drop?: number; hardship_drop?: number;
                 best_grid_left_out_drop?: number; best_grid_hardship_drop?: number; error?: string } | null;  // extra
}

// extra: GET /assumptions rows
export interface AssumptionRow {
  name: string; value: number | string | Record<string, number>; unit: string;
  rationale: string; tag: "ASSUMPTION" | "ANCHORED"; source: string | null; perturbed_in_robustness_check: boolean;
}

// extra: GET /labels  ({ar, en} per key)
export type LabelMap = Record<string, { ar: string; en: string }>;
export interface Labels { reasons: LabelMap; groups: LabelMap; modes: LabelMap; statuses: LabelMap; days: LabelMap }
