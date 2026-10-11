// Mirrors backend Pydantic models. Monetary values arrive as decimal strings and are never parsed with float math
// for display beyond formatting.

export type Money = string;
export type ItemStatus =
  | "potentially_covered" | "partially_payable" | "potentially_excluded" | "conditional"
  | "insufficient_evidence" | "conflicting_evidence" | "manual_review_required";

export interface LimitSpec { amount: Money | null; percent_of_sum_insured: string | null; basis: string; text: string }
export interface Interpretation {
  category: string; payable: boolean | null; scope_terms: string[]; limit: LimitSpec | null; percent: string | null;
  amount: Money | null; condition: string | null; condition_key: string | null; waiting_months: number | null;
  waiting_days: number | null; window_days_before: number | null; window_days_after: number | null;
  replaces: string[]; overrides: string[]; order: string[]; notes: string[];
}
export interface Clause {
  clause_id: string; document_id: string; doc_type: string; section: string; heading: string; text: string;
  page: number | null; group: string; effective_date: string | null; text_source: string;
  extraction_confidence: string; verification_status: string; interpretation: Interpretation;
}
export interface DocumentRecord {
  document_id: string; doc_type: "policy" | "endorsement" | "benefit_summary"; filename: string; size_bytes: number; sha256: string;
  page_count: number; status: string; warnings: string[]; synthetic: boolean; metadata: Record<string, string>;
  clauses?: Clause[]; clause_count: number; uploaded_at: string; ocr_pages: number[]; empty_pages: number[];
}
export interface PolicyVersion {
  version_id: string; label: string; policy_document_id: string; endorsement_ids: string[];
  effective_from: string | null; effective_to: string | null; superseded_sections: Record<string, string>; notes: string[];
  active_clause_count?: number;
}
export interface VersionSelection {
  treatment_date: string | null; selected: PolicyVersion | null; alternatives: PolicyVersion[]; reasons: string[];
  conflicts: string[]; review_required: boolean; overridden: boolean;
}
export interface BillItem {
  item_id: string; line_no: number; description: string; service_date: string | null; quantity: string;
  unit_price: Money | null; amount: Money; category_hint: string | null;
  source?: "extracted" | "manual" | "user_corrected";
  extracted?: { description: string; quantity: string; unit_price: string | null; amount: string; service_date: string | null } | null;
}
export interface BillItemEdit { item_id?: string; description: string; amount: string; quantity: string; unit_price: string | null; service_date: string | null }
export interface BillIssue { severity: "error" | "warning"; line_no: number | null; message: string }
export interface Bill {
  bill_id: string; document_id: string | null; hospital: string; patient: string; bill_date: string | null;
  admission_date: string | null; discharge_date: string | null; diagnosis: string; items: BillItem[];
  stated_total: Money | null; computed_total: Money; issues: BillIssue[]; synthetic: boolean;
  removed_items?: BillItem[]; reviewed_at?: string | null; breakdown?: BillBreakdown[];
}
export type Tri = "yes" | "no" | "unknown";
export interface ClaimFacts {
  vitamin_prescription: Tri; implant_invoice_submitted: Tri; post_hospitalisation_same_condition: Tri;
  pre_existing_condition: Tri; accident: Tri; deductible_used_this_year: Money; sum_insured_used_this_year: Money;
}
export interface Claim {
  claim_id: string; title: string; policy_document_id: string; endorsement_ids: string[]; benefit_summary_ids: string[]; bill: Bill;
  admission_date: string; discharge_date: string | null; diagnosis: string; facts: ClaimFacts; synthetic: boolean; created_at: string;
}
export interface Evidence {
  clause_id: string; section: string; heading: string; document_id: string; doc_type: string; page: number | null;
  excerpt: string; relation: string; specificity: "direct" | "general" | "none"; matched_terms: string[]; reason: string;
  retrieval: Record<string, number | null>; retrieval_rank: number | null;
}
export interface LedgerRow {
  item_id: string; line_no: number; original_description: string; normalized_description: string; category: string;
  service_date: string | null; quantity: string; claimed_amount: Money; status: ItemStatus; eligible_amount: Money | null;
  item_reductions: Money; deductible_share: Money; copay_share: Money; cap_share: Money; payable_low: Money;
  payable_high: Money; patient_low: Money; patient_high: Money; supporting_clause_ids: string[];
  applicable_limit: string | null; explanation: string; evidence_quality: string; manual_review: boolean;
  review_reasons: string[]; missing_information: string[]; evidence: Evidence[]; adjustments: string[]; hypothetical: boolean;
}
export interface TraceStep {
  step_no: number; stage: string; description: string; amount_before: Money; amount_after: Money;
  clause_ids: string[]; adjustments: string[];
}
export interface Adjustment {
  adjustment_id: string; stage: string; item_id: string | null; amount: Money; clause_ids: string[]; description: string; hypothetical: boolean;
}
export interface ClaimCheck { check: string; status: string; clause_ids: string[]; detail: string }
export interface FinancialSummary {
  total_billed: Money; eligible_definite: Money; unresolved_claimed: Money; item_reductions: Money;
  deductible_applied_low: Money; deductible_applied_high: Money; copay_low: Money; copay_high: Money;
  payable_low: Money; payable_high: Money; patient_low: Money; patient_high: Money; unresolved_exposure: Money;
  currency: string; computation_order: string[]; order_source: string; explanation: string[];
}
export interface Hypotheticals {
  deductible?: string | null; copay_percent?: string | null; limit_overrides?: Record<string, string>;
  item_amounts?: Record<string, string>; item_quantities?: Record<string, string>; removed_items?: string[];
  added_items?: BillItem[]; treatment_date?: string | null; version_id?: string | null;
}
export interface Analysis {
  analysis_id: string; claim_id: string; created_at: string; cause: string; version: VersionSelection; rows: LedgerRow[];
  claim_checks: ClaimCheck[]; summary: FinancialSummary; trace_low: TraceStep[]; trace_high: TraceStep[];
  adjustments: Adjustment[]; invariants: { name: string; passed: boolean; detail: string }[]; bill_issues: BillIssue[];
  hypothetical: boolean; hypotheticals: Hypotheticals | null; synthetic: boolean; retrieval_config: Record<string, string>;
  disclaimer: string;
}
export interface ChangedItem {
  item_id: string; description: string; change: "added" | "removed" | "changed"; status_before?: ItemStatus;
  status_after?: ItemStatus; clauses_before?: string[]; clauses_after?: string[]; payable_before: Money;
  payable_after: Money; delta: Money; reason: string;
}
export interface Comparison {
  comparison_id: string; created_at: string; cause: string; previous_analysis_id: string; updated_analysis_id: string;
  previous_version: string | null; updated_version: string | null; reasons: string[]; changed_items: ChangedItem[];
  changed_steps: { stage: string; before: string | null; after: string; amount_before: Money | null; amount_after: Money }[];
  changed_clauses: { added: string[]; removed: string[] }; payable_before: Money[]; payable_after: Money[];
  payable_delta: Money; payable_high_delta: Money; patient_before: Money[]; patient_after: Money[]; patient_delta: Money;
  hypothetical: boolean;
}
export interface HistoryEntry { analysis_id: string; created_at: string; cause: string; version: string | null; payable_low: Money; payable_high: Money }
export interface ClaimBundle { claim: Claim; analysis: Analysis | null; history: HistoryEntry[]; comparisons: Comparison[] }
export interface ClaimListEntry {
  claim_id: string; title: string; created_at: string; synthetic: boolean; admission_date: string; items: number; total_billed: Money;
  latest: null | { analysis_id: string; version: string | null; payable_low: Money; payable_high: Money; patient_low: Money;
    patient_high: Money; review_items: number; created_at: string };
}
export interface Citation { clause_id: string; section: string; heading: string; page: number | null; document_id: string; excerpt: string; relation?: string }
export interface CopilotAction { type: "open_clause" | "open_item" | "navigate"; label: string; clause_id?: string; item_id?: string; to?: string }
export interface AssistantAnswer { kind: string; answer: string; citations: Citation[]; grounded: boolean; disclaimer: string; question: string; data?: Comparison; actions?: CopilotAction[]; draft?: string; item_id?: string; engine?: string; breakdown?: { source_facts: string[]; calculated: string[]; interpretation: string; assumptions: string[]; missing: string[] } }
export interface SystemInfo { product: string; tagline: string; version: string; embedding_backend: string; reranker_available: boolean; ocr_available: boolean; max_upload_mb: number; external_services: string }

