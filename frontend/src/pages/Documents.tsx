import { ChevronDown, FileUp, Search, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { LoadDemoButton } from "../components/NeedClaim";
import { EmptyState, ErrorNote, PageHeader, Section, Spinner, Tag } from "../components/ui";
import { PolicyReader } from "../components/PolicyReader";
import { api } from "../lib/api";
import { cn, fmtDate } from "../lib/format";
import { useApp } from "../lib/store";
import type { Clause, DocumentRecord, PolicyVersion } from "../lib/types";

const CATEGORY_LABEL: Record<string, string> = {
  coverage: "Coverage", limit: "Limit / sub-limit", conditional_coverage: "Conditional coverage", exclusion: "Exclusion",
  conditional_exclusion: "Exclusion with exception", waiting_period: "Waiting period", deductible: "Deductible", copayment: "Co-payment",
  computation_order: "Computation order", precedence: "Precedence", applicability: "Applicability", claim_requirement: "Claim requirement",
  time_window: "Pre/post hospitalisation", definition: "Definition", other: "Not interpreted",
};
const CATEGORY_TONE: Record<string, string> = {
  coverage: "covered", limit: "partial", conditional_coverage: "conditional", exclusion: "excluded", conditional_exclusion: "conditional",
  waiting_period: "review", deductible: "neutral", copayment: "neutral", other: "insufficient",
};

function Uploader() {
  const { refresh } = useApp();
  const [docType, setDocType] = useState<"policy" | "endorsement" | "benefit_summary">("policy");
  const [progress, setProgress] = useState<number | null>(null);
  const [phase, setPhase] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);
  const [last, setLast] = useState<DocumentRecord | null>(null);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  async function handle(file: File | undefined) {
    if (!file) return;
    setErr(null); setLast(null);
    if (file.size > 15 * 1024 * 1024) { setErr("File exceeds the 15 MB limit."); return; }
    if (!/\.(pdf|png|jpe?g)$/i.test(file.name) && !["application/pdf", "image/png", "image/jpeg"].includes(file.type)) { setErr("Upload a PDF, JPEG or PNG file. Policies and endorsements must be PDF files or images of them."); return; }
    try {
      setProgress(0); setPhase("Uploading");
      const doc = await api.uploadDocument(file, docType, (p) => { setProgress(p); if (p === 100) setPhase("Extracting text, segmenting clauses and interpreting provisions"); });
      setLast(doc);
      await refresh();
    } catch (e) { setErr((e as Error).message); } finally { setProgress(null); setPhase(""); if (input.current) input.current.value = ""; }
  }

  return (
    <Section title="Upload policy documents" description="PDF policy wordings and endorsements, up to 15 MB. Files are validated by content, not by extension, and processed locally.">
      <div className="mb-3 flex flex-wrap gap-2" role="radiogroup" aria-label="Document type">
        {(["policy", "endorsement", "benefit_summary"] as const).map((t) => (
          <button key={t} role="radio" aria-checked={docType === t} onClick={() => setDocType(t)}
            className={cn("rounded-lg border px-3 py-1.5 text-sm", docType === t ? "border-accent/40 chip-on" : "border-line-2 text-muted hover:text-text")}>
            {t === "policy" ? "Policy wording" : t === "endorsement" ? "Endorsement / amendment" : "Benefits brochure"}
          </button>
        ))}
      </div>
      <label onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files[0]); }}
        className={cn("flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-8 text-center transition-colors",
          drag ? "border-accent bg-covered-bg/40" : "border-line-2 hover:bg-paper")}>
        <FileUp className="size-6 text-muted" aria-hidden />
        <span className="mt-2 text-sm font-medium text-text">Drop a PDF here or click to choose</span>
        <span className="text-xs text-muted">PDF, JPEG or PNG · uploading as {docType === "policy" ? "policy wording" : docType === "endorsement" ? "endorsement" : "benefits brochure"}</span>
        <input ref={input} type="file" accept="application/pdf,.pdf,image/png,image/jpeg" className="sr-only" data-testid="doc-upload" onChange={(e) => handle(e.target.files?.[0])} />
      </label>
      {progress !== null && (
        <div className="mt-3" aria-live="polite">
          <div className="flex justify-between text-xs text-muted"><span>{phase}…</span><span className="num">{progress}%</span></div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-paper">
            <motion.div className="h-full bg-accent" initial={{ width: 0 }} animate={{ width: `${progress}%` }} />
          </div>
        </div>
      )}
      <ErrorNote error={err} className="mt-3" />
      {last && (
        <div className="mt-3 rounded-lg border border-covered/25 bg-covered-bg px-3 py-2.5 text-sm text-covered" role="status">
          Processed <strong>{last.filename}</strong>: {last.clause_count} clauses on {last.page_count} page(s).
          {last.warnings.length > 0 && <ul className="mt-1 list-disc pl-5 text-conditional">{last.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
        </div>
      )}
    </Section>
  );
}

