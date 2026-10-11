import { ArrowRight, ChevronDown, Download, FileText, FileUp, Search, Trash2 } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
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

const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

type DocKind = "policy" | "endorsement" | "benefit_summary";
const KIND_LABEL: Record<DocKind, string> = { policy: "policy wording", endorsement: "endorsement / amendment", benefit_summary: "benefits brochure" };

type Uploaded = DocumentRecord;

/** Upload state shared by the drop box and the summary panel (which offers "wrong type? re-file it"). */
function useUpload(onDone: (doc: Uploaded) => void) {
  const { refresh } = useApp();
  const [progress, setProgress] = useState<number | null>(null);
  const [phase, setPhase] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);

  async function handle(f: File | undefined, kind: "auto" | DocKind = "auto") {
    if (!f) return;
    setErr(null);
    if (f.size > 15 * 1024 * 1024) { setErr("File exceeds the 15 MB limit."); return; }
    if (!/\.(pdf|png|jpe?g)$/i.test(f.name) && !["application/pdf", "image/png", "image/jpeg"].includes(f.type)) { setErr("Upload a PDF, JPEG or PNG file of your policy, endorsement or brochure."); return; }
    try {
      setFile(f); setProgress(0); setPhase("Uploading");
      const doc = await api.uploadDocument(f, kind, (pc) => { setProgress(pc); if (pc === 100) setPhase("Reading the document and its clauses"); });
      await refresh();
      onDone(doc as Uploaded);
    } catch (e) { setErr((e as Error).message); } finally { setProgress(null); setPhase(""); }
  }
  return { handle, progress, phase, err, file };
}
type Upload = ReturnType<typeof useUpload>;

function Progress({ up }: { up: Upload }) {
  if (up.progress === null) return null;
  return (
    <div className="mt-3" aria-live="polite">
      <div className="flex justify-between text-xs text-muted"><span>{up.phase}…</span><span className="num">{up.progress}%</span></div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-paper">
        <motion.div className="h-full bg-accent" initial={{ width: 0 }} animate={{ width: `${up.progress}%` }} />
      </div>
    </div>
  );
}

/** One upload box. Nivaaran works out whether the file is a policy wording, an endorsement or a brochure. */
function Uploader({ up, onCancel }: { up: Upload; onCancel?: () => void }) {
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const pick = (f: File | undefined) => { void up.handle(f).finally(() => { if (input.current) input.current.value = ""; }); };
  return (
    <Section title="Upload a document" description="Your policy wording, an endorsement or a benefits brochure: PDF, JPEG or PNG, up to 15 MB. Nivaaran works out which it is."
      actions={onCancel && up.progress === null ? <button type="button" className="btn-ghost text-sm" onClick={onCancel}>Back to the summary</button> : undefined}>
      <label onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
        className={cn("flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-10 text-center transition-colors",
          drag ? "border-accent bg-covered-bg/40" : "border-line-2 hover:bg-paper", up.progress !== null && "pointer-events-none opacity-60")}>
        <FileUp className="size-6 text-muted" aria-hidden />
        <span className="mt-2 text-sm font-medium text-text">Drop a file here or click to choose</span>
        <span className="text-xs text-muted">PDF, JPEG or PNG · the document type is detected automatically</span>
        <input ref={input} type="file" accept="application/pdf,.pdf,image/png,image/jpeg" className="sr-only" data-testid="doc-upload" onChange={(e) => pick(e.target.files?.[0])} />
      </label>
      <Progress up={up} />
      <ErrorNote error={up.err} className="mt-3" />
    </Section>
  );
}

