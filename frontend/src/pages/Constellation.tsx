import { Background, Controls, MarkerType, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useState } from "react";
import { NeedClaim } from "../components/NeedClaim";
import { ClauseRef, PageHeader, Section, Spinner, StatusBadge, SyntheticBanner, Tag } from "../components/ui";
import { api } from "../lib/api";
import { inr, RELATION_META, sec, STAGE_LABEL, STATUS_META, TONE_HEX } from "../lib/format";
import type { Analysis, ClaimBundle, Clause } from "../lib/types";

type Sel = { kind: string; id: string } | null;

function useClauses(bundle: ClaimBundle) {
  const [clauses, setClauses] = useState<Record<string, Clause> | null>(null);
  useEffect(() => {
    const ids = [bundle.claim.policy_document_id, ...bundle.claim.endorsement_ids];
    Promise.all(ids.map((i) => api.document(i))).then((docs) => {
      const m: Record<string, Clause> = {};
      docs.forEach((d) => d.clauses?.forEach((c) => (m[c.clause_id] = c)));
      setClauses(m);
    });
  }, [bundle.claim.policy_document_id, bundle.claim.endorsement_ids]);
  return clauses;
}

function build(a: Analysis, clauses: Record<string, Clause>) {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const base = { borderRadius: 4, fontSize: 12, padding: 8, border: "1px solid #d3cab6", background: "#fffefa", color: "#3b3e38", boxShadow: "0 10px 24px -18px rgba(20,45,39,.4)" };
  const cats = [...new Set(a.rows.map((r) => r.category))];
  const clauseIds: string[] = [];
  a.rows.forEach((r) => r.supporting_clause_ids.forEach((c) => !clauseIds.includes(c) && clauseIds.push(c)));
  const superseded = a.version.selected?.superseded_sections ?? {};
  Object.entries(superseded).forEach(([old, rep]) => { if (clauseIds.includes(rep) && !clauseIds.includes(old)) clauseIds.push(old); });
  const stageClauses = a.trace_low.flatMap((s) => (["deductible", "copay"].includes(s.stage) ? s.clause_ids : []));
  stageClauses.forEach((c) => !clauseIds.includes(c) && clauseIds.push(c));

  a.rows.forEach((r, i) => {
    const tone = STATUS_META[r.status].tone;
    nodes.push({ id: `item:${r.item_id}`, position: { x: 0, y: i * 62 }, data: { label: `${r.original_description}\n${inr(r.claimed_amount)}` },
      style: { ...base, width: 220, whiteSpace: "pre-line", borderLeft: `4px solid ${TONE_HEX[tone]}` }, sourcePosition: "right" as never, targetPosition: "left" as never });
  });
  cats.forEach((c, i) => {
    nodes.push({ id: `cat:${c}`, position: { x: 290, y: i * (a.rows.length * 62 / Math.max(cats.length, 1)) }, data: { label: c },
      style: { ...base, width: 170, background: "#142d27", color: "#f5f2ea", border: "1px solid #142d27", fontWeight: 600 }, sourcePosition: "right" as never, targetPosition: "left" as never });
  });
  a.rows.forEach((r) => edges.push({ id: `e:i-c:${r.item_id}`, source: `item:${r.item_id}`, target: `cat:${r.category}`, style: { stroke: "#d3cab6" } }));
  const spacing = Math.max(56, (a.rows.length * 62) / Math.max(clauseIds.length, 1));
  clauseIds.forEach((cid, i) => {
    const c = clauses[cid];
    const isOld = cid in superseded;
    const isEnd = c?.doc_type === "endorsement";
    nodes.push({ id: `cl:${cid}`, position: { x: 540, y: i * spacing }, data: { label: `${sec(cid)} ${c?.heading ?? ""}${isOld ? "\n(superseded)" : ""}` },
      style: { ...base, width: 210, whiteSpace: "pre-line", opacity: isOld ? 0.55 : 1, borderStyle: isOld ? "dashed" : "solid",
        background: isEnd ? "#f1ece0" : "#fffefa", borderColor: isEnd ? "#b69a62" : "#d3cab6" }, sourcePosition: "right" as never, targetPosition: "left" as never });
  });
  a.rows.forEach((r) => {
    r.evidence.filter((e) => r.supporting_clause_ids.includes(e.clause_id)).forEach((e) => {
      const tone = RELATION_META[e.relation]?.tone ?? "neutral";
      edges.push({ id: `e:${r.item_id}:${e.clause_id}`, source: `cat:${r.category}`, target: `cl:${e.clause_id}`, label: RELATION_META[e.relation]?.label,
        labelStyle: { fontSize: 10, fill: TONE_HEX[tone] }, style: { stroke: TONE_HEX[tone], strokeWidth: 1.5 }, markerEnd: { type: MarkerType.ArrowClosed, color: TONE_HEX[tone] },
        data: { item: r.item_id } });
    });
  });
  Object.entries(superseded).forEach(([old, rep]) => {
    if (clauseIds.includes(old) && clauseIds.includes(rep))
      edges.push({ id: `e:sup:${old}`, source: `cl:${old}`, target: `cl:${rep}`, label: "replaced by", animated: true, style: { stroke: "#3c5e7f", strokeDasharray: "4 3" }, labelStyle: { fontSize: 10, fill: "#74b0ee" } });
  });
  const steps = a.trace_low.filter((s) => !["billed"].includes(s.stage));
  steps.forEach((s, i) => {
    nodes.push({ id: `st:${s.stage}`, position: { x: 840, y: i * Math.max(70, (a.rows.length * 62) / steps.length) },
      data: { label: `${i + 1}. ${STAGE_LABEL[s.stage] ?? s.stage}\n${inr(s.amount_after)}` },
      style: { ...base, width: 180, whiteSpace: "pre-line", background: s.stage === "estimated_payable" ? "rgba(46,107,80,0.1)" : "#fffefa", color: s.stage === "estimated_payable" ? "#2e6b50" : "#222521", borderColor: s.stage === "estimated_payable" ? "#2e6b50" : "#d3cab6", fontWeight: 600 },
      sourcePosition: "bottom" as never, targetPosition: "top" as never });
    if (i > 0) edges.push({ id: `e:st:${i}`, source: `st:${steps[i - 1].stage}`, target: `st:${s.stage}`, style: { stroke: "#989a90" }, markerEnd: { type: MarkerType.ArrowClosed, color: "#9aa7b8" } });
    s.clause_ids.forEach((cid) => clauseIds.includes(cid) && edges.push({ id: `e:cl-st:${cid}:${s.stage}`, source: `cl:${cid}`, target: `st:${s.stage}`, style: { stroke: "#cfc6b2", strokeDasharray: "2 3" } }));
  });
  return { nodes, edges };
}

