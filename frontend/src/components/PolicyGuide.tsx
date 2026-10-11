import { AlertTriangle, BadgeIndianRupee, Ban, BedDouble, CalendarClock, ClipboardList, FileCheck2, Hospital, Hourglass, Info, Lightbulb, Percent, ShieldCheck, Wallet, type LucideIcon } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../lib/api";

import type { DocumentRecord, PolicyChecklist, PolicySummary } from "../lib/types";
import { useClauseViewer } from "./ClauseViewer";
import { Section } from "./ui";

/* Plain-language help built around the user's own policy numbers. Anything that is general advice rather than
   something the policy says is labelled "General guidance". */

const rupees = (v: number | string) => "₹" + Math.round(Number(v)).toLocaleString("en-IN");
const known = (v: unknown) => v !== null && v !== undefined && v !== "" && !String(v).includes("Not found");

export function usePolicyFacts(policy: DocumentRecord) {
  const [sum, setSum] = useState<PolicySummary | null>(null);
  const [ck, setCk] = useState<PolicyChecklist | null>(null);
  useEffect(() => {
    let live = true;
    setSum(null); setCk(null);
    api.policySummary(policy.document_id, "en").then((s) => live && setSum(s)).catch(() => {});
    api.policyChecklist(policy.document_id).then((c) => live && setCk(c)).catch(() => {});
    return () => { live = false; };
  }, [policy.document_id]);
  const si = known(policy.metadata.sum_insured) ? Number(String(policy.metadata.sum_insured).replace(/,/g, "")) : null;
  return { sum, ck, si, facts: sum?.facts };
}

function Ref({ docId, section }: { docId: string; section?: string }) {
  const { openClause } = useClauseViewer();
  if (!section) return null;
  return <button type="button" onClick={() => openClause(`${docId}:${section}`)} className="rounded-[3px] border border-line-2 px-1.5 py-px font-mono text-[10.5px] text-muted hover:border-accent hover:text-accent" aria-label={`Open clause ${section}`}>{section}</button>;
}

export function GeneralNote({ children }: { children: ReactNode }) {
  return <p className="flex items-start gap-2 rounded-[6px] bg-paper px-3 py-2 text-[12.5px] text-muted"><Info className="mt-0.5 size-3.5 shrink-0" /><span><span className="font-semibold text-text">General guidance.</span> {children}</span></p>;
}

/* ------------------------------------------------------------------ Key terms, with this policy's numbers */
export function KeyTerms({ policy }: { policy: DocumentRecord }) {
  const { facts: f, ck, si } = usePolicyFacts(policy);
  const id = policy.document_id;
  const room = f?.limits.find((l) => /room/i.test(l.label));
  const longest = ck?.waits.reduce<PolicyChecklist["waits"][number] | null>((m, w) => (!m || (w.months ?? 0) > (m.months ?? 0) ? w : m), null);
  const excluded = f?.counts.excluded ?? 0;
  const terms: { icon: LucideIcon; term: string; mean: string; yours: ReactNode; ex?: string; clause?: string }[] = [
    { icon: ShieldCheck, term: "Sum insured", mean: "The most the insurer will pay in a policy year, across all claims put together.",
      yours: si ? rupees(si) : "Not stated in this document",
      ex: si ? `If you claim ${rupees(si * 0.6)} in March, ${rupees(si * 0.4)} is left for the rest of the policy year.` : undefined },
    { icon: Wallet, term: "Deductible", mean: "An amount you pay yourself before the insurer starts paying.",
      yours: f?.deductible ? `${rupees(f.deductible.amount)} each year` : "None found", clause: f?.deductible?.clause,
      ex: f?.deductible ? `On a ${rupees(50000)} bill, you pay the first ${rupees(f.deductible.amount)}; the insurer looks at the remaining ${rupees(Math.max(0, 50000 - Number(f.deductible.amount)))}.` : undefined },
    { icon: Percent, term: "Co-payment", mean: "A share of every claim that you always pay, even after the deductible.",
      yours: f?.copay ? `${f.copay.percent}% of each claim` : "None found", clause: f?.copay?.clause,
      ex: f?.copay ? `If ${rupees(40000)} is approved, you pay ${rupees(40000 * Number(f.copay.percent) / 100)} and the insurer pays ${rupees(40000 * (1 - Number(f.copay.percent) / 100))}.` : undefined },
    { icon: BedDouble, term: "Room rent cap", mean: "The most the policy pays for your hospital room per day. Choosing a costlier room means you pay the difference.",
      yours: room ? `${rupees(room.amount)} ${room.basis}` : "No cap found", clause: room?.clause,
      ex: room ? `A room costing ${rupees(Number(room.amount) + 2000)} a day for 3 days: you pay ${rupees(2000 * 3)} of the room charges yourself.` : undefined },
    { icon: Hourglass, term: "Waiting period", mean: "Time you must hold the policy before some illnesses or treatments are covered.",
      yours: longest ? `${ck!.waits.length} found; longest ${longest.months ? `${longest.months} months` : `${longest.days} days`}` : "None found", clause: longest?.clause,
      ex: longest?.covered_from ? `${longest.label}: covered from ${new Date(longest.covered_from).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}.` : undefined },
    { icon: Ban, term: "Exclusion", mean: "Something the policy does not pay for at all, such as gloves, toiletries or cosmetic treatment.",
      yours: excluded ? `${excluded} listed` : "None found", ex: excluded ? "Check the “What is not covered” list before you're admitted, and keep those costs aside." : undefined },
  ];
  return (
    <Section title="Insurance words, explained with your policy" description="What each term means, what your policy says, and a quick example.">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {terms.map((t) => (
          <div key={t.term} className="flex flex-col rounded-[6px] border border-line bg-card p-4">
            <div className="flex items-center gap-2.5">
              <span className="grid size-8 place-items-center rounded-full bg-covered-bg text-accent"><t.icon className="size-4" /></span>
              <p className="flex-1 text-[14.5px] font-semibold text-ink">{t.term}</p>
              <Ref docId={id} section={t.clause} />
            </div>
            <p className="mt-2 text-[13px] leading-relaxed text-muted">{t.mean}</p>
            <p className="mt-3 text-[13px] text-muted">Your policy: <span className="font-semibold text-ink">{f || ck ? t.yours : "…"}</span></p>
            {t.ex && <p className="mt-2 rounded-[4px] bg-paper px-2.5 py-1.5 text-[12.5px] leading-snug text-text"><span className="font-medium text-accent">Example: </span>{t.ex}</p>}
          </div>))}
      </div>
    </Section>
  );
}