function Timeline({ policy }: { policy: DocumentRecord }) {
  const [data, setData] = useState<{ versions: PolicyVersion[]; conflicts: string[] } | null>(null);
  const { documents } = useApp();
  useEffect(() => { api.versions(policy.document_id).then(setData).catch(() => setData(null)); }, [policy.document_id, documents.length]);
  if (!data) return <Spinner />;
  return (
    <div>
      <ol className="relative ml-2 border-l border-line-2">
        {data.versions.map((v, i) => (
          <li key={v.version_id} className="mb-5 ml-5">
            <span className={cn("absolute -left-[7px] mt-1 size-3.5 rounded-full border-2 border-card", i === 0 ? "bg-ink" : "bg-accent")} aria-hidden />
            <p className="text-sm font-semibold text-ink">{v.label}</p>
            <p className="text-xs text-muted num">{fmtDate(v.effective_from)} → {fmtDate(v.effective_to)} · {v.active_clause_count} active clauses</p>
            {v.notes.map((n) => <p key={n} className="mt-1 text-xs text-text">{n}</p>)}
          </li>
        ))}
      </ol>
      {data.conflicts.map((c) => <ErrorNote key={c} error={c} className="mt-2" />)}
      <p className="mt-1 text-xs text-muted">Applicability is decided from effective dates and the documents' own applicability statements — never from upload order.</p>
    </div>
  );
}