export default function Constellation() {
  return (
    <div>
      <PageHeader eyebrow="Claim map" title="How each charge connects to the policy"
        description="Each charge on the left, the clause that decided it in the middle, and the step where the amount changed on the right. Click anything for details." />
      <NeedClaim>{(b) => <Graph bundle={b} />}</NeedClaim>
    </div>
  );
}

function Graph({ bundle }: { bundle: ClaimBundle & { analysis: Analysis } }) {
  const a = bundle.analysis;
  const clauses = useClauses(bundle);
  const [sel, setSel] = useState<Sel>(null);
  const graph = useMemo(() => (clauses ? build(a, clauses) : null), [a, clauses]);
  if (!graph || !clauses) return <Spinner label="Building constellation…" />;
  const nodes = graph.nodes.map((n) => {
    const hl = sel && (n.id === `${sel.kind}:${sel.id}` || graph.edges.some((e) => (e.source === `${sel.kind}:${sel.id}` && e.target === n.id) || (e.target === `${sel.kind}:${sel.id}` && e.source === n.id)));
    return sel ? { ...n, style: { ...n.style, opacity: hl ? 1 : 0.35, boxShadow: n.id === `${sel.kind}:${sel.id}` ? "0 0 0 3px rgba(182,154,98,0.55), 0 0 24px rgba(182,154,98,0.25)" : undefined } } : n;
  });
  return (
    <>
      <SyntheticBanner show={a.synthetic} />
      <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
        <div className="card h-[640px] overflow-hidden" data-testid="constellation">
          <ReactFlow nodes={nodes} edges={graph.edges.map((e) => {
            if (!sel) return e;
            const key = `${sel.kind}:${sel.id}`;
            const on = e.source === key || e.target === key;
            return { ...e, animated: on || e.animated, style: { ...e.style, opacity: on ? 1 : 0.15, strokeWidth: on ? 2.2 : (e.style?.strokeWidth ?? 1) } };
          })} fitView minZoom={0.2} nodesDraggable nodesConnectable={false}
            onNodeClick={(_, n) => { const [kind, ...rest] = n.id.split(":"); setSel({ kind, id: rest.join(":") }); }}
            onPaneClick={() => setSel(null)}>
            <Background gap={24} color="#ddd5c4" />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        <Section title="Details" description={sel ? undefined : "Select a bill item, category, clause or calculation step."}>
          <Detail sel={sel} a={a} clauses={clauses} />
          <div className="mt-5 border-t border-line pt-3">
            <p className="eyebrow mb-2">Legend</p>
            <div className="flex flex-wrap gap-1.5">
              {["support", "limit", "override_support", "exclusion", "conditional_exclusion"].map((r) => <Tag key={r} tone={RELATION_META[r].tone}>{RELATION_META[r].label}</Tag>)}
              <Tag tone="partial">Endorsement clause</Tag><Tag>Dashed = superseded</Tag>
            </div>
          </div>
        </Section>
      </div>
    </>
  );
}

