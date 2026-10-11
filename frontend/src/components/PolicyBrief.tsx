import { Ban, CheckCircle2, Hourglass, Scale, ShieldCheck, Wallet, XCircle, type LucideIcon } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { cn } from "../lib/format";
import type { PolicySummary } from "../lib/types";
import { useClauseViewer } from "./ClauseViewer";

type Lang = "en" | "hi";
const T = {
  en: { glance: "At a glance", deductible: "You pay first", perYear: "each year", copay: "Co-payment", ofClaim: "of each claim", room: "Room rent cap",
    window: "Before & after a stay", days: "days", months: "months", before: "before", after: "after", clauses: "clauses read", noFacts: "No deductible, co-payment or caps were found in this document." },
  hi: { glance: "एक नज़र में", deductible: "पहले आप देंगे", perYear: "हर साल", copay: "को-पेमेंट", ofClaim: "हर क्लेम का", room: "कमरे के किराये की सीमा",
    window: "भर्ती से पहले और बाद", days: "दिन", months: "महीने", before: "पहले", after: "बाद", clauses: "धाराएँ पढ़ी गईं", noFacts: "इस दस्तावेज़ में डिडक्टिबल, को-पेमेंट या सीमाएँ नहीं मिलीं।" },
};

const ACRONYMS: Record<string, string> = { icu: "ICU", ct: "CT", mri: "MRI", opd: "OPD", ot: "OT", iv: "IV", ecg: "ECG", hiv: "HIV" };
/** "icu charges" → "ICU charges"; first letter capitalised. */
function label(s: string) {
  const t = s.split(" ").map((w) => ACRONYMS[w.toLowerCase().replace(/[^a-z]/g, "")] ? w.replace(/[a-z]+/i, (m) => ACRONYMS[m.toLowerCase()]) : w).join(" ");
  return t.charAt(0).toUpperCase() + t.slice(1);
}
/** Whole-rupee amounts read better without ".00". */
const tidy = (s: string) => label(s.replace(/(\d)\.00(?!\d)/g, "$1"));
/** "Sahaay Secure Health Plan - Policy Wording (Version 1.0)" → "Sahaay Secure Health Plan". */
const shortTitle = (t: string) => t.replace(/\(.*?\)/g, "").split(/\s+[-–—:|]\s+/)[0].replace(/\b(policy wording|wording)\b/i, "").trim() || t;

/** "₹5,000" (Indian grouping, no paise when whole). */
function rupees(v: string) {
  const n = Number(v);
  return "₹" + n.toLocaleString("en-IN", { maximumFractionDigits: n % 1 ? 2 : 0 });
}

const TONES = {
  covered: { icon: ShieldCheck, ring: "text-covered bg-covered-bg", bar: "bg-covered" },
  limits: { icon: Scale, ring: "text-partial bg-partial-bg", bar: "bg-partial" },
  you_pay: { icon: Wallet, ring: "text-conditional bg-conditional-bg", bar: "bg-conditional" },
  waiting: { icon: Hourglass, ring: "text-review bg-review-bg", bar: "bg-brass" },
  excluded: { icon: Ban, ring: "text-excluded bg-excluded-bg", bar: "bg-excluded" },
} satisfies Record<string, { icon: LucideIcon; ring: string; bar: string }>;
type ToneKey = keyof typeof TONES;
const ORDER: ToneKey[] = ["covered", "limits", "you_pay", "waiting", "excluded"];

function ClauseChip({ docId, clause }: { docId: string; clause: string }) {
  const { openClause } = useClauseViewer();
  return (
    <button type="button" onClick={() => openClause(`${docId}:${clause}`)} aria-label={`Open clause ${clause}`}
      className="shrink-0 rounded-[3px] border border-line-2 px-1.5 py-px font-mono text-[10.5px] text-muted transition-colors hover:border-accent hover:text-accent">{clause}</button>
  );
}

