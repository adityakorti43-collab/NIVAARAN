import { Search } from "lucide-react";
import { useState } from "react";
import { NeedClaim } from "../components/NeedClaim";
import { EmptyState, ErrorNote, EvidenceCard, PageHeader, Section, Spinner, StatusBadge, SyntheticBanner, Tag } from "../components/ui";
import { api } from "../lib/api";
import { cn, inr } from "../lib/format";
import type { Analysis, ClaimBundle, Evidence } from "../lib/types";

const METHODS: { key: string; label: string; note: string }[] = [
  { key: "bm25", label: "Keyword baseline (BM25)", note: "Exact-term overlap" },
  { key: "semantic", label: "Semantic embeddings", note: "Meaning similarity" },
  { key: "hybrid", label: "Hybrid (RRF)", note: "Fused ranking" },
  { key: "hybrid_rerank", label: "Hybrid + reranker", note: "Cross-encoder re-ordering" },
];

export default function EvidenceExplorer() {
  return (
    <div>
      <PageHeader eyebrow="Evidence explorer" title="Inspect retrieval: what matched, and why"
        description="See which clauses each retrieval method proposes, and how verification accepts or rejects them. Relevance scores measure textual similarity only — they are never treated as the probability of coverage." />
      <NeedClaim>{(b) => <Explorer bundle={b} />}</NeedClaim>
    </div>
  );
}

function Explorer({ bundle }: { bundle: ClaimBundle & { analysis: Analysis } }) {
  const a = bundle.analysis;
  const [q, setQ] = useState("");
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [item, setItem] = useState(a.rows[0]?.item_id);
  const row = a.rows.find((r) => r.item_id === item);

  async function search(text: string) {
    if (!text.trim()) return;
    setBusy(true); setErr(null); setQ(text);
    try { setRes(await api.evidence(bundle.claim.claim_id, text)); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }

  return (
    <>
      <SyntheticBanner show={a.synthetic} />
      <Section title="Search the applicable policy version" description={`Searching ${a.version.selected?.label ?? "—"} (superseded clauses excluded by metadata filter).`}>
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); search(q); }}>
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 size-4 text-faint" aria-hidden />
            <input className="input pl-9" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Try: Nebuliser kit, IV fluids, attendant charges, dental scaling" aria-label="Evidence query" data-testid="evidence-query" />
          </div>
          <button className="btn-primary" disabled={busy || !q.trim()}>{busy ? <Spinner label="Searching" /> : "Search"}</button>
        </form>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {["Nebuliser kit for in-patient use", "Anesthesia charges", "Dental scaling", "Face masks"].map((s) => (
            <button key={s} className="rounded-full bg-paper px-2.5 py-1 text-xs text-muted hover:text-text" onClick={() => search(s)}>{s}</button>
          ))}
        </div>
        <ErrorNote error={err} className="mt-3" />
        {res && (
          <div className="mt-4">
            <p className="text-sm text-muted">Normalised query: <span className="font-medium text-text">{res.normalized_query}</span> · category <Tag>{res.category}</Tag></p>
            <div className="mt-3 grid gap-4 lg:grid-cols-2 2xl:grid-cols-4">
              {METHODS.map((m) => (
                <div key={m.key}>
                  <p className="text-sm font-semibold text-ink">{m.label}</p>
                  <p className="mb-2 text-xs text-muted">{m.note}{m.key === "semantic" ? ` · ${res.config.semantic_model}` : ""}{m.key === "hybrid_rerank" ? ` · ${res.config.reranker}` : ""}</p>
                  <ol className="space-y-2">
                    {res.results[m.key].slice(0, 5).map((h: { rank: number; score: number; evidence: Evidence }) => (
                      <li key={h.evidence.clause_id} className="flex gap-2">
                        <span className="mt-2.5 w-5 shrink-0 text-right text-xs text-faint num">{h.rank}</span>
                        <div className="min-w-0 flex-1">
                          <EvidenceCard e={{ ...h.evidence, retrieval: {} }} compact />
                          <p className="mt-0.5 text-[11px] text-faint num">score {h.score}</p>
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-faint">{res.note}</p>
          </div>
        )}
      </Section>

      <Section title="Evidence for a ledger item" className="mt-5" description="The candidates retrieved for an item, its decisive evidence, and the candidates rejected by verification.">
        <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
          <ul className="space-y-1">
            {a.rows.map((r) => (
              <li key={r.item_id}>
                <button onClick={() => setItem(r.item_id)} className={cn("flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-sm", item === r.item_id ? "chip-on" : "hover:bg-paper")}>
                  <span className="truncate">{r.original_description}</span>
                  {item !== r.item_id && <StatusBadge status={r.status} short />}
                </button>
              </li>
            ))}
          </ul>
          {row ? (
            <div className="min-w-0 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold text-ink">{row.original_description}</p><StatusBadge status={row.status} />
                <span className="text-sm text-muted num">claimed {inr(row.claimed_amount)}</span>
              </div>
              <p className="text-sm text-text">{row.explanation}</p>
              <div className="grid gap-x-4 text-xs text-muted sm:grid-cols-4">
                <span>Retrieval relevance: see scores per clause</span><span>Evidence support: {row.evidence_quality}</span>
                <span>Calculation: {row.eligible_amount === null ? "unresolved" : "deterministic"}</span><span>Review: {row.manual_review ? "required" : "not required"}</span>
              </div>
              {row.missing_information.length > 0 && <p className="text-sm text-review">Missing: {row.missing_information.join("; ")}</p>}
              {row.evidence.map((e) => <EvidenceCard key={e.clause_id} e={e} decisive={row.supporting_clause_ids.includes(e.clause_id)} />)}
            </div>
          ) : <EmptyState title="Select an item" />}
        </div>
      </Section>
    </>
  );
}