function Detail({ sel, a, clauses }: { sel: Sel; a: Analysis; clauses: Record<string, Clause> }) {
  if (!sel) return null;
  if (sel.kind === "item") {
    const r = a.rows.find((x) => x.item_id === sel.id)!;
    return (<div className="space-y-2 text-sm">
      <p className="font-semibold text-ink">{r.original_description}</p><StatusBadge status={r.status} />
      <p className="text-muted">{r.explanation}</p>
      <p className="num">Claimed {inr(r.claimed_amount)} · payable {r.eligible_amount === null ? `0 – ${inr(r.payable_high)}` : inr(r.payable_low)}</p>
      <div className="flex flex-wrap gap-1">{r.supporting_clause_ids.map((c) => <ClauseRef key={c} id={c} />)}</div>
    </div>);
  }
  if (sel.kind === "cat") {
    const rows = a.rows.filter((r) => r.category === sel.id);
    return (<div className="text-sm"><p className="font-semibold text-ink">{sel.id}</p>
      <ul className="mt-2 space-y-1">{rows.map((r) => <li key={r.item_id} className="flex justify-between gap-2"><span>{r.original_description}</span><StatusBadge status={r.status} short /></li>)}</ul></div>);
  }
  if (sel.kind === "cl") {
    const c = clauses[sel.id];
    const used = a.rows.filter((r) => r.supporting_clause_ids.includes(sel.id));
    const sup = a.version.selected?.superseded_sections ?? {};
    return (<div className="space-y-2 text-sm">
      <p className="font-semibold text-ink">{c?.section} {c?.heading}</p>
      <p className="text-xs text-muted">{c?.doc_type === "endorsement" ? "Endorsement" : "Policy wording"} · page {c?.page}</p>
      {sel.id in sup && <Tag tone="partial">Superseded by {sec(sup[sel.id])} in the applicable version</Tag>}
      <blockquote className="border-l-2 border-line-2 pl-3">"{c?.text}"</blockquote>
      {used.length > 0 && <p className="text-xs text-muted">Decides: {used.map((r) => r.original_description).join(", ")}</p>}
    </div>);
  }
  const s = a.trace_low.find((x) => x.stage === sel.id)!;
  return (<div className="space-y-2 text-sm"><p className="font-semibold text-ink">{STAGE_LABEL[s.stage]}</p><p className="text-muted">{s.description}</p>
    <p className="num">{inr(s.amount_before)} → <strong>{inr(s.amount_after)}</strong></p>
    <div className="flex flex-wrap gap-1">{s.clause_ids.map((c) => <ClauseRef key={c} id={c} />)}</div></div>);
}
