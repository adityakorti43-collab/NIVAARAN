import { AlertTriangle, ArrowRight, Bot, CheckCircle2, FileSearch, HelpCircle, ShieldCheck } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useClauseViewer } from "../components/ClauseViewer";
import { ease } from "../components/motion";
import { NeedClaim } from "../components/NeedClaim";
import { ErrorNote, PageHeader, PageSkeleton, Section, SyntheticBanner, Tag } from "../components/ui";
import { api } from "../lib/api";
import { cn, inr } from "../lib/format";
import { useApp } from "../lib/store";
import type { Analysis, ClaimBundle } from "../lib/types";

const SEV_TONE: Record<string, string> = { high: "conflict", medium: "conditional", low: "partial" };
const STATUS_TONE: Record<string, string> = {
  multiple_issues: "conflict", potential_discrepancy: "conditional", clarification_recommended: "partial",
  no_significant_discrepancy: "covered", insufficient_evidence: "insufficient",
};

type Excerpt = { clause_id: string; section: string; heading: string; page: number | null; text: string; document: string; doc_type: string };

function ExcerptCard({ e, label }: { e: Excerpt; label: string }) {
  const { openClause } = useClauseViewer();
  return (
    <div className="flex h-full flex-col rounded-xl border border-line bg-paper p-3.5">
      <p className="text-[12px] text-muted">{label}</p>
      <p className="mt-0.5 truncate text-[13px] font-semibold text-ink">{e.document}</p>
      <blockquote className="mt-2 flex-1 border-l-2 border-accent/50 pl-3 text-[13.5px] leading-relaxed text-text">“{e.text}”</blockquote>
      <button onClick={() => openClause(e.clause_id)} className="mt-3 self-start text-[12px] font-medium text-accent hover:underline">
        Open clause {e.section} · page {e.page ?? "?"} in the source
      </button>
    </div>
  );
}

export default function Fairness() {
  return (
    <div>
      <PageHeader eyebrow="Mismatch checks" title="Do your documents tell the same story?"
        description="Nivaaran reads your documents side by side and points out where they disagree. Each finding quotes the wording behind it. A clearly written exclusion isn't a mismatch, and nothing here is an accusation of fraud." />
      <NeedClaim>{(b) => <Workspace bundle={b} />}</NeedClaim>
    </div>
  );
}

