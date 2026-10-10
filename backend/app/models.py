"""Typed domain models shared by ingestion, retrieval, the rules engine and the API."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

NOT_FOUND = "Not found in the provided documents"


# ---------------------------------------------------------------- documents

class DocType(str, Enum):
    policy = "policy"
    endorsement = "endorsement"
    bill = "bill"
    benefit_summary = "benefit_summary"
    supporting = "supporting"


class ClauseCategory(str, Enum):
    definition = "definition"
    coverage = "coverage"
    limit = "limit"
    conditional_coverage = "conditional_coverage"
    exclusion = "exclusion"
    conditional_exclusion = "conditional_exclusion"
    waiting_period = "waiting_period"
    deductible = "deductible"
    copayment = "copayment"
    computation_order = "computation_order"
    precedence = "precedence"
    applicability = "applicability"
    claim_requirement = "claim_requirement"
    time_window = "time_window"
    other = "other"


class LimitSpec(BaseModel):
    amount: Optional[Decimal] = None
    percent_of_sum_insured: Optional[Decimal] = None
    basis: Literal["per_day", "per_hospitalisation", "per_eye", "per_policy_year", "per_claim", "unspecified"] = "unspecified"
    text: str = ""


class Interpretation(BaseModel):
    """Structured, deterministic reading of a clause. Every field is derived from the clause text."""
    category: ClauseCategory
    payable: Optional[bool] = None
    scope_terms: list[str] = Field(default_factory=list)
    limit: Optional[LimitSpec] = None
    percent: Optional[Decimal] = None  # co-payment percentage
    amount: Optional[Decimal] = None   # deductible amount
    condition: Optional[str] = None    # "unless ..." / "provided ..." text
    condition_key: Optional[str] = None
    waiting_months: Optional[int] = None
    waiting_days: Optional[int] = None
    window_days_before: Optional[int] = None
    window_days_after: Optional[int] = None
    replaces: list[str] = Field(default_factory=list)       # section numbers replaced
    overrides: list[str] = Field(default_factory=list)      # "notwithstanding" targets
    order: list[str] = Field(default_factory=list)          # computation stages
    notes: list[str] = Field(default_factory=list)


class Clause(BaseModel):
    clause_id: str
    document_id: str
    doc_type: DocType
    section: str
    heading: str
    text: str
    page: Optional[int]
    group: str = ""
    effective_date: Optional[date] = None
    text_source: Literal["text_layer", "ocr"] = "text_layer"
    extraction_confidence: Literal["high", "medium", "low"] = "high"
    verification_status: Literal["extracted", "verified_text_layer", "ocr_unverified"] = "verified_text_layer"
    interpretation: Interpretation


class PageText(BaseModel):
    number: int
    text: str
    source: Literal["text_layer", "ocr", "empty"]
    char_count: int


class DocumentRecord(BaseModel):
    document_id: str
    doc_type: DocType
    filename: str
    size_bytes: int
    sha256: str
    page_count: int
    status: Literal["processed", "processed_with_warnings", "failed"]
    warnings: list[str] = Field(default_factory=list)
    synthetic: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    clauses: list[Clause] = Field(default_factory=list)
    pages: list[PageText] = Field(default_factory=list)
    uploaded_at: str = ""
    owner_id: str = ""


# ---------------------------------------------------------------- versions

class PolicyVersion(BaseModel):
    version_id: str
    label: str
    policy_document_id: str
    endorsement_ids: list[str]
    effective_from: Optional[date]
    effective_to: Optional[date]
    superseded_sections: dict[str, str] = Field(default_factory=dict)  # old clause_id -> new clause_id
    notes: list[str] = Field(default_factory=list)


class VersionSelection(BaseModel):
    treatment_date: Optional[date]
    selected: Optional[PolicyVersion]
    alternatives: list[PolicyVersion] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    review_required: bool = False
    overridden: bool = False


# ---------------------------------------------------------------- bills

class BillItem(BaseModel):
    item_id: str
    line_no: int
    description: str
    service_date: Optional[date] = None
    quantity: Decimal = Decimal("1")
    unit_price: Optional[Decimal] = None
    amount: Decimal
    category_hint: Optional[str] = None
    # Provenance: read from the bill, entered by the user, or extracted and then corrected by the user.
    source: Literal["extracted", "manual", "user_corrected"] = "extracted"
    # Values as originally extracted, kept when the user corrects a line (never overwritten afterwards).
    extracted: Optional[dict[str, Optional[str]]] = None


class BillIssue(BaseModel):
    severity: Literal["error", "warning"]
    line_no: Optional[int] = None
    message: str


class Bill(BaseModel):
    bill_id: str
    document_id: Optional[str] = None
    hospital: str = NOT_FOUND
    patient: str = NOT_FOUND
    bill_date: Optional[date] = None
    admission_date: Optional[date] = None
    discharge_date: Optional[date] = None
    diagnosis: str = NOT_FOUND
    items: list[BillItem]
    stated_total: Optional[Decimal] = None
    computed_total: Decimal = Decimal("0.00")
    issues: list[BillIssue] = Field(default_factory=list)
    synthetic: bool = False
    removed_items: list[BillItem] = Field(default_factory=list)   # lines the user removed (kept for the audit trail)
    reviewed_at: Optional[str] = None                              # when the user confirmed the line items


# ---------------------------------------------------------------- claims

Tri = Literal["yes", "no", "unknown"]


class ClaimFacts(BaseModel):
    """Claim-level facts. Values are user-asserted unless a document establishes them."""
    vitamin_prescription: Tri = "unknown"
    implant_invoice_submitted: Tri = "unknown"
    post_hospitalisation_same_condition: Tri = "yes"
    pre_existing_condition: Tri = "no"
    accident: Tri = "no"
    deductible_used_this_year: Decimal = Decimal("0.00")
    sum_insured_used_this_year: Decimal = Decimal("0.00")


class Hypotheticals(BaseModel):
    """What-If Lab overrides. Anything set here is labelled HYPOTHETICAL in every output."""
    deductible: Optional[Decimal] = None
    copay_percent: Optional[Decimal] = None
    limit_overrides: dict[str, Decimal] = Field(default_factory=dict)  # clause_id -> limit amount
    item_amounts: dict[str, Decimal] = Field(default_factory=dict)
    item_quantities: dict[str, Decimal] = Field(default_factory=dict)
    removed_items: list[str] = Field(default_factory=list)
    added_items: list[BillItem] = Field(default_factory=list)
    treatment_date: Optional[date] = None
    version_id: Optional[str] = None

    def is_empty(self) -> bool:
        return not (self.deductible is not None or self.copay_percent is not None or self.limit_overrides
                    or self.item_amounts or self.item_quantities or self.removed_items or self.added_items
                    or self.treatment_date or self.version_id)


class Claim(BaseModel):
    claim_id: str
    title: str
    policy_document_id: str
    endorsement_ids: list[str] = Field(default_factory=list)
    benefit_summary_ids: list[str] = Field(default_factory=list)  # brochures / benefit summaries for cross-checks
    bill: Bill
    admission_date: date
    discharge_date: Optional[date] = None
    diagnosis: str = NOT_FOUND
    facts: ClaimFacts = Field(default_factory=ClaimFacts)
    synthetic: bool = False
    created_at: str = ""
    owner_id: str = ""


# ---------------------------------------------------------------- evidence & adjudication

Relation = Literal["support", "exclusion", "conditional_exclusion", "conditional_support", "limit",
                   "override_support", "time_window_support", "precedence", "irrelevant", "inapplicable"]


class Evidence(BaseModel):
    clause_id: str
    section: str
    heading: str
    document_id: str
    doc_type: DocType
    page: Optional[int]
    excerpt: str
    relation: Relation
    specificity: Literal["direct", "general", "none"]
    matched_terms: list[str] = Field(default_factory=list)
    reason: str
    retrieval: dict[str, Optional[float]] = Field(default_factory=dict)  # method -> score (relevance only)
    retrieval_rank: Optional[int] = None


ItemStatus = Literal["potentially_covered", "partially_payable", "potentially_excluded", "conditional",
                     "insufficient_evidence", "conflicting_evidence", "manual_review_required"]


class Adjustment(BaseModel):
    adjustment_id: str
    stage: Literal["exclusion", "item_limit", "deductible", "copay", "sum_insured_cap", "unresolved_hold"]
    item_id: Optional[str]
    amount: Decimal
    clause_ids: list[str]
    description: str
    hypothetical: bool = False


class TraceStep(BaseModel):
    step_no: int
    stage: str
    description: str
    amount_before: Decimal
    amount_after: Decimal
    clause_ids: list[str] = Field(default_factory=list)
    adjustments: list[str] = Field(default_factory=list)


class LedgerRow(BaseModel):
    item_id: str
    line_no: int
    original_description: str
    normalized_description: str
    category: str
    service_date: Optional[date]
    quantity: Decimal
    claimed_amount: Decimal
    status: ItemStatus
    eligible_amount: Optional[Decimal]          # after exclusions & item limits; None when unresolved
    item_reductions: Decimal                    # exclusions + item limits
    deductible_share: Decimal
    copay_share: Decimal
    cap_share: Decimal
    payable_low: Decimal
    payable_high: Decimal
    patient_low: Decimal
    patient_high: Decimal
    supporting_clause_ids: list[str]
    applicable_limit: Optional[str] = None
    explanation: str
    evidence_quality: Literal["direct", "general", "weak", "none"]
    manual_review: bool
    review_reasons: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    adjustments: list[str] = Field(default_factory=list)
    hypothetical: bool = False


class ClaimCheck(BaseModel):
    check: str
    status: Literal["satisfied", "not_satisfied", "unknown", "not_applicable"]
    clause_ids: list[str]
    detail: str


class FinancialSummary(BaseModel):
    total_billed: Decimal
    eligible_definite: Decimal
    unresolved_claimed: Decimal
    item_reductions: Decimal
    deductible_applied_low: Decimal
    deductible_applied_high: Decimal
    copay_low: Decimal
    copay_high: Decimal
    payable_low: Decimal
    payable_high: Decimal
    patient_low: Decimal
    patient_high: Decimal
    unresolved_exposure: Decimal
    currency: str = "INR"
    computation_order: list[str]
    order_source: str
    explanation: list[str]


class AnalysisResult(BaseModel):
    analysis_id: str
    claim_id: str
    created_at: str
    cause: str
    version: VersionSelection
    rows: list[LedgerRow]
    claim_checks: list[ClaimCheck]
    summary: FinancialSummary
    trace_low: list[TraceStep]
    trace_high: list[TraceStep]
    adjustments: list[Adjustment]
    invariants: list[dict[str, Any]]
    bill_issues: list[BillIssue]
    hypothetical: bool = False
    hypotheticals: Optional[Hypotheticals] = None
    synthetic: bool = False
    retrieval_config: dict[str, Any] = Field(default_factory=dict)
    disclaimer: str = ("Nivaaran provides decision-support estimates only. It does not guarantee insurer "
                       "approval, claim settlement or reimbursement.")