/* ------------------------------------------------------------------ Bill split slider */
export function BillSplit({ policy }: { policy: DocumentRecord }) {
  const { facts: f, si } = usePolicyFacts(policy);
  const [bill, setBill] = useState(100000);
  const ded = f?.deductible ? Number(f.deductible.amount) : 0;
  const pct = f?.copay ? Number(f.copay.percent) : 0;
  const { you, insurer, capped } = useMemo(() => {
    const afterDed = Math.max(0, bill - ded);
    let ins = afterDed * (1 - pct / 100);
    const cap = si ?? Infinity;
    const capped = ins > cap;
    ins = Math.min(ins, cap);
    return { you: bill - ins, insurer: ins, capped };
  }, [bill, ded, pct, si]);
  return (
    <Section title="Try a bill amount" description="Slide to see how a hospital bill would be shared, using your deductible and co-payment.">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[13px] text-muted">Hospital bill</p>
        <p className="font-display text-[34px] leading-none text-ink num">{rupees(bill)}</p>
      </div>
      <input type="range" min={10000} max={1000000} step={5000} value={bill} onChange={(e) => setBill(Number(e.target.value))} className="mt-3 w-full accent-[#1f5a4a]" aria-label="Hospital bill amount" />
      <div className="mt-5 flex h-4 overflow-hidden rounded-full bg-line" role="img" aria-label="Who pays">
        <motion.div className="h-full bg-accent" animate={{ width: `${(insurer / bill) * 100}%` }} transition={{ duration: 0.3 }} />
        <motion.div className="h-full bg-brass" animate={{ width: `${(you / bill) * 100}%` }} transition={{ duration: 0.3 }} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <div className="rounded-[6px] bg-covered-bg p-3"><p className="text-[12px] text-covered">Insurer pays</p><p className="mt-0.5 font-display text-[26px] text-ink num">{rupees(insurer)}</p></div>
        <div className="rounded-[6px] bg-review-bg p-3"><p className="text-[12px] text-review">You pay</p><p className="mt-0.5 font-display text-[26px] text-ink num">{rupees(you)}</p>
          <p className="text-[11.5px] text-muted">{[ded && `${rupees(Math.min(ded, bill))} deductible`, pct && `${pct}% co-pay`, capped && "above the sum insured"].filter(Boolean).join(" + ") || "nothing extra"}</p></div>
      </div>
      <p className="mt-3 text-[12px] leading-relaxed text-faint">A rough guide that assumes every charge is covered and within its caps. Real bills usually include some excluded items (gloves, toiletries…) and room-rent limits, so use the What-if calculator for a line-by-line estimate.</p>
    </Section>
  );
}