function Workspace({ bundle }: { bundle: ClaimBundle & { analysis: Analysis } }) {
  const { setSelection, askCopilot } = useApp();
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { setData(null); api.fairness(bundle.claim.claim_id).then(setData).catch((e) => setErr(e.message)); }, [bundle.claim.claim_id, bundle.analysis.analysis_id]);
  if (err) return <ErrorNote error={err} />;
  if (!data) return <PageSkeleton />;
  return (
    <>
      <SyntheticBanner show={bundle.analysis.synthetic} />
      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, ease }}
          className="relative overflow-hidden rounded-[24px] border border-line-2 bg-card p-6">
                    <p className="text-[13px] text-muted">Review status</p>
          <p className="mt-2 flex items-center gap-3 font-display text-[30px] font-bold leading-tight tracking-[-0.02em] text-ink md:text-[38px]" data-testid="fairness-status">
            <span className={cn("size-2.5 shrink-0 rounded-full", `bg-${STATUS_TONE[data.status] ?? "insufficient"}`)} aria-hidden />{data.status_label}</p>
          <p className="mt-3 max-w-xl text-[14px] leading-relaxed text-muted">{data.method}</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <Link to="/actions" className="btn-primary">Draft a clarification request <ArrowRight className="size-4" /></Link>
            <button className="btn-secondary" onClick={() => askCopilot("Is there a discrepancy between these documents?")}><Bot className="size-4" /> Ask about this</button>
          </div>
        </motion.div>
        <Section title="Documents reviewed" description="Only these documents were compared.">
          <ul className="space-y-2">
            {data.documents_reviewed.map((d: any) => (
              <li key={d.document_id} className="flex items-center gap-3 text-sm">
                <FileSearch className="size-4 text-accent" aria-hidden />
                <span className="min-w-0 flex-1 truncate text-ink">{d.title}</span>
                <Tag>{d.doc_type === "benefit_summary" ? "Benefit summary" : d.doc_type === "endorsement" ? "Endorsement" : "Policy"}</Tag>
              </li>))}
          </ul>
          {!data.documents_reviewed.some((d: any) => d.doc_type === "benefit_summary") && (
            <p className="mt-3 text-xs text-muted">Upload a benefits brochure or summary in Documents to compare it with the issued wording.</p>
          )}
        </Section>
      </div>

      <Section title={`Findings (${data.findings.length})`} className="mt-5" description="Severity is how much it could matter. Evidence is how fully the documents establish it. They are rated separately.">
        <ul className="space-y-3" data-testid="findings">
          {data.findings.map((f: any, i: number) => {
            const isOpen = open === f.id;
            return (
              <motion.li key={f.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.04, ease, duration: 0.45 }}
                className={cn("overflow-hidden rounded-2xl border transition-colors", isOpen ? "border-accent/40 bg-card-2" : "border-line bg-card hover:border-line-2")}>
                <button className="flex w-full flex-wrap items-center gap-2.5 p-4 text-left" aria-expanded={isOpen}
                  onClick={() => { setOpen(isOpen ? null : f.id); setSelection({ finding_id: f.id }); }}>
                  {f.severity === "high" ? <AlertTriangle className="size-4 text-conflict" aria-hidden /> : f.category === "ambiguous_clause" ? <HelpCircle className="size-4 text-partial" aria-hidden /> : <AlertTriangle className="size-4 text-conditional" aria-hidden />}
                  <span className="min-w-0 flex-1 text-[15px] font-semibold text-ink">{f.title}</span>
                  <Tag tone={SEV_TONE[f.severity]}>{f.severity} severity</Tag>
                  <Tag>evidence {f.evidence_completeness}</Tag>
                  <Tag tone="neutral">{f.category_label}</Tag>
                </button>
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3, ease }} className="overflow-hidden">
                      <div className="space-y-4 border-t border-line px-4 pb-5 pt-4">
                        <p className="text-[14.5px] leading-relaxed text-text">{f.explanation}</p>
                        {(f.excerpts.length > 0 || f.conflicting_excerpts.length > 0) && (
                          <div className={cn("grid gap-3", f.conflicting_excerpts.length ? "md:grid-cols-2" : "")}>
                            {f.excerpts.map((e: Excerpt) => <ExcerptCard key={e.clause_id} e={e} label={f.conflicting_excerpts.length ? "This document says" : "Evidence"} />)}
                            {f.conflicting_excerpts.map((e: Excerpt) => <ExcerptCard key={e.clause_id} e={e} label="But this document says" />)}
                          </div>
                        )}
                        <div className="grid gap-4 md:grid-cols-3">
                          <div><p className="text-[12.5px] font-semibold text-ink">Why it matters</p><p className="mt-1 text-[13.5px] text-muted">{f.why_it_matters}</p></div>
                          <div><p className="text-[12.5px] font-semibold text-ink">Still unresolved</p><ul className="mt-1 list-disc space-y-0.5 pl-4 text-[13.5px] text-muted">{f.unresolved_questions.map((q: string) => <li key={q}>{q}</li>)}</ul></div>
                          <div><p className="text-[12.5px] font-semibold text-ink">Suggested next steps</p><ul className="mt-1 list-disc space-y-0.5 pl-4 text-[13.5px] text-muted">{f.next_steps.map((q: string) => <li key={q}>{q}</li>)}</ul></div>
                        </div>
                        <button className="btn-secondary text-xs" onClick={() => askCopilot("Explain this discrepancy and whether it means I was misled.")}><Bot className="size-3.5" /> Ask about this finding</button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.li>
            );
          })}
          {data.findings.length === 0 && <li className="text-sm text-muted">No discrepancies were found in the reviewed documents. That does not prove none exist.</li>}
        </ul>
      </Section>

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Section title="Documented restrictive terms" description="Exclusions applied by clearly worded clauses. These are contract terms, not evidence of misconduct.">
          <ul className="space-y-2">
            {data.restrictive_terms.map((r: any) => (
              <li key={r.item} className="flex items-start gap-3 rounded-xl border border-line p-3 text-sm">
                <ShieldCheck className="mt-0.5 size-4 text-muted" aria-hidden />
                <div className="min-w-0 flex-1"><p className="font-medium text-ink">{r.item} <span className="text-muted num">· {inr(r.amount)}</span></p>
                  <p className="text-xs text-muted">{r.excerpts.map((e: Excerpt) => e.section).join(", ")} · {r.note}</p></div>
              </li>))}
            {data.restrictive_terms.length === 0 && <p className="text-sm text-muted">None in this claim.</p>}
          </ul>
        </Section>
        <Section title="Checks that passed" description="Consistency checks with no issue found.">
          <ul className="space-y-1.5">
            {data.checks.map((c: any, i: number) => (
              <li key={i} className="flex items-start gap-2.5 text-sm">
                {c.result === "consistent" ? <CheckCircle2 className="mt-0.5 size-4 text-covered" aria-label="consistent" /> : <HelpCircle className="mt-0.5 size-4 text-muted" aria-label={c.result} />}
                <span><span className="text-ink">{c.check}</span> <span className="text-muted">— {c.detail}</span></span>
              </li>))}
          </ul>
          <ul className="mt-4 list-disc space-y-1 pl-4 text-xs text-faint">{data.limitations.map((l: string) => <li key={l}>{l}</li>)}</ul>
        </Section>
      </div>
    </>
  );
}
