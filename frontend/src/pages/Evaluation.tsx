import { Play, Terminal } from "lucide-react";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EmptyState, ErrorNote, PageHeader, Section, Spinner, Tag } from "../components/ui";
import { api } from "../lib/api";
import { cn } from "../lib/format";

const METHOD_LABEL: Record<string, string> = {
  "bm25:raw": "BM25 · raw", "bm25:normalized": "BM25 · normalised", "semantic:raw": "Semantic · raw",
  "semantic:normalized": "Semantic · normalised", "hybrid:normalized": "Hybrid · normalised", "hybrid_rerank:normalized": "Hybrid + rerank · normalised",
};
const LABEL_TEXT: Record<string, string> = { covered: "Covered", excluded: "Excluded", conditional: "Conditional", conflict: "Conflict", insufficient: "Insufficient" };
const f = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v.toFixed(3));

export default function Evaluation() {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [split, setSplit] = useState<"eval" | "dev" | "all">("eval");
  useEffect(() => { api.evalResults().then(setData).catch((e) => setErr(e.status === 404 ? null : e.message)); }, []);

  const run = async () => {
    setBusy(true); setErr(null);
    try { setData(await api.evalRun()); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };

  return (
    <div>
      <PageHeader eyebrow="Evaluation" title="Keyword baseline vs semantic retrieval"
        description="Metrics are computed by actually running the labelled evaluation — nothing on this page is typed in by hand. The dataset is small and synthetic; read the limitations before drawing conclusions."
        actions={<button className="btn-primary" onClick={run} disabled={busy} data-testid="run-eval">{busy ? <Spinner label="Running evaluation…" /> : <><Play className="size-4" /> Run evaluation</>}</button>} />
      <ErrorNote error={err} className="mb-4" />
      {!data ? (
        <EmptyState title="No evaluation results yet" actions={<button className="btn-primary" onClick={run} disabled={busy}>{busy ? <Spinner label="Running…" /> : "Run evaluation"}</button>}>
          Runs ~60 labelled queries through BM25, semantic, hybrid and reranked retrieval plus evidence verification (about 30–60 seconds).
        </EmptyState>
      ) : <Results data={data} split={split} setSplit={setSplit} />}
    </div>
  );
}

function Results({ data, split, setSplit }: { data: any; split: "eval" | "dev" | "all"; setSplit: (s: "eval" | "dev" | "all") => void }) {
  const r = data.results[split];
  const methods = Object.keys(r.retrieval);
  const chart = methods.map((m) => ({ name: METHOD_LABEL[m] ?? m, "Recall@3": r.retrieval[m]["recall@3"], MRR: r.retrieval[m].mrr, "nDCG@5": r.retrieval[m]["ndcg@5"] }));
  const v = r.verification;
  const best = methods.reduce((a, b) => (r.retrieval[b].mrr > r.retrieval[a].mrr ? b : a), methods[0]);
  const bm = r.retrieval["bm25:raw"], se = r.retrieval["semantic:raw"];
  return (
    <div className="space-y-5">
      <div className="grid gap-3 md:grid-cols-4">
        <div className="card p-4"><p className="eyebrow">Queries</p><p className="mt-2 text-xl font-semibold num">{data.dataset.query_count}</p><p className="text-xs text-muted">{data.dataset.retrieval_queries} with relevant clauses · {data.dataset.labeled_items} labelled items</p></div>
        <div className="card p-4"><p className="eyebrow">Split (seed {data.split.seed})</p><p className="mt-2 text-xl font-semibold num">{data.split.dev_queries} / {data.split.eval_queries}</p><p className="text-xs text-muted">dev / eval, group-level (no paraphrase leakage)</p></div>
        <div className="card p-4"><p className="eyebrow">Semantic model</p><p className="mt-2 text-sm font-semibold break-all">{data.configuration.semantic_model}</p><p className="text-xs text-muted">Reranker: {data.configuration.reranker}</p></div>
        <div className="card p-4"><p className="eyebrow">Generated</p><p className="mt-2 text-sm font-semibold">{new Date(data.generated_at).toLocaleString("en-IN")}</p><p className="text-xs text-muted">Runtime {data.runtime_seconds}s · <Tag tone="conditional">Synthetic dataset</Tag></p></div>
      </div>
      <div className="flex gap-1.5" role="tablist" aria-label="Data split">
        {(["eval", "dev", "all"] as const).map((s) => (
          <button key={s} role="tab" aria-selected={split === s} onClick={() => setSplit(s)} className={cn("rounded-full px-3 py-1 text-xs", split === s ? "chip-on" : "bg-card border border-line text-muted")}>
            {s === "eval" ? "Held-out eval split" : s === "dev" ? "Dev split" : "All queries"}</button>
        ))}
      </div>
      <Section title="Retrieval — side by side" description={`${r.retrieval[methods[0]].queries} queries with labelled relevant clauses. "Raw" = bill text as written; "normalised" = after Nivaaran's abbreviation/category lexicon.`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="eval-table">
            <thead><tr className="border-b border-line text-left text-[12px] font-semibold text-muted">
              <th className="py-2 pr-3 font-medium">Method</th>{["Recall@1", "Recall@3", "Recall@5", "Hit@1", "P@3", "MRR", "nDCG@5"].map((h) => <th key={h} className="py-2 pr-3 text-right font-medium">{h}</th>)}</tr></thead>
            <tbody>{methods.map((m) => {
              const x = r.retrieval[m];
              return (<tr key={m} className={cn("border-b border-line", m === best && "bg-covered-bg/40")}>
                <td className="py-2 pr-3 font-medium">{METHOD_LABEL[m] ?? m}{m === best && <Tag tone="covered" className="ml-1.5">best MRR</Tag>}</td>
                {["recall@1", "recall@3", "recall@5", "hit@1", "precision@3", "mrr", "ndcg@5"].map((k) => <td key={k} className="py-2 pr-3 text-right num">{f(x[k])}</td>)}
              </tr>);
            })}</tbody>
          </table>
        </div>
        <div className="mt-4 h-64" role="img" aria-label="Retrieval metrics by method">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart} margin={{ left: 0, right: 8, top: 8 }}>
              <CartesianGrid vertical={false} stroke="#e3ddcf" />
              <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#6c7068" }} interval={0} angle={-12} textAnchor="end" height={56} axisLine={{ stroke: "#d3cab6" }} tickLine={false} />
              <YAxis domain={[0, 1]} tick={{ fontSize: 11, fill: "#6c7068" }} axisLine={false} tickLine={false} width={36} />
              <Tooltip formatter={(val) => Number(val).toFixed(3)} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="Recall@3" fill="#3c5e7f" radius={[2, 2, 0, 0]} />
              <Bar dataKey="MRR" fill="#2e6b50" radius={[2, 2, 0, 0]} />
              <Bar dataKey="nDCG@5" fill="#b69a62" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="mt-2 text-sm text-text">
          Measured on this split: raw-text BM25 MRR {f(bm?.mrr)} vs raw-text semantic MRR {f(se?.mrr)}
          {bm && se && (se.mrr > bm.mrr ? " — semantic retrieval ranks the right clause higher when bill wording differs from policy wording." : se.mrr < bm.mrr ? " — the keyword baseline is stronger here." : " — no difference.")}
          {" "}See error examples below for where each fails.
        </p>
      </Section>
      <div className="grid gap-5 xl:grid-cols-2">
        <Section title="Evidence verification" description={`${v.items} labelled bill items through the production verification path.`}>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-lg bg-paper p-3"><p className="eyebrow">Accuracy</p><p className="mt-1 text-xl font-semibold num">{f(v.accuracy)}</p></div>
            <div className="rounded-lg bg-paper p-3"><p className="eyebrow">Macro-F1</p><p className="mt-1 text-xl font-semibold num">{f(v.macro_f1)}</p></div>
            <div className="rounded-lg bg-paper p-3"><p className="eyebrow">Unsupported answers</p><p className="mt-1 text-xl font-semibold num">{f(v.unsupported_answer_rate)}</p></div>
          </div>
          <p className="mt-2 text-xs text-muted">{v.unsupported_answer_rate_definition}</p>
          <table className="mt-3 w-full text-sm">
            <thead><tr className="border-b border-line text-left text-[12px] font-semibold text-muted"><th className="py-1.5 font-medium">Label</th><th className="py-1.5 text-right font-medium">Precision</th><th className="py-1.5 text-right font-medium">Recall</th><th className="py-1.5 text-right font-medium">F1</th><th className="py-1.5 text-right font-medium">Support</th></tr></thead>
            <tbody>{Object.entries(v.per_label).map(([k, x]: any) => (
              <tr key={k} className="border-b border-line"><td className="py-1.5">{LABEL_TEXT[k]}</td><td className="py-1.5 text-right num">{x.support ? f(x.precision) : "—"}</td><td className="py-1.5 text-right num">{x.support ? f(x.recall) : "—"}</td><td className="py-1.5 text-right num">{x.support ? f(x.f1) : "—"}</td><td className="py-1.5 text-right num">{x.support}</td></tr>))}
              <tr className="border-b border-line"><td className="py-1.5">Ambiguity detection (non-definitive)</td><td className="py-1.5 text-right num">{f(v.ambiguity_detection.precision)}</td><td className="py-1.5 text-right num">{f(v.ambiguity_detection.recall)}</td><td className="py-1.5 text-right num">{f(v.ambiguity_detection.f1)}</td><td className="py-1.5 text-right num">{v.ambiguity_detection.support}</td></tr>
            </tbody>
          </table>
          <p className="eyebrow mt-4 mb-1.5">Confusion (gold → predicted)</p>
          <div className="flex flex-wrap gap-1.5">{v.confusion.map((c: any) => <Tag key={c.gold + c.pred} tone={c.gold === c.pred ? "covered" : "excluded"}>{LABEL_TEXT[c.gold]} → {LABEL_TEXT[c.pred]}: {c.count}</Tag>)}</div>
        </Section>
        <Section title="Error examples" description="Every miss on the selected split's eval portion, as produced by the run.">
          {data.error_examples.length === 0 ? <p className="text-sm text-muted">No errors recorded on the eval split.</p> : (
            <ul className="max-h-[420px] space-y-2 overflow-y-auto pr-1 text-sm">
              {data.error_examples.map((e: any, i: number) => (
                <li key={i} className="rounded-lg border border-line p-2.5">
                  <p><span className="font-mono text-xs text-faint">{e.id}</span> <span className="font-medium">"{e.query}"</span> <Tag tone="excluded">{e.type}</Tag></p>
                  {e.type === "verification" ? <p className="mt-1 text-xs text-muted">gold {e.gold}, predicted {e.pred}. {e.explanation}</p> :
                    <p className="mt-1 text-xs text-muted">expected {e.expected.join(", ")}; top-3 was {e.top3.join(", ") || "(nothing retrieved)"}</p>}
                </li>))}
            </ul>
          )}
        </Section>
      </div>
      <div className="grid gap-5 xl:grid-cols-2">
        <Section title="Configuration & metric definitions">
          <dl className="space-y-1.5 text-sm">
            {Object.entries(data.configuration).filter(([k]) => k !== "query_forms").map(([k, val]) => <div key={k}><dt className="inline text-muted">{k.replaceAll("_", " ")}: </dt><dd className="inline">{String(val)}</dd></div>)}
            {Object.entries(data.metric_definitions).map(([k, val]) => <div key={k}><dt className="inline font-medium">{k}: </dt><dd className="inline text-muted">{String(val)}</dd></div>)}
            <div><dt className="inline text-muted">split method: </dt><dd className="inline">{data.split.method}</dd></div>
          </dl>
        </Section>
        <Section title="Limitations & reproduction">
          <ul className="list-disc space-y-1.5 pl-5 text-sm text-text">{data.limitations.map((l: string) => <li key={l}>{l}</li>)}</ul>
          <p className="eyebrow mt-4 mb-1.5">Reproduce</p>
          <code className="flex items-center gap-2 rounded-lg border border-line-2 bg-paper px-3 py-2 font-mono text-xs text-accent"><Terminal className="size-3.5" aria-hidden />{data.command}</code>
        </Section>
      </div>
    </div>
  );
}
