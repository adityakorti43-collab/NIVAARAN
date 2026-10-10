import { ExternalLink, FileText, ZoomIn } from "lucide-react";
import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { api } from "../lib/api";
import { cn } from "../lib/format";
import type { Clause, DocumentRecord } from "../lib/types";
import { Modal } from "./overlay";
import { SpeakButtons } from "./SpeakButtons";

interface Ctx { openClause: (clauseId: string) => void }
const ClauseCtx = createContext<Ctx>({ openClause: () => {} });
export const useClauseViewer = () => useContext(ClauseCtx);

const CAT: Record<string, string> = {
  coverage: "Coverage", limit: "Coverage with limit", conditional_coverage: "Conditional coverage", exclusion: "Exclusion",
  conditional_exclusion: "Exclusion with exception", waiting_period: "Waiting period", deductible: "Deductible", copayment: "Co-payment",
  computation_order: "Computation order", precedence: "Precedence rule", applicability: "Applicability", claim_requirement: "Claim requirement",
  time_window: "Pre/post hospitalisation", definition: "Definition", other: "Not interpreted",
};

export function ClauseViewerProvider({ children }: { children: ReactNode }) {
  const cache = useRef<Record<string, Promise<DocumentRecord>>>({});
  const [state, setState] = useState<{ clause: Clause; doc: DocumentRecord } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [imgLoaded, setImgLoaded] = useState(false);
  const [zoomed, setZoomed] = useState(false);

  const openClause = useCallback((clauseId: string) => {
    const docId = clauseId.split(":")[0];
    cache.current[docId] ??= api.document(docId);
    setError(null); setImgLoaded(false); setZoomed(false);
    cache.current[docId].then((doc) => {
      const clause = doc.clauses?.find((c) => c.clause_id === clauseId);
      if (clause) setState({ clause, doc });
      else setError("This clause is no longer available.");
    }).catch((e) => { delete cache.current[docId]; setError((e as Error).message); });
  }, []);

  const c = state?.clause;
  const it = c?.interpretation;
  return (
    <ClauseCtx.Provider value={{ openClause }}>
      {children}
      <Modal open={!!state || !!error} onClose={() => { setState(null); setError(null); }} size="xl"
        title={c ? <span><span className="mr-2 font-mono text-accent">{c.section}</span>{c.heading}</span> : "Clause"}
        subtitle={state && <span className="inline-flex items-center gap-1.5"><FileText className="size-3.5" />{state.doc.metadata.title ?? state.doc.filename} · page {c?.page} · {c?.text_source === "ocr" ? "OCR text (unverified)" : "PDF text layer"}{state.doc.synthetic && " · synthetic demo document"}</span>}>
        {error && <p className="text-sm text-excluded">{error}</p>}
        {c && it && state && (
          <div className="grid gap-5 lg:grid-cols-[1fr_1.05fr]">
            <div className="space-y-4">
              <div>
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2"><p className="eyebrow">Exact text</p>
                  <SpeakButtons getText={async (lang) => (await api.explainClause(c.document_id, c.section, lang)).text} /></div>
                <blockquote className="rounded-xl border border-line bg-paper p-4 text-[14px] leading-relaxed text-ink">“{c.text}”</blockquote>
              </div>
              <div>
                <p className="eyebrow mb-2">Structured reading (derived from the text above)</p>
                <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
                  <dt className="text-muted">Type</dt><dd className="text-ink">{CAT[it.category] ?? it.category}</dd>
                  {it.scope_terms.length > 0 && <><dt className="text-muted">Applies to</dt><dd>{it.scope_terms.join(", ")}</dd></>}
                  {it.limit && <><dt className="text-muted">Limit</dt><dd>{it.limit.text}</dd></>}
                  {it.percent && <><dt className="text-muted">Percentage</dt><dd>{it.percent}%</dd></>}
                  {it.condition && <><dt className="text-muted">Condition</dt><dd>{it.condition}</dd></>}
                  {it.waiting_months && <><dt className="text-muted">Waiting</dt><dd>{it.waiting_months} months</dd></>}
                  {it.replaces.length > 0 && <><dt className="text-muted">Replaces</dt><dd>clause {it.replaces.join(", ")}</dd></>}
                  {it.overrides.length > 0 && <><dt className="text-muted">Overrides</dt><dd>{it.overrides.join(", ")}</dd></>}
                  {it.order.length > 0 && <><dt className="text-muted">Order</dt><dd>{it.order.join(" → ")}</dd></>}
                  <dt className="text-muted">Confidence</dt><dd className="capitalize">{c.extraction_confidence} (extraction)</dd>
                </dl>
              </div>
              <p className="text-xs text-faint">The structured reading is pattern-based. The quoted text is the evidence; confirm against the full wording.</p>
            </div>
            <div>
              <div className="mb-2 flex items-center justify-between">
                <p className="eyebrow">Source page {c.page} — clause highlighted</p>
                <div className="flex gap-1">
                  <button className="btn-ghost px-2 py-1 text-xs" onClick={() => setZoomed(!zoomed)} aria-pressed={zoomed}><ZoomIn className="size-3.5" /> {zoomed ? "Fit" : "Zoom"}</button>
                  <a className="btn-ghost px-2 py-1 text-xs" target="_blank" rel="noreferrer"
                    href={`/api/documents/${c.document_id}/pages/${c.page}.png?highlight=${encodeURIComponent(c.clause_id)}&zoom=2.5`}><ExternalLink className="size-3.5" /> Open</a>
                </div>
              </div>
              <div className={cn("relative overflow-auto rounded-xl border border-line bg-white", zoomed ? "max-h-[60dvh]" : "max-h-[60dvh]")}>
                {!imgLoaded && <div className="skeleton aspect-[1/1.414] w-full" />}
                <img alt={`Page ${c.page} of ${state.doc.filename} with clause ${c.section} highlighted`}
                  src={`/api/documents/${c.document_id}/pages/${c.page}.png?highlight=${encodeURIComponent(c.clause_id)}`}
                  onLoad={() => setImgLoaded(true)} className={cn("block", zoomed ? "w-[180%] max-w-none" : "w-full", !imgLoaded && "absolute opacity-0")} />
              </div>
            </div>
          </div>
        )}
      </Modal>
    </ClauseCtx.Provider>
  );
}
