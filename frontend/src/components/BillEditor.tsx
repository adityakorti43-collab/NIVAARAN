import { CheckCircle2, Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { cn, fromPaise, inr, toPaise } from "../lib/format";
import type { BillItem, BillItemEdit } from "../lib/types";
import { ease } from "./motion";
import { ErrorNote, Spinner, Tag } from "./ui";

const MONEY_RE = /^\d[\d,]*(\.\d{1,2})?$/;
const QTY_RE = /^\d+(\.\d+)?$/;

export const toEdit = (i: BillItem): BillItemEdit => ({ item_id: i.item_id, description: i.description, amount: i.amount, quantity: i.quantity,
  unit_price: i.unit_price, service_date: i.service_date });

const SOURCE: Record<string, [string, string]> = {
  extracted: ["Extracted", "neutral"], user_corrected: ["Corrected by you", "conditional"], manual: ["Entered by you", "partial"],
};

export function SourceTag({ item }: { item: BillItem }) {
  const [label, tone] = SOURCE[item.source ?? "extracted"];
  return <Tag tone={tone}>{label}</Tag>;
}

/**
 * Editable bill lines. Amounts are validated as decimal strings and summed in integer paise for the preview
 * only; the server recomputes totals and arithmetic checks, and keeps the originally extracted values.
 */
export function BillEditor({ items, statedTotal, busy, error, onSave, onCancel, saveLabel = "Save corrections and re-analyse" }: {
  items: BillItem[]; statedTotal: string | null; busy?: boolean; error?: string | null;
  onSave: (rows: BillItemEdit[]) => void; onCancel?: () => void; saveLabel?: string;
}) {
  const original = useMemo(() => items.map(toEdit), [items]);
  const [rows, setRows] = useState<BillItemEdit[]>(original);
  useEffect(() => setRows(original), [original]);
  const set = (i: number, patch: Partial<BillItemEdit>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const bad = rows.map((r) => !r.description.trim() || !MONEY_RE.test(r.amount.trim()) || !QTY_RE.test(String(r.quantity).trim()));
  const total = bad.some(Boolean) ? null : fromPaise(rows.reduce((s, r) => s + toPaise(r.amount), 0n));
  const dirty = JSON.stringify(rows) !== JSON.stringify(original);
  const byId = Object.fromEntries(items.map((i) => [i.item_id, i]));

  return (
    <div className="space-y-3">
      <div className="hidden grid-cols-[44px_1fr_90px_130px_36px] gap-2 px-1 text-[11px] font-semibold uppercase tracking-wide text-faint md:grid">
        <span>Line</span><span>Description (as billed)</span><span>Qty</span><span className="text-right">Amount ₹</span><span />
      </div>
      <ul className="space-y-2" data-testid="bill-editor">
        <AnimatePresence initial={false}>
          {rows.map((r, i) => {
            const orig = r.item_id ? byId[r.item_id] : undefined;
            const changed = orig && JSON.stringify(toEdit(orig)) !== JSON.stringify(r);
            return (
              <motion.li key={r.item_id ?? `new-${i}`} layout initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.25, ease }}
                className={cn("grid grid-cols-[1fr_90px_36px] gap-2 rounded-xl border p-2 md:grid-cols-[44px_1fr_90px_130px_36px] md:items-center",
                  bad[i] ? "border-excluded/50" : changed || !orig ? "border-conditional/40 bg-conditional-bg/40" : "border-line")}>
                <span className="hidden text-xs text-faint num md:block">{orig ? orig.line_no : "new"}</span>
                <input className="input col-span-3 md:col-span-1" value={r.description} aria-label={`Line ${orig?.line_no ?? "new"} description`}
                  onChange={(e) => set(i, { description: e.target.value })} />
                <input className="input num" value={r.quantity} inputMode="decimal" aria-label={`Line ${orig?.line_no ?? "new"} quantity`}
                  onChange={(e) => set(i, { quantity: e.target.value, unit_price: null })} />
                <input className="input text-right num" value={r.amount} inputMode="decimal" aria-label={`Line ${orig?.line_no ?? "new"} amount`}
                  onChange={(e) => set(i, { amount: e.target.value, unit_price: null })} />
                <button type="button" className="btn-ghost px-2" aria-label={`Remove line ${orig?.line_no ?? "new"}`} onClick={() => setRows(rows.filter((_, j) => j !== i))}>
                  <Trash2 className="size-4" /></button>
                {changed && orig && (
                  <p className="col-span-3 text-[11px] text-muted md:col-span-5 md:pl-[52px]">
                    {orig.extracted ? "Originally extracted" : "Was"}: {(orig.extracted ?? toEdit(orig)).description} · qty {(orig.extracted ?? toEdit(orig)).quantity} · {inr((orig.extracted ?? toEdit(orig)).amount)}
                  </p>)}
              </motion.li>);
          })}
        </AnimatePresence>
      </ul>
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className="btn-ghost text-xs" onClick={() => setRows([...rows, { description: "", amount: "", quantity: "1", unit_price: null, service_date: null }])}>
          <Plus className="size-3.5" /> Add a line</button>
        {dirty && <button type="button" className="btn-ghost text-xs" onClick={() => setRows(original)}><RotateCcw className="size-3.5" /> Undo all changes</button>}
        <div className="flex-1" />
        <p className="text-sm text-muted">Preview total <span className="num font-semibold text-ink">{total ? inr(total) : "—"}</span>
          {statedTotal && total && toPaise(total) !== toPaise(statedTotal) && <span className="ml-2 text-conditional">differs from the stated total {inr(statedTotal)}</span>}</p>
      </div>
      {bad.some(Boolean) && <p className="text-xs text-excluded">Each line needs a description, a quantity and an amount such as 1250 or 1,250.50.</p>}
      <ErrorNote error={error} />
      <div className="flex flex-wrap gap-2">
        <button type="button" className="btn-primary" data-testid="save-bill" disabled={busy || bad.some(Boolean) || rows.length === 0 || (!dirty && !!onCancel)}
          onClick={() => onSave(rows.map((r) => ({ ...r, description: r.description.trim(), amount: r.amount.replace(/,/g, "").trim(), quantity: String(r.quantity).trim() })))}>
          {busy ? <Spinner label="Recalculating…" /> : saveLabel}</button>
        {onCancel && <button type="button" className="btn-secondary" onClick={onCancel}>Cancel</button>}
      </div>
    </div>
  );
}

