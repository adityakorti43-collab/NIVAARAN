import { AlertTriangle, ArrowRight, Bot, Calculator, ListChecks, CalendarClock, FileCheck2, FilePlus2, FileText, FileWarning, GitBranch, ReceiptText, ScrollText, ShieldAlert, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ease, MoneyTicker, Stagger, StaggerItem } from "../components/motion";
import { Disclaimer, EmptyState, ErrorNote, PageHeader, PageSkeleton, Range, Section, StatusBadge, SyntheticBanner, Tag } from "../components/ui";
import { api } from "../lib/api";
import { cn, fmtDate, inr } from "../lib/format";
import { useApp } from "../lib/store";
import type { Analysis, DocumentRecord, PolicySummary } from "../lib/types";
import { BillSplit, KeyTerms, usePolicyFacts } from "../components/PolicyGuide";

function EstimateHero({ a, title }: { a: Analysis; title: string }) {
  const s = a.summary;
  const billed = Number(s.total_billed) || 1;
  const parts = [
    { k: "Estimated payable (definite)", v: s.payable_low, c: "#93c6a8" },
    { k: "Unresolved, payable only if resolved favourably", v: s.unresolved_exposure, c: "#dcb66e" },
    { k: "Potential patient share (minimum)", v: s.patient_low, c: "rgba(245,242,234,0.16)" },
  ];
  return (
    <div className="theme-forest relative overflow-hidden rounded-[6px] bg-forest p-6 md:p-10" style={{ boxShadow: "0 30px 60px -36px rgba(20,45,39,.55)" }}>
      <div className="pointer-events-none absolute inset-0 [background-image:linear-gradient(rgb(245_242_234/0.04)_1px,transparent_1px),linear-gradient(90deg,rgb(245_242_234/0.04)_1px,transparent_1px)] [background-size:40px_40px] [mask-image:linear-gradient(to_bottom,black,transparent)]" aria-hidden />
      <div className="pointer-events-none absolute -right-20 -top-24 size-80 rounded-full bg-brass/[0.12] blur-3xl" aria-hidden />
      <div className="relative flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div className="min-w-0">
          <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-sage">Estimated payable · {title}</p>
          <p className="mt-3 font-display text-[58px] leading-[0.92] tracking-[-0.015em] text-ink md:text-[92px]" data-testid="stat-payable"><MoneyTicker value={s.payable_low} /></p>
          <p className="mt-3 max-w-xl text-[15px] text-muted">Up to <span className="num font-semibold text-ink">{inr(s.payable_high)}</span> if every unresolved item were resolved favourably, of <span className="num font-semibold text-ink">{inr(s.total_billed)}</span> billed. An estimate, not an insurer decision.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className="inline-flex items-center gap-2 rounded-[3px] border border-line-2 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.1em] text-text"><GitBranch className="size-3.5 text-accent" />{a.version.selected?.label ?? "No version"}</span>
          <Link to="/claim" className="btn-primary">Open the ledger <ArrowRight className="size-4" /></Link>
        </div>
      </div>
      <div className="relative mt-8">
        <div className="flex h-2 gap-1 overflow-hidden rounded-full" role="img" aria-label="Composition of the billed amount">
          {parts.map((p, i) => (
            <motion.div key={p.k} style={{ background: p.c, flexGrow: Number(p.v) / billed, flexBasis: 0, originX: 0 }} initial={{ scaleX: 0 }} animate={{ scaleX: 1 }}
              transition={{ duration: 1.1, ease, delay: 0.2 + i * 0.14 }} className="h-full rounded-full" />))}
        </div>
        <ul className="mt-3.5 flex flex-wrap gap-x-6 gap-y-1.5 text-[13px]">
          {parts.map((p) => <li key={p.k} className="flex items-center gap-2 text-muted"><span className="size-2.5 rounded-full" style={{ background: p.c }} />{p.k} <span className="num font-semibold text-ink">{inr(p.v)}</span></li>)}
        </ul>
      </div>
    </div>
  );
}