/* ------------------------------------------------------------------ Claim journey */
export function ClaimJourney({ policy }: { policy: DocumentRecord }) {
  const { ck, facts: f } = usePolicyFacts(policy);
  const id = policy.document_id;
  const room = f?.limits.find((l) => /room/i.test(l.label));
  const deadline = ck?.notice[0];
  const steps: { icon: LucideIcon; when: string; items: ReactNode[] }[] = [
    { icon: CalendarClock, when: "Before a planned admission", items: [
      "Tell your insurer (or TPA) before you're admitted; the number is on your policy card. Ask whether the hospital is in their network for cashless treatment.",
      room ? <>Choose a room within your cap of <strong>{rupees(room.amount)} {room.basis}</strong> <Ref docId={id} section={room.clause} />; a costlier room means you pay the difference.</> : "Check whether your policy limits room rent before choosing a room.",
      ck?.waits.some((w) => !w.done) ? "Check the waiting periods below: if your treatment is still within one, it won't be paid yet." : "Your waiting periods have all ended, based on the policy's start date.",
    ] },
    { icon: Hospital, when: "During the stay", items: [
      "Ask for an itemised bill (every charge listed separately), not just a total.",
      "Keep every prescription and test report, and any implant or stent invoice.",
      ck?.window ? <>Bills from <strong>{ck.window.before} days before</strong> admission are covered too <Ref docId={id} section={ck.window.clause} />, so gather them now.</> : "Keep pharmacy and test bills from the days before admission.",
    ] },
    { icon: FileCheck2, when: "At discharge", items: [
      "Collect the discharge summary, the final itemised bill and payment receipts before you leave.",
      "Read the bill line by line. Upload it to Nivaaran's claim workspace to see which charges your policy covers.",
    ] },
    { icon: ClipboardList, when: "After you go home", items: [
      deadline ? <><strong>{deadline.text}</strong> <Ref docId={id} section={deadline.clause} /></> : "Submit the claim as soon as possible; most policies set a deadline.",
      ck?.window ? <>Follow-up costs for the same illness up to <strong>{ck.window.after} days after discharge</strong> are covered: keep those bills.</> : "Keep follow-up bills for the same illness.",
      "If an amount is cut, ask the insurer for the clause they relied on, in writing.",
    ] },
  ];
  return (
    <Section title="Your claim, step by step" description="What to do before, during and after a hospital stay. Policy-specific points carry their clause number.">
      <ol className="relative space-y-6">
        <span className="absolute bottom-4 left-[17px] top-4 w-px bg-line-2" aria-hidden />
        {steps.map((s, i) => (
          <li key={s.when} className="relative grid grid-cols-[36px_1fr] gap-4">
            <span className="relative z-[1] grid size-9 place-items-center rounded-full border border-brass bg-card text-accent"><s.icon className="size-4" /></span>
            <div>
              <p className="pt-1.5 text-[15px] font-semibold text-ink"><span className="mr-2 font-mono text-[11px] text-brass">0{i + 1}</span>{s.when}</p>
              <ul className="mt-2 space-y-1.5">{s.items.map((x, j) => <li key={j} className="flex items-start gap-2 text-[13.5px] leading-relaxed text-text"><span className="mt-2 size-1.5 shrink-0 rounded-full bg-brass" />{<span>{x}</span>}</li>)}</ul>
            </div>
          </li>))}
      </ol>
      <div className="mt-5"><GeneralNote>Steps without a clause number are common practice in Indian health insurance, not something your policy states. Your insurer's own process may differ slightly.</GeneralNote></div>
    </Section>
  );
}