/** Read-only bill lines with provenance, plus the review controls for a saved claim. */
export function BillReview({ items, removed, reviewedAt, statedTotal, computedTotal, onSave, onConfirm }: {
  items: BillItem[]; removed: BillItem[]; reviewedAt: string | null | undefined; statedTotal: string | null; computedTotal: string;
  onSave: (rows: BillItemEdit[]) => Promise<void>; onConfirm: () => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const run = async (f: () => Promise<void>) => { setBusy(true); setErr(null); try { await f(); setEditing(false); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); } };
  const corrected = items.filter((i) => i.source === "user_corrected").length;
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
        {reviewedAt ? <Tag tone="covered"><CheckCircle2 className="size-3" /> Lines confirmed by you {new Date(reviewedAt).toLocaleString("en-IN")}</Tag>
          : <Tag tone="review">Extracted lines not yet confirmed</Tag>}
        {corrected > 0 && <Tag tone="conditional">{corrected} corrected</Tag>}
        {removed.length > 0 && <Tag>{removed.length} removed</Tag>}
        <span className="text-muted">Total <span className="num font-semibold text-ink">{inr(computedTotal)}</span>{statedTotal && <> · stated on bill {inr(statedTotal)}</>}</span>
        <div className="flex-1" />
        {!editing && <button className="btn-secondary h-8 px-3 text-xs" onClick={() => setEditing(true)} data-testid="edit-bill"><Pencil className="size-3.5" /> Correct lines</button>}
        {!editing && !reviewedAt && <button className="btn-primary h-8 px-3 text-xs" disabled={busy} onClick={() => run(onConfirm)} data-testid="confirm-bill">
          {busy ? <Spinner label="Saving" /> : <><CheckCircle2 className="size-3.5" /> Confirm lines are correct</>}</button>}
      </div>
      {editing ? <BillEditor items={items} statedTotal={statedTotal} busy={busy} error={err} onSave={(rows) => run(() => onSave(rows))} onCancel={() => setEditing(false)} /> : (
        <>
          <ErrorNote error={err} />
          <ul className="max-h-[360px] divide-y divide-line overflow-y-auto rounded-xl border border-line text-sm">
            {items.map((i) => (
              <li key={i.item_id} className="grid grid-cols-[32px_1fr_auto] items-center gap-2 px-3 py-2">
                <span className="text-xs text-faint num">{i.line_no}</span>
                <span className="min-w-0"><span className="text-ink">{i.description}</span> <span className="text-faint">× {i.quantity}</span> <SourceTag item={i} />
                  {i.extracted && <span className="block text-[11px] text-muted">Originally extracted: {i.extracted.description} · qty {i.extracted.quantity} · {inr(i.extracted.amount)}</span>}</span>
                <span className="num text-ink">{inr(i.amount)}</span>
              </li>))}
            {removed.map((i) => (
              <li key={`rm-${i.item_id}`} className="grid grid-cols-[32px_1fr_auto] items-center gap-2 px-3 py-2 opacity-60">
                <span className="text-xs text-faint num">{i.line_no}</span><span className="line-through">{i.description}</span><span className="num line-through">{inr(i.amount)}</span>
              </li>))}
          </ul>
        </>)}
    </div>
  );
}