function Card({ tone, title, count, children, i, wide }: { tone: ToneKey; title: string; count: number; children: ReactNode; i: number; wide?: boolean }) {
  const reduce = useReducedMotion();
  const { icon: Icon, ring, bar } = TONES[tone];
  return (
    <motion.section initial={reduce ? false : { opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45, delay: 0.06 * i, ease: [0.22, 1, 0.36, 1] }}
      className={cn("relative overflow-hidden rounded-[6px] border border-line bg-card", wide && "lg:col-span-2")} data-testid={`brief-${tone}`}>
      <div className={cn("absolute inset-x-0 top-0 h-[3px]", bar)} aria-hidden />
      <header className="flex items-center gap-3 px-4 pb-2 pt-4">
        <span className={cn("grid size-9 place-items-center rounded-full", ring)}><Icon className="size-[18px]" strokeWidth={1.8} /></span>
        <h3 className="flex-1 text-[15px] font-semibold tracking-tight text-ink">{title}</h3>
        <span className="rounded-full border border-line-2 px-2 py-0.5 font-mono text-[11px] text-muted">{count}</span>
      </header>
      <div className="px-4 pb-4">{children}</div>
    </motion.section>
  );
}

/**
 * The practical summary, laid out to be read at a glance: the key numbers first, then colour-coded sections
 * (covered, limits, what you pay, waiting periods, not covered). Every point keeps its clause chip.
 */
