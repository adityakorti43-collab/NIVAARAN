import { AlertTriangle, CheckCircle2, CircleDashed, CircleHelp, ExternalLink, FileText, FlaskConical, GitCompareArrows, Info, Loader2, MinusCircle, ShieldAlert, XCircle } from "lucide-react";
import { motion } from "motion/react";
import type { ReactNode } from "react";
import { cn, RELATION_META, sec, STATUS_META, TONE } from "../lib/format";
import type { Evidence, ItemStatus } from "../lib/types";
import { useClauseViewer } from "./ClauseViewer";
import { ease, MoneyRange } from "./motion";
import { Tip } from "./overlay";

const STATUS_ICON: Record<ItemStatus, typeof CheckCircle2> = {
  potentially_covered: CheckCircle2, partially_payable: MinusCircle, potentially_excluded: XCircle, conditional: CircleDashed,
  insufficient_evidence: CircleHelp, conflicting_evidence: GitCompareArrows, manual_review_required: ShieldAlert,
};

export function StatusBadge({ status, short = false, className }: { status: ItemStatus; short?: boolean; className?: string }) {
  const m = STATUS_META[status];
  const Icon = STATUS_ICON[status];
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset ring-current/15", TONE[m.tone], className)}>
      <Icon className="size-3.5 shrink-0" aria-hidden />
      {short ? m.short : m.label}
    </span>
  );
}

export function Tag({ tone = "neutral", children, className }: { tone?: string; children: ReactNode; className?: string }) {
  return <span className={cn("inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium", TONE[tone], className)}>{children}</span>;
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease }}
      className="mb-7 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div className="max-w-3xl">
        {eyebrow && <p className="mb-2 text-[13px] font-medium text-muted">{eyebrow}</p>}
        <h1 className="h-display text-[32px] leading-[1.02] md:text-[44px]">{title}</h1>
        {description && <p className="mt-2.5 max-w-2xl text-[14px] leading-relaxed text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </motion.div>
  );
}

export function Section({ title, description, actions, children, className }: { title: string; description?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("card min-w-0 p-4 md:p-5", className)}>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-[15px] font-semibold tracking-tight text-ink">{title}</h2>
          {description && <p className="mt-0.5 text-xs leading-relaxed text-muted">{description}</p>}
        </div>
        {actions}
      </div>
      {children}
    </section>
  );
}

export function Stat({ label, value, sub, tone, testId, info }: { label: string; value: ReactNode; sub?: ReactNode; tone?: string; testId?: string; info?: ReactNode }) {
  return (
    <div className="card group relative overflow-hidden p-4" data-testid={testId}>
      {tone && <div className={cn("absolute inset-x-0 top-0 h-px opacity-70", `bg-${tone}`)} aria-hidden />}
      <p className="eyebrow flex items-center gap-1.5">{label}
        {info && <Tip content={info}><Info className="size-3 text-faint" aria-label="More information" tabIndex={0} /></Tip>}</p>
      <p className={cn("mt-2.5 text-[23px] font-semibold leading-tight tracking-tight num", tone ? `text-${tone}` : "text-ink")}>{value}</p>
      {sub && <p className="mt-1 text-xs leading-snug text-muted">{sub}</p>}
    </div>
  );
}

export function Range({ low, high }: { low: string; high: string }) {
  return <MoneyRange low={low} high={high} />;
}

export function EmptyState({ icon: Icon = FileText, title, children, actions }: { icon?: typeof FileText; title: string; children?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="card relative flex flex-col items-center overflow-hidden px-6 py-16 text-center">
      <div className="grid-fade pointer-events-none absolute inset-0" aria-hidden />
      <div className="relative mb-4 grid size-14 place-items-center rounded-2xl border border-line-2 bg-card-2 text-accent "><Icon className="size-6" aria-hidden /></div>
      <h3 className="relative text-lg font-semibold text-ink">{title}</h3>
      {children && <div className="relative mt-1.5 max-w-md text-sm text-muted">{children}</div>}
      {actions && <div className="relative mt-6 flex flex-wrap justify-center gap-2">{actions}</div>}
    </div>
  );
}

/** Retired: real documents are never labelled as demo data. Kept as a no-op so existing pages need no special cases. */
export function SyntheticBanner(_: { show?: boolean }) {
  return null;
}