/* ------------------------------------------------------------------ Why claims get cut */
export function CutReasons({ policy }: { policy: DocumentRecord }) {
  const { sum, facts: f } = usePolicyFacts(policy);
  const id = policy.document_id;
  const excl = f && f.counts.excluded > 0 ? sum?.sections[sum.sections.length - 1] : undefined;
  const reasons: { icon: LucideIcon; title: string; body: ReactNode }[] = [
    { icon: Ban, title: "Items the policy excludes", body: excl ? <>Your policy doesn't pay for: {excl.items.slice(0, 4).map((x, i) => <span key={x.clause}>{i > 0 && "; "}{x.text} <Ref docId={id} section={x.clause} /></span>)}{excl.items.length > 4 && ` and ${excl.items.length - 4} more`}.</> : "Check the list of exclusions in your policy summary." },
    { icon: BedDouble, title: "Room above the cap", body: "Staying in a room costlier than your cap means the extra is yours, and some policies also reduce other charges in proportion. Check your room-rent clause." },
    { icon: Hourglass, title: "A waiting period hasn't ended", body: "Treatment for a condition still inside its waiting period isn't paid, even if everything else is in order." },
    { icon: FileCheck2, title: "Missing papers", body: "A missing prescription, test report or implant invoice is the most common reason a covered item is held back. Keep every paper." },
    { icon: AlertTriangle, title: "Late submission", body: "Claims sent after the policy's deadline can be refused. Note the date the day you're discharged." },
    { icon: BadgeIndianRupee, title: "Deductible and co-payment", body: f?.deductible || f?.copay ? <>These aren't cuts but they reduce what's paid: {[f?.deductible && `the first ${rupees(f.deductible.amount)}`, f?.copay && `${f.copay.percent}% of each claim`].filter(Boolean).join(" and ")}.</> : "Your policy doesn't appear to have either." },
  ];
  return (
    <Section title="Why claims usually get reduced" description="Know these before you're admitted, and most surprises can be avoided.">
      <div className="grid gap-3 sm:grid-cols-2">
        {reasons.map((r) => (
          <div key={r.title} className="flex gap-3 rounded-[6px] border border-line p-3.5">
            <span className="grid size-8 shrink-0 place-items-center rounded-full bg-excluded-bg text-excluded"><r.icon className="size-4" /></span>
            <div><p className="text-[14px] font-semibold text-ink">{r.title}</p><p className="mt-1 text-[13px] leading-relaxed text-muted">{r.body}</p></div>
          </div>))}
      </div>
    </Section>
  );
}

/* ------------------------------------------------------------------ How the estimate is worked out */
export function HowEstimateWorks() {
  const steps = [
    ["Remove what isn't covered", "Excluded items (gloves, toiletries, TV…) are taken out."],
    ["Apply the caps", "Room rent, ICU, ambulance and other limits are applied per day or per stay."],
    ["Take off the deductible", "The amount you pay first each year comes off the total."],
    ["Apply the co-payment", "Your share of what's left is taken off."],
    ["Check the sum insured", "The insurer never pays more than your sum insured."],
  ];
  return (
    <Section title="How the estimate is worked out" description="The same order the insurer follows, with the clause for each step.">
      <ol className="space-y-2.5">
        {steps.map(([t, b], i) => (
          <li key={t} className="flex gap-3">
            <span className="grid size-7 shrink-0 place-items-center rounded-full bg-forest font-mono text-[11px] text-brass">{i + 1}</span>
            <div><p className="text-[14px] font-semibold text-ink">{t}</p><p className="text-[13px] text-muted">{b}</p></div>
          </li>))}
      </ol>
      <div className="mt-4 flex items-start gap-2 rounded-[6px] bg-review-bg px-3 py-2.5 text-[12.5px] text-text"><Lightbulb className="mt-0.5 size-4 shrink-0 text-review" />
        Tip: enter charges the way a hospital itemises them ("Room rent", "Gloves and masks", "Surgeon fee") so each one is matched to the right clause.</div>
    </Section>
  );
}

/* ------------------------------------------------------------------ Topics for the assistant */
export function AskTopics({ onAsk }: { onAsk: (q: string) => void }) {
  const topics: [string, LucideIcon, string[]][] = [
    ["Costs and limits", BadgeIndianRupee, ["Is room rent capped?", "Is there a limit on ICU charges?", "What do I pay myself on a claim?"]],
    ["What's covered", ShieldCheck, ["Is ambulance covered?", "Are medicines covered after discharge?", "Is day-care treatment covered?"]],
    ["What's not covered", Ban, ["What isn't covered?", "Are gloves and masks covered?", "Is cosmetic surgery covered?"]],
    ["Waiting periods and claims", Hourglass, ["How long are the waiting periods?", "Which documents do I need to claim?", "When must I submit my claim?"]],
  ];
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {topics.map(([t, Icon, qs]) => (
        <div key={t} className="rounded-[6px] border border-line bg-card p-4">
          <p className="flex items-center gap-2 text-[14px] font-semibold text-ink"><Icon className="size-4 text-accent" />{t}</p>
          <div className="mt-2.5 space-y-1.5">{qs.map((q) => <button key={q} type="button" onClick={() => onAsk(q)} className="block w-full rounded-[4px] px-2 py-1.5 text-left text-[13px] text-text hover:bg-paper hover:text-accent">{q}</button>)}</div>
        </div>))}
    </div>
  );
}

