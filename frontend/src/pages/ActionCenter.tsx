import { Check, ClipboardCopy, Download, FileQuestion, ListChecks, MessageSquareText } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { useClauseViewer } from "../components/ClauseViewer";
import { ease } from "../components/motion";
import { NeedClaim } from "../components/NeedClaim";
import { PolicyChecklistView } from "../components/PolicyMode";
import { Disclaimer, ErrorNote, PageHeader, PageSkeleton, Range, Section, SyntheticBanner } from "../components/ui";
import { api } from "../lib/api";
import { inr, sec } from "../lib/format";
import type { Analysis, ClaimBundle } from "../lib/types";

export default function ActionCenter() {
  return (
    <div>
      <PageHeader eyebrow="Next steps" title="What to do next"
        description="Questions to put to your insurer, documents worth finding, and a draft letter. Nivaaran never sends anything: you read it, edit it and send it yourself." />
      <NeedClaim policyView={(p) => <PolicyChecklistView policy={p} />}>{(b) => <Center bundle={b} />}</NeedClaim>
    </div>
  );
}

function Center({ bundle }: { bundle: ClaimBundle & { analysis: Analysis } }) {
  const { openClause } = useClauseViewer();
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [letter, setLetter] = useState("");
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    api.actions(bundle.claim.claim_id).then((d) => { setData(d); setLetter(d.letter); }).catch((e) => setErr(e.message));
  }, [bundle.claim.claim_id, bundle.analysis.analysis_id]);
  if (err) return <ErrorNote error={err} />;
  if (!data) return <PageSkeleton />;
  const s = data.summary;
  return (
    <>
      <SyntheticBanner show={bundle.analysis.synthetic} />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[["Estimated payable", <Range low={s.payable[0]} high={s.payable[1]} />], ["Potential out-of-pocket", <Range low={s.patient[0]} high={s.patient[1]} />],
          ["Items needing review", `${s.review_items}`], ["Document mismatches", s.fairness_status]].map(([k, v], i) => (
          <motion.div key={k as string} className="card p-4" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05, ease }}>
            <p className="text-[12.5px] text-muted">{k}</p><p className="mt-2 text-[17px] font-semibold text-ink">{v}</p>
          </motion.div>))}
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[1fr_1.1fr]">
        <div className="space-y-5">
          <Section title={`Questions to ask (${data.questions.length})`} description="Each one comes from a specific ledger item or finding.">
            <ol className="space-y-2.5" data-testid="questions">
              {data.questions.map((q: any, i: number) => (
                <li key={i} className="flex gap-3 rounded-xl border border-line p-3">
                  <span className="grid size-6 shrink-0 place-items-center rounded-full bg-accent/15 text-[12px] font-semibold text-accent num">{i + 1}</span>
                  <div className="min-w-0 text-sm">
                    <p className="text-ink">{q.question}</p>
                    {q.clauses?.length > 0 && <p className="mt-1 flex flex-wrap gap-1">{[...new Set<string>(q.clauses)].slice(0, 4).map((c) => (
                      <button key={c} onClick={() => openClause(c)} className="rounded-md border border-line-2 px-1.5 py-0.5 font-mono text-[11px] text-accent hover:border-accent/60">{sec(c)}</button>))}</p>}
                  </div>
                </li>))}
            </ol>
          </Section>
          <Section title="Documents to gather" description="Information the analysis could not establish.">
            <ul className="space-y-1.5">{data.missing_documents.map((m: string) => <li key={m} className="flex items-start gap-2 text-sm"><FileQuestion className="mt-0.5 size-4 text-conditional" aria-hidden />{m}</li>)}
              {data.missing_documents.length === 0 && <li className="text-sm text-muted">Nothing missing.</li>}</ul>
          </Section>
          <Section title="Unresolved amounts" description="Not counted in the definite estimate.">
            <ul className="space-y-1.5">{data.unresolved_inputs.map((u: any) => (
              <li key={u.item} className="flex items-center justify-between gap-3 text-sm"><span className="text-ink">{u.item}</span><span className="num text-muted">{inr(u.range[0])} – {inr(u.range[1])}</span></li>))}</ul>
          </Section>
        </div>
        <Section title="Clarification request (draft)" description="Edit freely. It asks questions and makes no accusations."
          actions={<div className="flex gap-2">
            <button className="btn-secondary h-9 text-xs" onClick={async () => { try { await navigator.clipboard.writeText(letter); setCopied(true); setTimeout(() => setCopied(false), 1800); } catch { setCopied(false); } }}>
              {copied ? <><Check className="size-3.5" /> Copied</> : <><ClipboardCopy className="size-3.5" /> Copy</>}</button>
            <a className="btn-secondary h-9 text-xs" download="nivaaran-clarification-request.txt" href={`data:text/plain;charset=utf-8,${encodeURIComponent(letter)}`}><Download className="size-3.5" /> .txt</a>
          </div>}>
          <label htmlFor="letter" className="sr-only">Clarification request</label>
          <textarea id="letter" data-testid="letter" value={letter} onChange={(e) => setLetter(e.target.value)}
            className="input min-h-[520px] resize-y font-mono text-[13px] leading-relaxed" />
          <div className="mt-4 rounded-xl border border-line bg-paper p-3.5">
            <p className="flex items-center gap-2 text-[13px] font-semibold text-ink"><ListChecks className="size-4 text-accent" aria-hidden /> General steps</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px] text-muted">{data.general_steps.map((g: string) => <li key={g}>{g}</li>)}</ul>
          </div>
          <p className="mt-3 flex items-start gap-2 text-xs text-faint"><MessageSquareText className="mt-0.5 size-3.5" aria-hidden />Nivaaran does not cite legal deadlines or regulations. Check rules that apply in your jurisdiction before relying on any timeline.</p>
          <Disclaimer className="mt-2" />
        </Section>
      </div>
    </>
  );
}
