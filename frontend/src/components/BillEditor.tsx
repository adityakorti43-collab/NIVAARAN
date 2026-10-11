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

/** An amount that reads like a receipt (₹14,000). The field's value is never reformatted (so typing and pasting
 *  behave normally); the formatted amount is drawn over it and hidden while you edit. */
function AmountField({ value, onChange, label, invalid }: { value: string; onChange: (v: string) => void; label: string; invalid: boolean }) {
  const [focus, setFocus] = useState(false);
  const pretty = !focus && MONEY_RE.test(value.trim()) ? inr(value.replace(/,/g, "")).replace(/\.00$/, "") : null;
  return (
    <div className="relative">
      <input className={cn(FIELD, "text-right font-medium text-ink num", pretty && "text-transparent caret-transparent", invalid && "border-excluded/60")}
        value={value} inputMode="decimal" aria-label={label} onFocus={() => setFocus(true)} onBlur={() => setFocus(false)} onChange={(e) => onChange(e.target.value)} />
      {pretty && <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-[14px] font-medium text-ink num" aria-hidden>{pretty}</span>}
    </div>
  );
}

// Fields look like the printed bill until you point at or edit them.
const FIELD = "w-full rounded-[4px] border border-transparent bg-transparent px-2 py-1.5 text-[14px] outline-none transition-colors hover:border-line-2 focus:border-accent focus:bg-card";

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
  const changedCount = rows.filter((r) => !r.item_id || (byId[r.item_id] && JSON.stringify(toEdit(byId[r.item_id])) !== JSON.stringify(r))).length + (original.length - rows.filter((r) => r.item_id).length);
  const matches = statedTotal && total ? toPaise(total) === toPaise(statedTotal) : null;

  return (
    <div className="overflow-hidden rounded-[6px] border border-line bg-card">
      <div className="hidden grid-cols-[40px_1fr_70px_140px_36px] gap-2 border-b border-line bg-paper px-3 py-2 font-mono text-[10.5px] uppercase tracking-[0.12em] text-faint md:grid">
        <span>#</span><span className="px-2">As written on the bill</span><span className="px-2 text-right">Qty</span><span className="px-2 text-right">Amount</span><span />
      </div>
      <ul data-testid="bill-editor">
        <AnimatePresence initial={false}>
          {rows.map((r, i) => {
            const orig = r.item_id ? byId[r.item_id] : undefined;
            const changed = orig && JSON.stringify(toEdit(orig)) !== JSON.stringify(r);
            const was = orig && (orig.extracted ?? toEdit(orig));
            return (
              <motion.li key={r.item_id ?? `new-${i}`} layout initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.25, ease }}
                className={cn("group relative grid grid-cols-[1fr_70px_36px] items-center gap-x-2 border-b border-line/70 px-3 py-1 last:border-b-0 md:grid-cols-[40px_1fr_70px_140px_36px]",
                  i % 2 === 1 && "bg-paper/45", bad[i] && "bg-excluded-bg/60", (changed || !orig) && !bad[i] && "bg-conditional-bg/50")}>
                {(changed || !orig) && <span className="absolute inset-y-1 left-0 w-[3px] rounded-r bg-conditional" aria-hidden />}
                <span className="hidden font-mono text-[11.5px] text-faint md:block">{orig ? String(orig.line_no).padStart(2, "0") : "+"}</span>
                <input className={cn(FIELD, "col-span-3 text-text md:col-span-1")} value={r.description} placeholder="What was charged" aria-label={`Line ${orig?.line_no ?? "new"} description`}
                  onChange={(e) => set(i, { description: e.target.value })} />
                <input className={cn(FIELD, "text-right text-muted num")} value={r.quantity} inputMode="decimal" aria-label={`Line ${orig?.line_no ?? "new"} quantity`}
                  onChange={(e) => set(i, { quantity: e.target.value, unit_price: null })} />
                <AmountField value={r.amount} label={`Line ${orig?.line_no ?? "new"} amount`} invalid={bad[i] && !MONEY_RE.test(r.amount.trim())}
                  onChange={(v) => set(i, { amount: v, unit_price: null })} />
                <button type="button" className="grid size-8 place-items-center rounded-[4px] text-faint opacity-60 transition hover:bg-excluded-bg hover:text-excluded group-hover:opacity-100"
                  aria-label={`Remove line ${orig?.line_no ?? "new"}`} onClick={() => setRows(rows.filter((_, j) => j !== i))}>
                  <Trash2 className="size-4" /></button>
                {changed && was && (
                  <p className="col-span-3 pb-1 pl-2 text-[11.5px] text-muted md:col-span-5 md:pl-[50px]">
                    Bill said: {was.description} · qty {was.quantity} · {inr(was.amount)}
                  </p>)}
              </motion.li>);
          })}
        </AnimatePresence>
      </ul>
      <div className="flex flex-wrap items-center gap-2 border-t border-line px-3 py-2">
        <button type="button" className="btn-ghost h-8 px-2.5 text-[12.5px]" onClick={() => setRows([...rows, { description: "", amount: "", quantity: "1", unit_price: null, service_date: null }])}>
          <Plus className="size-3.5" /> Add a line</button>
        {dirty && <button type="button" className="btn-ghost h-8 px-2.5 text-[12.5px]" onClick={() => setRows(original)}><RotateCcw className="size-3.5" /> Undo my changes</button>}
        {dirty && changedCount > 0 && <span className="text-[12px] text-conditional">{changedCount} line{changedCount === 1 ? "" : "s"} changed</span>}
      </div>
      {bad.some(Boolean) && <p className="border-t border-line px-4 py-2 text-xs text-excluded">Each line needs a description, a quantity and an amount such as 1250 or 1,250.50.</p>}
      <div className="theme-forest flex flex-wrap items-center gap-4 bg-forest px-4 py-3.5 text-ivory">
        <div className="min-w-0">
          <p className="text-[11.5px] text-ivory/60">{rows.length} lines · total</p>
          <p className="font-display text-[28px] leading-none num">{total ? inr(total).replace(/\.00$/, "") : "—"}</p>
        </div>
        {matches !== null && (
          <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11.5px]", matches ? "bg-covered/30 text-[#bfe0cf]" : "bg-conditional/30 text-[#f1d9a6]")}>
            {matches ? <><CheckCircle2 className="size-3.5" /> Same as the bill's total</> : <>The bill's own total is {inr(statedTotal)}</>}
          </span>)}
        <div className="flex-1" />
        {onCancel && <button type="button" className="btn h-10 border border-ivory/25 px-4 text-ivory hover:bg-ivory/10" onClick={onCancel}>Cancel</button>}
        <button type="button" className="btn-brass h-10 px-5 font-semibold" data-testid="save-bill" disabled={busy || bad.some(Boolean) || rows.length === 0 || (!dirty && !!onCancel)}
          onClick={() => onSave(rows.map((r) => ({ ...r, description: r.description.trim(), amount: r.amount.replace(/,/g, "").trim(), quantity: String(r.quantity).trim() })))}>
          {busy ? <Spinner label="Recalculating…" /> : <><CheckCircle2 className="size-4" /> {saveLabel}</>}</button>
      </div>
      {error && <div className="p-3"><ErrorNote error={error} /></div>}
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