/** A plain-language snapshot: how much is covered, capped, excluded, and how the waiting periods stand today. */
function PolicyGlance({ policy }: { policy: DocumentRecord }) {
  const { facts: f, ck } = usePolicyFacts(policy);
  if (!f) return <Section title="Your policy in a minute"><PageSkeleton /></Section>;
  const waitsOpen = ck?.waits.filter((w) => !w.done) ?? [];
  const rows: [string, string, string][] = [
    ["Things it pays for", `${f.counts.covered}`, "Hospital stays, doctors, tests, medicines and more. See the full list in Documents."],
    ["Caps on what it pays", `${f.counts.limits}`, f.limits.slice(0, 2).map((l) => `${l.label.replace(/\bicu\b/i, "ICU")} up to ₹${Number(l.amount).toLocaleString("en-IN")} ${l.basis}`).join("; ") || "No caps found."],
    ["Things it never pays for", `${f.counts.excluded}`, "Typically consumables, toiletries and personal comforts. Budget for these yourself."],
    ["Waiting periods still running", `${waitsOpen.length}`, waitsOpen.length ? waitsOpen.map((w) => `${w.label} until ${w.covered_from ? fmtDate(w.covered_from) : "date not known"}`).join("; ") : "All waiting periods have ended."],
  ];
  return (
    <Section title="Your policy in a minute" description="The headline facts, read from its clauses.">
      <ul className="divide-y divide-line">
        {rows.map(([k, n, d]) => (
          <li key={k} className="flex gap-4 py-3">
            <span className="w-10 shrink-0 font-display text-[28px] leading-none text-ink num">{n}</span>
            <div className="min-w-0"><p className="text-[14px] font-semibold text-ink">{k}</p><p className="mt-0.5 text-[12.5px] leading-relaxed text-muted first-letter:uppercase">{d}</p></div>
          </li>))}
      </ul>
    </Section>
  );
}

