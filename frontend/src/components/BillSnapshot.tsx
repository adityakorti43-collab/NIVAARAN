import { AlertTriangle, BedDouble, CalendarDays, CheckCircle2, Stethoscope, UserRound } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { cn, inr as inrFull } from "../lib/format";
import type { Bill } from "../lib/types";

// Categorical palette in the site's forest × brass family, distinct enough to tell apart at a glance.
const PALETTE = ["#1f5a4a", "#b69a62", "#3c5e7f", "#a2463a", "#7a4e86", "#946617", "#5f8a7a", "#a9b8a5"];

/** Whole rupees without ".00" (the editor below keeps exact paise). */
const inr = (v: string | null | undefined) => inrFull(v).replace(/\.00$/, "");

function nights(a: string | null, b: string | null) {
  if (!a || !b) return null;
  const n = Math.round((Date.parse(b) - Date.parse(a)) / 86_400_000);
  return n >= 0 ? n : null;
}
const day = (d: string | null) => (d ? new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—");
const known = (s: string | null | undefined) => (s && !s.startsWith("Not found") ? s : null);

/**
 * The bill, read at a glance: who and where, the stay, the total (and whether it matches the bill's own total),
 * where the money went by kind of charge, and the biggest single charges.
 */
export function BillSnapshot({ bill }: { bill: Bill }) {
  const reduce = useReducedMotion();
  const total = Number(bill.computed_total) || 0;
  const stated = bill.stated_total ? Number(bill.stated_total) : null;
  const matches = stated === null ? null : Math.abs(stated - total) < 0.5;
  const stay = nights(bill.admission_date, bill.discharge_date);
  const groups = bill.breakdown ?? [];
  const top = groups.slice(0, 7);
  const rest = groups.slice(7).reduce((s, g) => s + Number(g.amount), 0);
  const slices = [...top.map((g, i) => ({ label: g.label, amount: Number(g.amount), count: g.count, color: PALETTE[i % PALETTE.length] })),
    ...(rest > 0 ? [{ label: "Everything else", amount: rest, count: groups.slice(7).reduce((s, g) => s + g.count, 0), color: "#d3cab6" }] : [])];
  const biggest = [...bill.items].sort((a, b) => Number(b.amount) - Number(a.amount)).slice(0, 4);
  const maxItem = Number(biggest[0]?.amount ?? 1) || 1;

  return (
    <div className="overflow-hidden rounded-[6px] border border-line bg-card" data-testid="bill-snapshot">
      {/* Receipt header */}
      <div className="theme-forest relative overflow-hidden bg-forest px-5 py-5 text-ivory">
        <div className="pointer-events-none absolute -left-10 -top-24 size-64 rounded-full bg-brass/15 blur-3xl" aria-hidden />
        <div className="relative flex flex-wrap items-start justify-between gap-5">
          <div className="min-w-0">
            <p className="font-mono text-[10.5px] uppercase tracking-[0.18em] text-brass">Hospital bill</p>
            <h3 className="mt-1.5 font-display text-[30px] leading-tight text-ivory">{known(bill.hospital) ?? "Hospital not stated"}</h3>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-[13px] text-ivory/75">
              {known(bill.patient) && <span className="inline-flex items-center gap-1.5"><UserRound className="size-3.5 text-brass" />{bill.patient}</span>}
              <span className="inline-flex items-center gap-1.5"><CalendarDays className="size-3.5 text-brass" />{day(bill.admission_date)} → {day(bill.discharge_date)}</span>
              {stay !== null && <span className="inline-flex items-center gap-1.5"><BedDouble className="size-3.5 text-brass" />{stay} night{stay === 1 ? "" : "s"}</span>}
              {known(bill.diagnosis) && <span className="inline-flex items-center gap-1.5"><Stethoscope className="size-3.5 text-brass" />{bill.diagnosis}</span>}
            </div>
          </div>
          <div className="text-right">
            <p className="text-[12px] text-ivory/60">Total billed · {bill.items.length} lines</p>
            <p className="font-display text-[42px] leading-none text-ivory num">{inr(bill.computed_total)}</p>
            {matches !== null && (
              <p className={cn("mt-2 inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11.5px]", matches ? "bg-covered/30 text-[#bfe0cf]" : "bg-conditional/30 text-[#f1d9a6]")}>
                {matches ? <CheckCircle2 className="size-3.5" /> : <AlertTriangle className="size-3.5" />}
                {matches ? "Lines add up to the bill's total" : `Bill says ${inr(bill.stated_total)}`}
              </p>)}
          </div>
        </div>
      </div>

      <div className="grid gap-6 p-5 lg:grid-cols-[1.4fr_1fr]">
        {/* Where the money went */}
        {slices.length > 0 && total > 0 && (
          <div>
            <p className="text-[13px] font-semibold text-ink">Where the money went</p>
            <div className="mt-3 flex h-3.5 w-full overflow-hidden rounded-full bg-line" role="img" aria-label="Bill split by type of charge">
              {slices.map((s, i) => (
                <motion.div key={s.label} style={{ backgroundColor: s.color }} title={`${s.label}: ${inr(s.amount.toFixed(2))}`}
                  initial={reduce ? false : { width: 0 }} animate={{ width: `${(s.amount / total) * 100}%` }} transition={{ duration: 0.8, delay: 0.05 * i, ease: [0.22, 1, 0.36, 1] }}
                  className="h-full border-r border-card last:border-r-0" />))}
            </div>
            <ul className="mt-4 grid gap-x-6 gap-y-2 sm:grid-cols-2">
              {slices.map((s) => (
                <li key={s.label} className="flex items-center gap-2.5 text-[13px]">
                  <span className="size-2.5 shrink-0 rounded-[2px]" style={{ backgroundColor: s.color }} aria-hidden />
                  <span className="min-w-0 flex-1 truncate text-text" title={s.label}>{s.label}</span>
                  <span className="text-faint num">{Math.round((s.amount / total) * 100)}%</span>
                  <span className="w-[86px] text-right font-medium text-ink num">{inr(s.amount.toFixed(2))}</span>
                </li>))}
            </ul>
          </div>
        )}

        {/* Biggest single charges */}
        {biggest.length > 0 && (
          <div>
            <p className="text-[13px] font-semibold text-ink">Biggest charges</p>
            <ul className="mt-3 space-y-3">
              {biggest.map((it) => (
                <li key={it.item_id}>
                  <div className="flex items-baseline gap-3 text-[13px]">
                    <span className="min-w-0 flex-1 truncate text-text" title={it.description}>{it.description}</span>
                    <span className="font-medium text-ink num">{inr(it.amount)}</span>
                  </div>
                  <div className="mt-1 h-1 overflow-hidden rounded-full bg-line">
                    <motion.div className="h-full rounded-full bg-gradient-to-r from-brass/50 to-brass" initial={reduce ? false : { width: 0 }}
                      animate={{ width: `${(Number(it.amount) / maxItem) * 100}%` }} transition={{ duration: 0.8, delay: 0.2, ease: [0.22, 1, 0.36, 1] }} />
                  </div>
                </li>))}
            </ul>
          </div>
        )}
      </div>

      {bill.issues.length > 0 && (
        <ul className="space-y-1.5 border-t border-line px-5 py-3">
          {bill.issues.map((i) => (
            <li key={i.message} className={cn("flex items-start gap-2 text-[12.5px]", i.severity === "error" ? "text-excluded" : "text-conditional")}>
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" />{i.message}
            </li>))}
        </ul>
      )}
    </div>
  );
}
