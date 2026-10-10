import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { ItemStatus } from "./types";

export const cn = (...v: ClassValue[]) => twMerge(clsx(v));

/** Format a decimal string as Indian-grouped INR without converting the value through float arithmetic. */
export function inr(v: string | null | undefined, opts: { sign?: boolean; symbol?: boolean } = {}): string {
  if (v === null || v === undefined || v === "") return "—";
  const neg = v.trim().startsWith("-");
  const [ip, fp = "00"] = v.replace("-", "").replace(/,/g, "").split(".");
  const last3 = ip.slice(-3);
  const rest = ip.slice(0, -3);
  const grouped = rest ? rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + last3 : last3;
  const s = `${opts.symbol === false ? "" : "₹"}${grouped}.${(fp + "00").slice(0, 2)}`;
  if (neg) return `−${s}`;
  return opts.sign && Number(v) > 0 ? `+${s}` : s;
}

/** Exact decimal-string arithmetic in integer paise (no float rounding). */
export function toPaise(v: string): bigint {
  const neg = v.trim().startsWith("-");
  const [i, f = ""] = v.replace("-", "").replace(/,/g, "").split(".");
  const p = BigInt(i || "0") * 100n + BigInt((f + "00").slice(0, 2));
  return neg ? -p : p;
}
export function fromPaise(p: bigint): string {
  const neg = p < 0n;
  const a = neg ? -p : p;
  return `${neg ? "-" : ""}${a / 100n}.${(a % 100n).toString().padStart(2, "0")}`;
}
export const subMoney = (a: string, b: string) => fromPaise(toPaise(a) - toPaise(b));

/** Numeric value for charts only (never used to compute displayed money). */
export const num = (v: string | null | undefined) => (v ? Number(v) : 0);

export const sec = (clauseId: string) => (clauseId.includes(":") ? clauseId.split(":")[1] : clauseId);

export const STATUS_META: Record<ItemStatus, { label: string; tone: string; short: string }> = {
  potentially_covered: { label: "Potentially covered", short: "Covered", tone: "covered" },
  partially_payable: { label: "Partially payable", short: "Partial", tone: "partial" },
  potentially_excluded: { label: "Potentially excluded", short: "Excluded", tone: "excluded" },
  conditional: { label: "Conditional", short: "Conditional", tone: "conditional" },
  insufficient_evidence: { label: "Insufficient evidence", short: "No evidence", tone: "insufficient" },
  conflicting_evidence: { label: "Conflicting evidence", short: "Conflict", tone: "conflict" },
  manual_review_required: { label: "Manual review required", short: "Review", tone: "review" },
};

export const TONE: Record<string, string> = {
  covered: "bg-covered-bg text-covered",
  partial: "bg-partial-bg text-partial",
  excluded: "bg-excluded-bg text-excluded",
  conditional: "bg-conditional-bg text-conditional",
  insufficient: "bg-insufficient-bg text-insufficient",
  conflict: "bg-conflict-bg text-conflict",
  review: "bg-review-bg text-review",
  neutral: "bg-white/[0.05] text-muted",
};

export const TONE_HEX: Record<string, string> = {
  covered: "#2e6b50", partial: "#3c5e7f", excluded: "#a2463a", conditional: "#946617",
  insufficient: "#73786f", conflict: "#7a4e86", review: "#8a6f22", neutral: "#cfc6b2",
};

/** Chart palette (single source for all charts). */
export const CHART = {
  grid: "#e3ddcf", axis: "#d3cab6", tick: "#6c7068", surface: "#fffefa",
  total: "#222521", reduction: "#a2463a", payable: "#2e6b50", patient: "#b69a62",
  series: ["#3c5e7f", "#2e6b50", "#b69a62"],
};

export const RELATION_META: Record<string, { label: string; tone: string }> = {
  support: { label: "Supports", tone: "covered" },
  limit: { label: "Supports with limit", tone: "partial" },
  override_support: { label: "Overrides exclusion", tone: "covered" },
  time_window_support: { label: "Supports (time window)", tone: "covered" },
  conditional_support: { label: "Conditional coverage", tone: "conditional" },
  exclusion: { label: "Excludes", tone: "excluded" },
  conditional_exclusion: { label: "Excludes unless…", tone: "conditional" },
  precedence: { label: "Precedence rule", tone: "neutral" },
  irrelevant: { label: "Not evidence", tone: "insufficient" },
  inapplicable: { label: "Does not apply", tone: "insufficient" },
};

export const STAGE_LABEL: Record<string, string> = {
  billed: "Billed", exclusion: "Exclusions", unresolved_hold: "Unresolved held out", item_limit: "Item limits",
  deductible: "Deductible", copay: "Co-payment", sum_insured_cap: "Sum insured cap", estimated_payable: "Estimated payable",
};

export const fmtDate = (d: string | null | undefined) =>
  d ? new Date(d + (d.length === 10 ? "T00:00:00" : "")).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";