export function HypotheticalBanner({ children }: { children?: ReactNode }) {
  return (
    <div role="note" className="mb-4 flex items-start gap-2.5 rounded-xl border border-partial/25 bg-partial-bg px-3.5 py-2.5 text-sm text-partial">
      <FlaskConical className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p><strong className="font-semibold">Hypothetical scenario.</strong> <span className="text-text/85">{children ?? "These inputs are assumptions you entered, not terms established by the policy documents."}</span></p>
    </div>
  );
}

export function Disclaimer({ className }: { className?: string }) {
  return (
    <p className={cn("text-xs leading-relaxed text-faint", className)}>
      Nivaaran provides decision-support estimates only. It does not guarantee insurer approval, claim settlement or reimbursement.
    </p>
  );
}

export function ErrorNote({ error, className }: { error: string | null | undefined; className?: string }) {
  if (!error) return null;
  return (
    <div role="alert" className={cn("flex items-start gap-2 rounded-xl border border-excluded/25 bg-excluded-bg px-3 py-2.5 text-sm text-excluded", className)}>
      <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p>{error}</p>
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return <span className="inline-flex items-center gap-2 text-sm text-muted"><Loader2 className="size-4 animate-spin text-accent" aria-hidden />{label}</span>;
}

export function PageSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading">
      <div className="skeleton mb-3 h-4 w-28" /><div className="skeleton mb-8 h-9 w-2/3 max-w-xl" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-28" />)}</div>
      <div className="skeleton mt-5 h-80" />
    </div>
  );
}

export function EvidenceCard({ e, decisive, compact }: { e: Evidence; decisive?: boolean; compact?: boolean }) {
  const r = RELATION_META[e.relation] ?? { label: e.relation, tone: "neutral" };
  const muted = e.relation === "irrelevant" || e.relation === "inapplicable";
  const { openClause } = useClauseViewer();
  return (
    <div className={cn("group rounded-xl border p-3 transition-colors", decisive ? "border-line-2 bg-card-2" : "border-line bg-paper/60", muted && "opacity-75 hover:opacity-100")}>
      <div className="flex flex-wrap items-center gap-1.5">
        <button onClick={() => openClause(e.clause_id)} className="font-mono text-xs font-medium text-accent underline-offset-2 hover:underline" aria-label={`Open source of clause ${e.section}`}>{e.section}</button>
        <span className="text-sm font-medium text-ink">{e.heading}</span>
        <Tag tone={r.tone}>{r.label}</Tag>
        {e.specificity !== "none" && <Tag>{e.specificity === "direct" ? "Names the item" : "Category match"}</Tag>}
        {decisive && <Tag tone="review">Decisive</Tag>}
        <button onClick={() => openClause(e.clause_id)} className="ml-auto inline-flex items-center gap-1 text-[11px] text-faint transition-colors hover:text-accent">
          {e.doc_type === "endorsement" ? "Endorsement" : "Policy"} · p. {e.page ?? "?"} <ExternalLink className="size-3" aria-hidden />
        </button>
      </div>
      {!compact && <blockquote className="mt-2 border-l-2 border-accent/40 pl-3 text-[13px] leading-relaxed text-text">“{e.excerpt}”</blockquote>}
      <p className="mt-2 text-xs text-muted">{e.reason}</p>
      {(e.retrieval?.bm25 != null || e.retrieval?.semantic != null) && (
        <p className="mt-1.5 text-[11px] text-faint num">
          Retrieval relevance (similarity, not proof): BM25 {e.retrieval.bm25 ?? "—"} · semantic {e.retrieval.semantic ?? "—"}
          {e.matched_terms.length > 0 && <> · matched terms: {e.matched_terms.join(", ")}</>}
        </p>
      )}
    </div>
  );
}

export function ClauseRef({ id }: { id: string }) {
  const { openClause } = useClauseViewer();
  return (
    <button type="button" onClick={(ev) => { ev.stopPropagation(); openClause(id); }} title="Open clause source"
      className="rounded-md border border-line-2 bg-ink/[0.03] px-1.5 py-0.5 font-mono text-[11px] text-accent transition-colors hover:border-accent/50 hover:bg-accent/10">
      {sec(id)}
    </button>
  );
}