/** What just happened to the upload, shown at the top of the summary that replaces the upload box. */
function UploadResult({ doc, up }: { doc: Uploaded; up: Upload }) {
  const kind = doc.doc_type as DocKind;
  return (
    <div className="mb-5 rounded-lg border border-covered/25 bg-covered-bg px-3 py-2.5 text-sm text-covered" role="status" data-testid="upload-result">
      Saved <strong>{doc.filename}</strong> as {kind === "endorsement" ? "an" : "a"} <strong>{KIND_LABEL[kind]}</strong>: {plural(doc.clause_count, "clause")} on {plural(doc.page_count, "page")}.
      {doc.warnings.length > 0 && <ul className="mt-1 list-disc pl-5 text-conditional">{doc.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
      {up.file && (
        <p className="mt-2 text-[12.5px] text-muted">Wrong type? Save it as:{" "}
          {(Object.keys(KIND_LABEL) as DocKind[]).filter((k) => k !== kind).map((k, i) => (
            <span key={k}>{i > 0 && " · "}<button type="button" className="font-medium text-accent underline-offset-2 hover:underline" onClick={() => up.handle(up.file!, k)} data-testid={`refile-${k}`}>{KIND_LABEL[k]}</button></span>
          ))}
        </p>
      )}
      <Progress up={up} />
      <ErrorNote error={up.err} className="mt-2" />
    </div>
  );
}

const DOT: Record<string, string> = {
  covered: "bg-covered", partial: "bg-partial", conditional: "bg-conditional", excluded: "bg-excluded", review: "bg-brass",
  neutral: "bg-line-2", insufficient: "bg-insufficient",
};
const dot = (cat: string) => DOT[CATEGORY_TONE[cat] ?? "neutral"] ?? "bg-line-2";
const rupees = (v: string) => { const n = Number(String(v).replace(/[^\d.]/g, "")); return Number.isFinite(n) && n > 0 ? "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: 0 }) : v; };

function Timeline({ policy }: { policy: DocumentRecord }) {
  const [data, setData] = useState<{ versions: PolicyVersion[]; conflicts: string[] } | null>(null);
  const { documents } = useApp();
  useEffect(() => { api.versions(policy.document_id).then(setData).catch(() => setData(null)); }, [policy.document_id, documents.length]);
  if (!data) return <Spinner />;
  const today = new Date().toISOString().slice(0, 10);
  return (
    <div>
      <ol className="relative space-y-4">
        <span className="absolute bottom-3 left-[11px] top-3 w-px bg-gradient-to-b from-brass/70 via-line-2 to-line" aria-hidden />
        {data.versions.map((v, i) => {
          const current = (!v.effective_from || v.effective_from <= today) && (!v.effective_to || today <= v.effective_to);
          return (
            <li key={v.version_id} className="relative pl-9">
              <span className={cn("absolute left-0 top-0.5 grid size-[23px] place-items-center rounded-full border-2 font-mono text-[10px]",
                current ? "border-brass bg-forest text-ivory" : "border-line-2 bg-card text-muted")} aria-hidden>{i + 1}</span>
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-[14px] font-semibold text-ink">{v.label}</p>
                {current && <span className="rounded-full bg-covered-bg px-2 py-px text-[11px] font-medium text-covered">In force today</span>}
              </div>
              <p className="mt-1 inline-flex items-center gap-1.5 rounded-[3px] bg-paper px-2 py-0.5 text-[12px] text-muted num">
                {fmtDate(v.effective_from)} <ArrowRight className="size-3" /> {fmtDate(v.effective_to)}
                <span className="text-faint">·</span> {v.active_clause_count} clauses
              </p>
              {v.notes.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {v.notes.map((n) => <li key={n} className="border-l-2 border-brass/40 pl-2.5 text-[12.5px] leading-snug text-text">{n}</li>)}
                </ul>)}
            </li>);
        })}
      </ol>
      {data.conflicts.map((c) => <ErrorNote key={c} error={c} className="mt-3" />)}
      <p className="mt-4 text-[11.5px] text-faint">Which wording applies is decided by effective dates and the documents' own statements, never by upload order.</p>
    </div>
  );
}

function ClauseBrowser({ doc }: { doc: DocumentRecord }) {
  const [clauses, setClauses] = useState<Clause[] | null>(null);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { setClauses(null); setCat(""); setQ(""); api.document(doc.document_id).then((d) => setClauses(d.clauses ?? [])); }, [doc.document_id]);
  const shown = useMemo(() => (clauses ?? []).filter((c) => (!cat || c.interpretation.category === cat) &&
    (!q || `${c.section} ${c.heading} ${c.text}`.toLowerCase().includes(q.toLowerCase()))), [clauses, q, cat]);
  if (!clauses) return <Spinner label="Loading clauses…" />;
  const counts = clauses.reduce<Record<string, number>>((m, c) => ({ ...m, [c.interpretation.category]: (m[c.interpretation.category] ?? 0) + 1 }), {});
  const cats = Object.keys(counts).sort((x, y) => counts[y] - counts[x]);
  return (
    <div>
      <div className="relative">
        <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-faint" aria-hidden />
        <input className="input h-11 pl-9" placeholder="Search the wording: a word, a heading or a clause number" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search clauses" />
      </div>
      <div className="-mx-1 mt-3 flex flex-wrap gap-1.5 px-1" role="radiogroup" aria-label="Filter by category">
        {["", ...cats].map((c) => (
          <button key={c || "all"} type="button" role="radio" aria-checked={cat === c} onClick={() => setCat(c)}
            className={cn("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] transition-colors",
              cat === c ? "border-ink bg-ink text-paperwhite" : "border-line-2 text-muted hover:border-ink/40 hover:text-ink")}>
            {c && <span className={cn("size-1.5 rounded-full", dot(c))} aria-hidden />}
            {c ? CATEGORY_LABEL[c] ?? c : "All"}
            <span className={cn("num", cat === c ? "text-paperwhite/70" : "text-faint")}>{c ? counts[c] : clauses.length}</span>
          </button>))}
      </div>
      {/* kept for keyboard users and the existing filter shortcut */}
      <select className="sr-only" value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Filter by category" tabIndex={-1}>
        <option value="">All categories</option>
        {cats.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c] ?? c}</option>)}
      </select>
      <p className="mb-2 mt-4 text-[12px] text-faint">{shown.length === clauses.length ? `${clauses.length} clauses` : `${shown.length} of ${clauses.length} clauses`}</p>
      {shown.length === 0 && <p className="rounded-[4px] border border-dashed border-line-2 px-4 py-6 text-center text-sm text-muted">No clause matches “{q}”.</p>}
      <ul className="overflow-hidden rounded-[6px] border border-line">
        {shown.map((c, idx) => {
          const it = c.interpretation;
          const isOpen = open === c.clause_id;
          const chapter = c.section.split(".")[0];
          const newChapter = idx === 0 || shown[idx - 1].section.split(".")[0] !== chapter;
          return (
            <li key={c.clause_id} className={cn(newChapter && idx > 0 && "border-t-2 border-line", !newChapter && "border-t border-line/70")}>
              <button className={cn("group flex w-full items-center gap-3 px-4 py-3 text-left transition-colors", isOpen ? "bg-paper" : "hover:bg-paper/70")}
                aria-expanded={isOpen} onClick={() => setOpen(isOpen ? null : c.clause_id)}>
                <span className={cn("size-2 shrink-0 rounded-full", dot(it.category))} aria-hidden />
                <span className="w-11 shrink-0 font-mono text-[12px] text-muted">{c.section}</span>
                <span className="min-w-0 flex-1 truncate text-[14px] text-ink">{c.heading}</span>
                <span className="hidden shrink-0 text-[12px] text-muted md:inline">{CATEGORY_LABEL[it.category] ?? it.category}</span>
                <span className="hidden w-9 shrink-0 text-right text-[11.5px] text-faint sm:inline">p.{c.page}</span>
                <ChevronDown className={cn("size-4 shrink-0 text-faint transition-transform group-hover:text-ink", isOpen && "rotate-180")} aria-hidden />
              </button>
              {isOpen && (
                <motion.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} className="space-y-3 bg-paper px-4 pb-4 pl-[46px] text-sm">
                  <blockquote className="font-display text-[17px] leading-relaxed text-ink">“{c.text}”</blockquote>
                  <div className="flex flex-wrap gap-1.5">
                    <Tag tone={CATEGORY_TONE[it.category] ?? "neutral"}>{CATEGORY_LABEL[it.category] ?? it.category}</Tag>
                    {it.limit && <Tag tone="partial">Limit: {it.limit.text}</Tag>}
                    {it.percent && <Tag tone="conditional">{it.percent}%</Tag>}
                    {it.waiting_months && <Tag tone="review">{it.waiting_months} months wait</Tag>}
                    {it.waiting_days && <Tag tone="review">{it.waiting_days} days wait</Tag>}
                    {it.replaces.length > 0 && <Tag tone="conflict">Replaces {it.replaces.join(", ")}</Tag>}
                  </div>
                  <dl className="grid gap-x-6 gap-y-1 text-[12px] sm:grid-cols-2">
                    {it.scope_terms.length > 0 && <Field k="Applies to" v={it.scope_terms.join(", ")} />}
                    {it.condition && <Field k="Condition" v={it.condition} />}
                    {it.overrides.length > 0 && <Field k="Overrides" v={it.overrides.join(", ")} />}
                    {it.order.length > 0 && <Field k="Order" v={it.order.join(" → ")} />}
                    <Field k="Source" v={`${doc.filename}, page ${c.page} · ${c.text_source === "ocr" ? "OCR text (unverified)" : "PDF text layer"}`} />
                    {c.group && <Field k="Part" v={c.group} />}
                    <Field k="Reading confidence" v={c.extraction_confidence} />
                  </dl>
                  {it.notes.map((n) => <p key={n} className="text-xs text-conditional">{n}</p>)}
                </motion.div>
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
  const [last, setLast] = useState<Uploaded | null>(null);
  const [uploading, setUploading] = useState(false);
  const up = useUpload((doc) => { setLast(doc); setSelected(doc.document_id); setUploading(false); window.scrollTo({ top: 0, behavior: "smooth" }); });
  const showUploader = uploading || !sel;
  const [confirming, setConfirming] = useState<{ id: string; claims?: string[] } | null>(null);
  const [deleting, setDeleting] = useState(false);
  async function remove(id: string, withClaims: boolean) {
    setDeleting(true); setErr(null);
    try {
      await api.deleteDocument(id, withClaims);
      setConfirming(null);
      if (last?.document_id === id) setLast(null);
      if (selected === id) setSelected(null);
      await refresh();
    } catch (e) {
      const x = e as Error & { status?: number; body?: { claims?: string[] } };
      if (x.status === 409 && x.body?.claims) setConfirming({ id, claims: x.body.claims });   // ask again, naming the claims
      else setErr(x.message);
    } finally { setDeleting(false); }
  }
  const policies = documents.filter((d) => d.doc_type === "policy");

  return (
    <div>
      <PageHeader eyebrow="Documents" title="Policy documents and versions"
        description="Every clause keeps its document, page and exact text so each conclusion can be traced back to evidence." />
      {/* The upload box, or, once a document is in, its practical summary in the same place. */}
      <div className="mb-5">
        {showUploader ? <Uploader up={up} onCancel={sel ? () => setUploading(false) : undefined} /> : (
          <Section title={`In plain words: ${sel.metadata.title ?? sel.filename}`}
            description="A practical summary of what this document covers, limits and excludes, with a spoken explanation in English or Hindi. Tap a clause number to see the exact wording."
            actions={<button type="button" className="btn-secondary" onClick={() => setUploading(true)} data-testid="upload-another"><FileUp className="size-4" /> Upload another document</button>}>
            {last && last.document_id === sel.document_id && <UploadResult doc={last} up={up} />}
            <PolicyReader doc={sel} />
          </Section>
        )}
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)]">
        <div className="min-w-0 space-y-5">
          <Section title="Your documents" description="Tap one to see its summary and wording.">
            {documents.length === 0 ? (
              <EmptyState title="No documents yet">Upload your policy wording above to begin. Add any endorsements and your benefits brochure too.</EmptyState>
            ) : (
              <ul className="space-y-2.5">
                {documents.map((d) => {
                  const active = sel?.document_id === d.document_id;
                  const kind = d.doc_type === "policy" ? ["Policy wording", "bg-forest text-ivory"] : d.doc_type === "endorsement" ? ["Endorsement", "bg-partial text-paperwhite"] : ["Brochure", "bg-brass text-forest"];
                  const eff = d.metadata.effective_date && !String(d.metadata.effective_date).startsWith("Not found") ? fmtDate(String(d.metadata.effective_date)) : null;
                  return (
                  <li key={d.document_id}>
                    <div className={cn("group relative flex items-center gap-3.5 rounded-[6px] border bg-card p-3.5 transition-all",
                      active ? "border-brass shadow-[0_8px_24px_-16px_rgb(20_45_39/0.45)]" : "border-line hover:border-line-2")}>
                      {active && <span className="absolute inset-y-3 left-0 w-[3px] rounded-r bg-brass" aria-hidden />}
                      <span className={cn("grid size-11 shrink-0 place-items-center rounded-[6px]", kind[1])}><FileText className="size-5" strokeWidth={1.6} /></span>
                      <button className="min-w-0 flex-1 text-left" onClick={() => { setSelected(d.document_id); setUploading(false); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
                        <p className="truncate text-[14px] font-semibold text-ink" title={d.metadata.title ?? d.filename}>{d.metadata.title ?? d.filename}</p>
                        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[12px] text-muted">
                          <span>{kind[0]}</span><span className="text-faint">·</span>
                          <span className="num">{plural(d.clause_count, "clause")}, {plural(d.page_count, "page")}</span>
                          {eff && <><span className="text-faint">·</span><span>from {eff}</span></>}
                          <span className="text-faint">·</span>
                          <span className={cn("inline-flex items-center gap-1", d.status === "processed" ? "text-covered" : d.status === "failed" ? "text-excluded" : "text-conditional")}>
                            <span className="size-1.5 rounded-full bg-current" aria-hidden />{d.status === "processed" ? "Read" : d.status.replaceAll("_", " ")}</span>
                        </p>
                        {d.warnings.length > 0 && <ul className="mt-1.5 list-disc pl-4 text-xs text-conditional">{d.warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
                      </button>
                      <div className="flex shrink-0 items-center opacity-70 transition-opacity group-hover:opacity-100">
                        <a className="btn-ghost p-1.5" href={api.downloadUrl(d.document_id)} download aria-label={`Download ${d.filename}`}><Download className="size-4" /></a>
                        <button className="btn-ghost p-1.5 hover:text-excluded" aria-label={`Delete ${d.filename}`} data-testid={`delete-${d.document_id}`}
                          onClick={() => { setErr(null); setConfirming(confirming?.id === d.document_id ? null : { id: d.document_id }); }}><Trash2 className="size-4" /></button>
                      </div>
                    </div>
                    {confirming?.id === d.document_id && (
                      <div className="mt-1.5 rounded-[6px] border border-excluded/30 bg-excluded-bg px-3.5 py-3 text-sm text-text" role="alertdialog" aria-label="Confirm delete">
                        {confirming.claims
                          ? <p>{confirming.claims.length === 1 ? "A saved claim" : `${confirming.claims.length} saved claims`} ({confirming.claims.map((c) => `“${c}”`).join(", ")}) {confirming.claims.length === 1 ? "uses" : "use"} this document. Delete the document and {confirming.claims.length === 1 ? "that claim" : "those claims"} too?</p>
                          : <p>Delete <strong>{d.filename}</strong> and everything read from it? This can't be undone.</p>}
                        <div className="mt-2.5 flex gap-2">
                          <button type="button" className="btn border border-excluded/40 bg-surface text-excluded hover:bg-excluded/10" disabled={deleting} data-testid="confirm-delete"
                            onClick={() => remove(d.document_id, !!confirming.claims)}>{deleting ? "Deleting…" : confirming.claims ? "Delete document and claims" : "Delete"}</button>
                          <button type="button" className="btn-ghost" onClick={() => setConfirming(null)}>Cancel</button>
                        </div>
                      </div>
                    )}
                  </li>);
                })}
              </ul>
            )}
            <ErrorNote error={err} className="mt-3" />
          </Section>
          {policies.map((p) => (
            <Section key={p.document_id} title="How the policy changed over time" description={p.metadata.title}>
              <Timeline policy={p} />
            </Section>
          ))}
        </div>
        {sel && (
          <div className="min-w-0 space-y-5">
          <Section title="The wording, clause by clause"
            description={<>{[sel.metadata.insurer, sel.metadata.policy_number && `Policy ${sel.metadata.policy_number}`, sel.metadata.sum_insured && `Sum insured ${rupees(String(sel.metadata.sum_insured))}`].filter((x) => x && !String(x).includes("Not found")).join(" · ")}</>}>
            <ClauseBrowser doc={sel} />
          </Section>
          </div>
        )}
      </div>
    </div>
  );
}