export function PolicyBrief({ summary, docId, lang, clauseCount, title }: { summary: PolicySummary; docId: string; lang: Lang; clauseCount?: number; title?: string }) {
  const t = T[lang];
  const f = summary.facts;
  const room = f?.limits.find((l) => /room/i.test(l.label));
  // Sections arrive in a fixed order with empty ones omitted, so pair them with the non-empty kinds by position.
  const present = f ? ORDER.filter((k) => (f.counts[k] ?? 0) > 0) : ORDER.slice(0, summary.sections.length);
  const sections: Partial<Record<ToneKey, PolicySummary["sections"][number]>> = {};
  present.forEach((k, i) => { sections[k] = summary.sections[i]; });
  const maxMonths = Math.max(12, ...(f?.waits ?? []).map((w) => w.months ?? (w.days ?? 0) / 30));

  const tiles = [
    f?.deductible && { label: t.deductible, value: rupees(f.deductible.amount), sub: t.perYear, clause: f.deductible.clause },
    f?.copay && { label: t.copay, value: `${f.copay.percent}%`, sub: t.ofClaim, clause: f.copay.clause },
    room && { label: t.room, value: rupees(room.amount), sub: room.basis, clause: room.clause },
    f?.window && { label: t.window, value: `${f.window.before ?? 0} · ${f.window.after ?? 0}`, sub: `${t.days} ${t.before} · ${t.after}`, clause: f.window.clause },
  ].filter(Boolean) as { label: string; value: string; sub: string; clause: string }[];

  return (
    <div className="space-y-5" lang={lang} data-testid="practical-summary">
      {/* At a glance: the numbers that decide most claims */}
      <div className="theme-forest relative overflow-hidden rounded-[6px] bg-forest px-5 py-5 text-ivory">
        <div className="pointer-events-none absolute -right-16 -top-20 size-64 rounded-full bg-brass/15 blur-3xl" aria-hidden />
        <div className="relative flex flex-wrap items-baseline justify-between gap-2">
          <p className={cn("text-brass", lang === "en" ? "font-mono text-[10.5px] uppercase tracking-[0.18em]" : "text-[13px] font-medium")}>{t.glance}</p>
          {clauseCount ? <p className="text-[12px] text-ivory/60">{clauseCount} {t.clauses}</p> : null}
        </div>
        <h3 className="relative mt-1.5 font-display text-[34px] leading-tight text-ivory">{shortTitle(title ?? summary.title)}</h3>
        {tiles.length > 0 ? (
          <div className={cn("relative mt-4 grid grid-cols-2 gap-px overflow-hidden rounded-[4px] bg-ivory/10", tiles.length >= 4 ? "lg:grid-cols-4" : tiles.length === 3 ? "lg:grid-cols-3" : "lg:grid-cols-2")}>
            {tiles.map((x) => (
              <div key={x.label} className="bg-forest/95 px-4 py-3.5">
                <p className="text-[11.5px] text-ivory/60">{x.label}</p>
                <p className="mt-1 font-display text-[30px] leading-none text-ivory">{x.value}</p>
                <div className="mt-1.5 flex items-center justify-between gap-2"><span className="text-[11.5px] text-ivory/55">{x.sub}</span><ClauseChipDark docId={docId} clause={x.clause} /></div>
              </div>))}
          </div>
        ) : <p className="relative mt-3 text-[13px] text-ivory/60">{t.noFacts}</p>}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {present.map((k, i) => {
          const s = sections[k];
          if (!s) return null;
          const wide = i === present.length - 1 && present.length % 2 === 1;   // an odd last card spans the full width
          if (k === "limits" && f?.limits.length) return (
            <Card key={k} tone={k} title={s.heading} count={f.limits.length} i={i} wide={wide}>
              <ul className="divide-y divide-line">
                {f.limits.map((l) => (
                  <li key={l.clause + l.label} className="flex items-center gap-3 py-2">
                    <span className="min-w-0 flex-1 text-[13.5px] text-text">{label(l.label)}</span>
                    <span className="whitespace-nowrap rounded-full bg-partial-bg px-2.5 py-0.5 text-[12.5px] font-semibold text-partial num">{rupees(l.amount)}<span className="font-normal text-partial/75"> {l.basis}</span></span>
                    <ClauseChip docId={docId} clause={l.clause} />
                  </li>))}
              </ul>
            </Card>
          );
          if (k === "waiting" && f?.waits.length) return (
            <Card key={k} tone={k} title={s.heading} count={f.waits.length} i={i} wide={wide}>
              <ul className="space-y-3 pt-1">
                {f.waits.map((w) => {
                  const m = w.months ?? (w.days ?? 0) / 30;
                  return (
                    <li key={w.clause + w.label}>
                      <div className="flex items-baseline gap-3">
                        <span className="min-w-0 flex-1 text-[13.5px] text-text">{label(w.label)}</span>
                        <span className="whitespace-nowrap text-[12.5px] font-semibold text-review num">{w.months ? `${w.months} ${t.months}` : `${w.days} ${t.days}`}</span>
                        <ClauseChip docId={docId} clause={w.clause} />
                      </div>
                      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-line">
                        <motion.div className="h-full rounded-full bg-gradient-to-r from-brass/60 to-brass" initial={{ width: 0 }} animate={{ width: `${Math.max(4, (m / maxMonths) * 100)}%` }} transition={{ duration: 0.9, delay: 0.3, ease: [0.22, 1, 0.36, 1] }} />
                      </div>
                    </li>);
                })}
              </ul>
            </Card>
          );
          const Icon = k === "excluded" ? XCircle : CheckCircle2;
          return (
            <Card key={k} tone={k} title={s.heading} count={s.items.length} i={i} wide={wide}>
              <ul className={cn("grid gap-x-8 gap-y-2", wide && "md:grid-cols-2")}>
                {s.items.map((it) => (
                  <li key={it.clause + it.text} className="flex items-start gap-2.5">
                    <Icon className={cn("mt-0.5 size-4 shrink-0", k === "excluded" ? "text-excluded" : k === "you_pay" ? "text-conditional" : "text-covered")} strokeWidth={1.8} />
                    <span className="min-w-0 flex-1 text-[13.5px] leading-snug text-text">{tidy(it.text)}</span>
                    <ClauseChip docId={docId} clause={it.clause} />
                  </li>))}
              </ul>
            </Card>
          );
        })}
      </div>
      {present.length === 0 && <p className="text-sm text-muted">No covered items, limits, waiting periods or exclusions could be read from this document's clauses. Open the clauses below to read the wording.</p>}
      <p className="text-[12px] text-faint">{summary.outro}</p>
    </div>
  );
}

function ClauseChipDark({ docId, clause }: { docId: string; clause: string }) {
  const { openClause } = useClauseViewer();
  return (
    <button type="button" onClick={() => openClause(`${docId}:${clause}`)} aria-label={`Open clause ${clause}`}
      className="rounded-[3px] border border-ivory/20 px-1.5 py-px font-mono text-[10.5px] text-ivory/65 transition-colors hover:border-brass hover:text-brass">{clause}</button>
  );
}