/** The dashboard before any claim: your policy's key numbers, and what you can already do with it. */
function PolicyHome({ policy }: { policy: DocumentRecord }) {
  const [sum, setSum] = useState<PolicySummary | null>(null);
  useEffect(() => { api.policySummary(policy.document_id, "en").then(setSum).catch(() => setSum(null)); }, [policy.document_id]);
  const f = sum?.facts;
  const room = f?.limits.find((l) => /room/i.test(l.label));
  const rupees = (v: string) => "₹" + Number(v).toLocaleString("en-IN", { maximumFractionDigits: 0 });
  const si = policy.metadata.sum_insured && !String(policy.metadata.sum_insured).includes("Not found") ? rupees(String(policy.metadata.sum_insured)) : null;
  const tiles = [si && ["Sum insured", si], f?.deductible && ["You pay first", rupees(f.deductible.amount)], f?.copay && ["Co-payment", `${f.copay.percent}%`],
    room && ["Room rent cap", `${rupees(room.amount)}/day`]].filter(Boolean) as [string, string][];
  const tools = [
    { to: "/what-if", icon: Calculator, title: "Estimate a hospital stay", body: "Enter expected charges and see what your policy would pay." },
    { to: "/assistant", icon: Bot, title: "Ask about your policy", body: "Room rent, waiting periods, exclusions: in English or Hindi." },
    { to: "/actions", icon: ListChecks, title: "Get claim-ready", body: "Documents to keep and when each waiting period ends." },
    { to: "/reports", icon: ScrollText, title: "Download a summary", body: "A printable PDF of your policy in plain words." },
  ];
  return (
    <div className="space-y-5">
      <div className="theme-forest relative overflow-hidden rounded-[6px] bg-forest p-6 md:p-8" style={{ boxShadow: "0 30px 60px -36px rgba(20,45,39,.55)" }}>
        <div className="pointer-events-none absolute -right-20 -top-24 size-80 rounded-full bg-brass/[0.12] blur-3xl" aria-hidden />
        <div className="relative flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-brass">Your policy</p>
            <p className="mt-2 font-display text-[40px] leading-tight text-ivory md:text-[52px]">{(policy.metadata.title ?? policy.filename).split(/\s+[-–—]\s+/)[0]}</p>
            <p className="mt-1 text-[13.5px] text-ivory/65">{[policy.metadata.insurer, policy.clause_count && `${policy.clause_count} clauses read`].filter((x) => x && !String(x).includes("Not found")).join(" · ")}</p>
          </div>
          <Link to="/documents" className="btn-brass">Read the summary <ArrowRight className="size-4" /></Link>
        </div>
        {tiles.length > 0 && (
          <div className={cn("relative mt-6 grid grid-cols-2 gap-px overflow-hidden rounded-[4px] bg-ivory/10", tiles.length >= 4 ? "lg:grid-cols-4" : tiles.length === 3 ? "lg:grid-cols-3" : "lg:grid-cols-2")}>
            {tiles.map(([k, v]) => <div key={k} className="bg-forest/95 px-4 py-3.5"><p className="text-[11.5px] text-ivory/60">{k}</p><p className="mt-1 font-display text-[30px] leading-none text-ivory num">{v}</p></div>)}
          </div>)}
      </div>
      <Stagger className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {tools.map((t) => (
          <StaggerItem key={t.to}>
            <Link to={t.to} className="card group flex h-full flex-col p-5 transition-colors hover:border-brass">
              <span className="grid size-10 place-items-center rounded-full bg-covered-bg text-accent"><t.icon className="size-5" /></span>
              <p className="mt-4 text-[15px] font-semibold text-ink">{t.title}</p>
              <p className="mt-1 flex-1 text-[13px] leading-relaxed text-muted">{t.body}</p>
              <span className="mt-4 inline-flex items-center gap-1 text-[13px] font-medium text-accent">Open <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" /></span>
            </Link>
          </StaggerItem>))}
      </Stagger>
      <div className="grid gap-5 xl:grid-cols-[1fr_1.4fr]"><BillSplit policy={policy} /><PolicyGlance policy={policy} /></div>
      <KeyTerms policy={policy} />
      <div className="card flex flex-wrap items-center gap-4 p-5">
        <span className="grid size-10 place-items-center rounded-full bg-forest text-brass"><ReceiptText className="size-5" /></span>
        <div className="min-w-0 flex-1"><p className="text-[15px] font-semibold text-ink">Have a hospital bill?</p>
          <p className="text-[13px] text-muted">Upload it and every charge is matched to the clause that decides it, with what you're likely to get back.</p></div>
        <Link to="/claim" className="btn-primary">Analyse a bill <ArrowRight className="size-4" /></Link>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { user, bundle, setActiveClaimId, claims, documents } = useApp();
  const policy = documents.find((d) => d.doc_type === "policy");
  const nav = useNavigate();
  const [ov, setOv] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api.overview().then(setOv).catch((e) => setErr(e.message)); }, [claims.length, bundle?.analysis?.analysis_id]);
  if (!ov && !err) return <PageSkeleton />;
  const a = bundle?.analysis;
  const open = (cid: string, to = "/claim") => { setActiveClaimId(cid); nav(to); };
  const hour = new Date().getHours();
  return (
    <div>
      <PageHeader eyebrow={hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening"} title={user?.name?.trim() ? `Welcome back, ${user.name.trim().split(" ")[0]}` : "Welcome back"}
        description={"Your policies, claims and open questions, in one place."}
        actions={<><Link to="/documents" className="btn-secondary"><FilePlus2 className="size-4" /> Upload documents</Link><Link to="/claim" className="btn-primary">Analyze a claim <ArrowRight className="size-4" /></Link></>} />
      <ErrorNote error={err} className="mb-5" />
      {ov && ov.claims.length === 0 && policy ? <PolicyHome policy={policy} /> : ov && ov.claims.length === 0 ? (
        <EmptyState icon={Sparkles} title="Your workspace is empty"
          actions={<><Link to="/documents" className="btn-primary">Upload a policy</Link><Link to="/claim" className="btn-secondary">Create a claim</Link></>}>
          Start by uploading your policy wording, any endorsements and an itemised hospital bill.
        </EmptyState>
      ) : ov && (
        <>
          {a && <SyntheticBanner show={a.synthetic} />}
          {a && bundle && <EstimateHero a={a} title={bundle.claim.title} />}
          <Stagger className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[["Claims", ov.claims.length, ReceiptText, "bg-partial-bg text-partial"], ["Pending reviews", ov.pending_reviews.length, ShieldAlert, "bg-review-bg text-review"],
              ["Potential discrepancies", ov.discrepancy_count, AlertTriangle, "bg-conditional-bg text-conditional"], ["Saved reports", ov.reports.length, ScrollText, "bg-covered-bg text-covered"]].map(([k, v, I, t]) => {
              const Icon = I as typeof ReceiptText;
              return (
                <StaggerItem key={k as string}>
                  <div className="card flex items-center gap-4 p-4">
                    <span className={`grid size-11 place-items-center rounded-xl ${t}`}><Icon className="size-5" aria-hidden /></span>
                    <div><p className="text-[13px] text-muted">{k as string}</p><p className="text-[26px] font-semibold leading-tight text-ink num">{v as number}</p></div>
                  </div>
                </StaggerItem>);
            })}
          </Stagger>

          <div className="mt-5 grid gap-5 xl:grid-cols-[1.5fr_1fr]">
            <Section title="Claims" description="Open a claim to continue reviewing it.">
              <ul className="divide-y divide-line" data-testid="claims-list">
                {ov.claims.map((c: any) => (
                  <li key={c.claim_id} className="flex flex-wrap items-center gap-3 py-3">
                    <ReceiptText className="size-4 text-accent" aria-hidden />
                    <div className="min-w-[220px] flex-1">
                      <p className="text-sm font-semibold text-ink">{c.title}</p>
                      <p className="text-xs text-muted">Treatment {fmtDate(c.admission_date)} · {c.version ?? "version not determined"} · billed {inr(c.total_billed)}</p>
                    </div>
                    {c.payable && <span className="text-sm num text-ink"><Range low={c.payable[0]} high={c.payable[1]} /></span>}
                    {c.review_items > 0 && <Tag tone="review">{c.review_items} to review</Tag>}
                    {c.discrepancies > 0 && <Tag tone="conditional">{c.discrepancies} discrepancies</Tag>}
                    
                    <button className="btn-secondary h-8 px-3 text-xs" onClick={() => open(c.claim_id)}>Open</button>
                  </li>))}
              </ul>
            </Section>
            <Section title="Recent activity" description="Recorded changes to your analyses.">
              <ol className="relative space-y-4 before:absolute before:bottom-2 before:left-[7px] before:top-2 before:w-px before:bg-line-2">
                {ov.activity.slice(0, 7).map((x: any, i: number) => (
                  <li key={i} className="relative pl-6">
                    <span className={`absolute left-0 top-1 size-[15px] rounded-full border-2 border-card ${i === 0 ? "bg-accent" : "bg-line-2"}`} aria-hidden />
                    <p className="text-sm text-ink">{x.what}</p>
                    <p className="text-xs text-muted"><CalendarClock className="mr-1 inline size-3" aria-hidden />{x.claim} · {new Date(x.at).toLocaleString("en-IN")}</p>
                  </li>))}
              </ol>
            </Section>
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-3">
            <Section title="Pending reviews" description="Items Nivaaran won't decide without more evidence.">
              <ul className="space-y-2">
                {ov.pending_reviews.slice(0, 6).map((r: any, i: number) => (
                  <li key={i}><button onClick={() => open(r.claim_id)} className="flex w-full items-center gap-2 rounded-xl border border-line p-2.5 text-left text-sm hover:border-line-2">
                    <span className="min-w-0 flex-1 truncate text-ink">{r.item}</span><StatusBadge status={r.status} short /></button></li>))}
                {ov.pending_reviews.length === 0 && <p className="text-sm text-muted">Nothing awaiting review.</p>}
              </ul>
            </Section>
            <Section title="Missing documents" description="Information the analysis could not establish.">
              <ul className="space-y-2">
                {ov.missing_documents.slice(0, 6).map((m: any, i: number) => (
                  <li key={i} className="flex items-start gap-2 text-sm"><FileWarning className="mt-0.5 size-4 shrink-0 text-conditional" aria-hidden /><span className="text-text">{m.need}</span></li>))}
                {ov.missing_documents.length === 0 && <p className="text-sm text-muted">Nothing missing.</p>}
              </ul>
              {ov.missing_documents.length > 0 && <Link to="/actions" className="btn-ghost mt-3 px-0 text-xs">Open the Action Center <ArrowRight className="size-3.5" /></Link>}
            </Section>
            <Section title="Saved reports" description="Generated from your saved analyses.">
              <ul className="space-y-2">
                {ov.reports.slice(0, 6).map((r: any) => (
                  <li key={r.id} className="flex items-center gap-2 text-sm"><FileText className="size-4 text-accent" aria-hidden />
                    <span className="min-w-0 flex-1 truncate text-text">{r.kind.toUpperCase()} · {new Date(r.created).toLocaleString("en-IN")}</span>
                    <a className="text-xs font-medium text-accent hover:underline" href={api.reportUrl(r.claim_id, r.kind)} download>Download</a></li>))}
                {ov.reports.length === 0 && <p className="text-sm text-muted">No reports yet. Generate one from Reports.</p>}
              </ul>
            </Section>
          </div>

          <Section title="Policy library" className="mt-5" description="Documents in your workspace."
            actions={<Link to="/documents" className="btn-ghost text-xs">Manage <ArrowRight className="size-3.5" /></Link>}>
            <ul className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {ov.documents.map((d: any) => (
                <li key={d.document_id} className="flex min-w-0 items-center gap-3 rounded-xl border border-line p-3">
                  {d.status === "processed" ? <FileCheck2 className="size-4 text-covered" aria-label="Processed" /> : <FileWarning className="size-4 text-conditional" aria-label="Processed with warnings" />}
                  <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium text-ink">{d.title}</p>
                    <p className="text-xs text-muted">{d.doc_type === "policy" ? "Policy wording" : d.doc_type === "endorsement" ? "Endorsement" : "Benefit summary"} · {d.clause_count} clauses</p></div>
                  
                </li>))}
            </ul>
          </Section>
          <Disclaimer className="mt-6" />
        </>
      )}
    </div>
  );
}