function ClauseBrowser({ doc }: { doc: DocumentRecord }) {
  const [clauses, setClauses] = useState<Clause[] | null>(null);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { setClauses(null); api.document(doc.document_id).then((d) => setClauses(d.clauses ?? [])); }, [doc.document_id]);
  const shown = useMemo(() => (clauses ?? []).filter((c) => (!cat || c.interpretation.category === cat) &&
    (!q || `${c.section} ${c.heading} ${c.text}`.toLowerCase().includes(q.toLowerCase()))), [clauses, q, cat]);
  if (!clauses) return <Spinner label="Loading clauses…" />;
  const cats = [...new Set(clauses.map((c) => c.interpretation.category))];
  return (
    <div>
      <div className="mb-3 flex flex-col gap-2 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 size-4 text-faint" aria-hidden />
          <input className="input pl-9" placeholder="Search clause text, heading or number" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search clauses" />
        </div>
        <select className="input sm:w-56" value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Filter by category">
          <option value="">All categories</option>
          {cats.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c] ?? c}</option>)}
        </select>
      </div>
      <p className="mb-2 text-xs text-muted">{shown.length} of {clauses.length} clauses</p>
      <ul className="divide-y divide-line rounded-lg border border-line">
        {shown.map((c) => {
          const it = c.interpretation;
          const isOpen = open === c.clause_id;
          return (
            <li key={c.clause_id}>
              <button className="flex w-full items-center gap-3 px-3 py-2.5 text-left hover:bg-paper" aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : c.clause_id)}>
                <span className="w-12 shrink-0 font-mono text-xs text-ink">{c.section}</span>
                <span className="min-w-0 flex-1 truncate text-sm text-text">{c.heading}</span>
                <Tag tone={CATEGORY_TONE[it.category] ?? "neutral"}>{CATEGORY_LABEL[it.category] ?? it.category}</Tag>
                <span className="hidden text-xs text-faint sm:inline">p. {c.page}</span>
                <ChevronDown className={cn("size-4 text-faint transition-transform", isOpen && "rotate-180")} aria-hidden />
              </button>
              {isOpen && (
                <div className="space-y-2 bg-paper/60 px-3 pb-3 pt-1 text-sm">
                  <blockquote className="border-l-2 border-line-2 pl-3 leading-relaxed">"{c.text}"</blockquote>
                  <dl className="grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
                    <Field k="Source" v={`${doc.filename}, page ${c.page} · ${c.text_source === "ocr" ? "OCR text (unverified)" : "PDF text layer"}`} />
                    <Field k="Group" v={c.group || "—"} />
                    {it.scope_terms.length > 0 && <Field k="Terms covered by clause" v={it.scope_terms.join(", ")} />}
                    {it.limit && <Field k="Limit" v={it.limit.text} />}
                    {it.percent && <Field k="Percentage" v={`${it.percent}%`} />}
                    {it.condition && <Field k="Condition" v={it.condition} />}
                    {it.waiting_months && <Field k="Waiting period" v={`${it.waiting_months} months`} />}
                    {it.waiting_days && <Field k="Waiting period" v={`${it.waiting_days} days`} />}
                    {it.replaces.length > 0 && <Field k="Replaces" v={it.replaces.join(", ")} />}
                    {it.overrides.length > 0 && <Field k="Overrides" v={it.overrides.join(", ")} />}
                    {it.order.length > 0 && <Field k="Order" v={it.order.join(" → ")} />}
                    <Field k="Extraction confidence" v={c.extraction_confidence} />
                  </dl>
                  {it.notes.map((n) => <p key={n} className="text-xs text-conditional">{n}</p>)}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

const Field = ({ k, v }: { k: string; v: string }) => (<div><dt className="inline text-muted">{k}: </dt><dd className="inline text-text">{v}</dd></div>);

export default function Documents() {
  const { documents, refresh } = useApp();
  const [selected, setSelected] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const sel = documents.find((d) => d.document_id === selected) ?? documents[0];
  const policies = documents.filter((d) => d.doc_type === "policy");

  return (
    <div>
      <PageHeader eyebrow="Documents" title="Policy documents and versions"
        description="Every clause keeps its document, page and exact text so each conclusion can be traced back to evidence." />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <div className="space-y-5">
          <Uploader />
          <Section title="Documents" description="Select a document to inspect its clauses.">
            {documents.length === 0 ? (
              <EmptyState title="No documents yet" actions={<LoadDemoButton className="btn-secondary" />}>Upload a policy wording to begin.</EmptyState>
            ) : (
              <ul className="space-y-2">
                {documents.map((d) => (
                  <li key={d.document_id}>
                    <div className={cn("flex items-start gap-3 rounded-lg border p-3", sel?.document_id === d.document_id ? "border-ink" : "border-line")}>
                      <button className="min-w-0 flex-1 text-left" onClick={() => setSelected(d.document_id)}>
                        <p className="truncate text-sm font-medium text-text">{d.metadata.title ?? d.filename}</p>
                        <p className="mt-0.5 text-xs text-muted">{d.filename} · {d.page_count} pages · {d.clause_count} clauses</p>
                        <div className="mt-1.5 flex flex-wrap gap-1.5">
                          <Tag
  tone={
    d.doc_type === "policy"
      ? "neutral"
      : d.doc_type === "endorsement"
        ? "partial"
        : "conditional"
  }
>
  {d.doc_type === "policy"
    ? "Policy"
    : d.doc_type === "endorsement"
      ? "Endorsement"
      : d.doc_type === "benefit_summary"
        ? "Benefits Brochure"
        : d.doc_type}
</Tag>
                          <Tag tone={d.status === "processed" ? "covered" : d.status === "failed" ? "excluded" : "conditional"}>{d.status.replaceAll("_", " ")}</Tag>
                          {d.synthetic && <Tag tone="conditional">Synthetic</Tag>}
                          <Tag>Effective {d.metadata.effective_date}</Tag>
                        </div>
                        {d.warnings.length > 0 && <ul className="mt-1.5 list-disc pl-4 text-xs text-conditional">{d.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
                      </button>
                      <a className="btn-ghost p-1.5 text-xs" href={api.downloadUrl(d.document_id)} download aria-label={`Download ${d.filename}`}>↓</a>
                      <button className="btn-ghost p-1.5" aria-label={`Delete ${d.filename}`} onClick={async () => {
                        if (!confirm(`Delete ${d.filename} and its extracted clauses?`)) return;
                        try { await api.deleteDocument(d.document_id); setErr(null); await refresh(); } catch (e) { setErr((e as Error).message); }
                      }}><Trash2 className="size-4" /></button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            <ErrorNote error={err} className="mt-3" />
          </Section>
          {policies.map((p) => (
            <Section key={p.document_id} title="Policy-version timeline" description={p.metadata.title}>
              <Timeline policy={p} />
            </Section>
          ))}
        </div>
        {sel && (
          <div className="min-w-0 space-y-5">
          <Section title="Listen to this policy" description="Hear a short summary in English, Hindi or Marathi, or have the full wording read out clause by clause. Every point cites its clause.">
            <PolicyReader doc={sel} />
          </Section>
          <Section title={`Extracted clauses — ${sel.metadata.title ?? sel.filename}`}
            description={<>Insurer: {sel.metadata.insurer} · Policy no. {sel.metadata.policy_number}{sel.metadata.sum_insured ? ` · Sum insured ${sel.metadata.sum_insured}` : ""}</>}>
            <ClauseBrowser doc={sel} />
          </Section>
          </div>
        )}
      </div>
    </div>
  );
}