export interface AuthUser {
  id: string; created: string; is_demo: boolean;
  email: string | null; email_verified: boolean; name: string | null; avatar_url: string | null; phone: string | null;
  google_linked: boolean; provider: "google" | "phone" | "password" | "demo";
}
export interface AuthProviders { google: boolean }
export interface PolicySummary {
  lang: "en" | "hi"; title: string; intro: string; outro: string; text: string; quick_text: string; source: string;
  sections: { heading: string; items: { text: string; clause: string }[] }[];
  facts?: {
    deductible: { amount: string; clause: string } | null; copay: { percent: string; clause: string } | null;
    window: { before: number | null; after: number | null; clause: string } | null;
    limits: { label: string; amount: string; basis: string; clause: string }[];
    waits: { label: string; months: number | null; days: number | null; clause: string }[];
    counts: Record<"covered" | "limits" | "you_pay" | "waiting" | "excluded", number>;
  };
}
export interface BillBreakdown { category: string; label: string; amount: string; count: number }

export interface PolicyAnswer {
  question: string; language: "en" | "hi"; answer: string; answer_en?: string; grounded: boolean; engine: string; disclaimer: string;
  citations: { clause_id: string; section: string; heading: string; page: number | null; document_id: string; excerpt: string }[];
}
export interface PolicyChecklist {
  policy_start: string | null;
  claim_documents: { text: string; clause: string }[];
  notice: { text: string; clause: string }[];
  waits: { label: string; months: number | null; days: number | null; covered_from: string | null; done: boolean; clause: string }[];
  window: { before: number | null; after: number | null; clause: string } | null;
  deductible: { amount: string; clause: string } | null;
  copay: { percent: string; clause: string } | null;
}
