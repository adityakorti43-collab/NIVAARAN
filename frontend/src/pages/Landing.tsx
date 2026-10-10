import { ArrowRight, ArrowUpRight, Bot } from "lucide-react";
import { motion, useReducedMotion, useScroll, useSpring, useTransform } from "motion/react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CinematicIntro, replayIntro } from "../components/CinematicIntro";
import { webglAvailable } from "../components/HeroFallback";
import { AskBox } from "../components/LandingAsk";
import { ease, Reveal } from "../components/motion";
import { LogoMark } from "../components/Shell";
import { api } from "../lib/api";
import { cn } from "../lib/format";
import { useApp } from "../lib/store";

// The hero's signature scene: a 3D hospital receipt printed with the demo bill and each line's verdict.
const Hero3D = lazy(() => import("../components/Hero3D"));

function useStart() {
  const nav = useNavigate();
  const { user, setUser, refresh, setActiveClaimId } = useApp();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  /** Signed in: open the workspace. Otherwise: open an isolated synthetic demo workspace. */
  const start = async (to = "/claim") => {
    if (user) { nav(to); return; }
    setBusy(true); setErr(null);
    try { const r = await api.enterDemo(); setUser(r.user); setActiveClaimId(r.claim_id); await refresh(); nav(to); }
    catch (e) { setErr((e as Error).message); setBusy(false); }
  };
  return { start, busy, err };
}

/** Mono chapter marker: number in brass, a short rule, the chapter name. */
function Chapter({ n, children, className }: { n: string; children: ReactNode; className?: string }) {
  return (
    <p className={cn("flex items-center gap-3 font-mono text-[11px] uppercase tracking-[0.18em] text-muted", className)}>
      <span className="text-brass">{n}</span><span className="h-px w-10 bg-brass/60" aria-hidden /><span>{children}</span>
    </p>
  );
}

const H2 = "font-display text-[44px] leading-[0.98] tracking-[-0.015em] text-ink md:text-[68px]";

const CHAPTERS: [string, string, string][] = [["01", "Policies", "#policies"], ["02", "Bills", "#bills"], ["03", "Exclusions", "#exclusions"], ["04", "Calculation", "#calculation"], ["05", "Questions", "#ask"]];

function Nav({ onStart, busy }: { onStart: () => void; busy: boolean }) {
  const { user } = useApp();
  const [solid, setSolid] = useState(false);
  useEffect(() => { const f = () => setSolid(window.scrollY > 40); f(); window.addEventListener("scroll", f, { passive: true }); return () => window.removeEventListener("scroll", f); }, []);
  return (
    <header className={cn("theme-forest fixed inset-x-0 top-0 z-50 transition-all duration-300", solid ? "border-b border-white/10 bg-forest/92 backdrop-blur-xl" : "")}>
      <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-8 px-5 md:px-10">
        <Link to="/" className="flex shrink-0 items-center gap-2.5" aria-label="Nivaaran home"><LogoMark className="size-7" /><span className="font-display text-[26px] leading-none text-ivory">Nivaaran</span></Link>
        <nav aria-label="Landing" className="hidden items-center gap-6 text-[14.5px] font-semibold text-ivory/80 md:flex xl:gap-8">
          {CHAPTERS.map(([, l, h]) => <a key={h} href={h} className="transition-colors hover:text-brass">{l}</a>)}
          <a href="#security" className="transition-colors hover:text-brass">Security</a>
        </nav>
        <div className="flex-1" />
        {user ? <Link to="/dashboard" className="hidden text-[14.5px] font-semibold text-ivory hover:text-brass sm:inline">Dashboard</Link>
          : <Link to="/login" className="hidden text-[14.5px] font-semibold text-ivory hover:text-brass sm:inline" data-testid="nav-signin">Sign in</Link>}
        <button className="btn-primary font-semibold" onClick={onStart} disabled={busy} data-testid="landing-demo">{busy ? "Opening" : user ? "Open workspace" : "Try the demo"}</button>
      </div>
    </header>
  );
}

function Hero({ onStart, onAsk, busy, err }: { onStart: () => void; onAsk: (q: string) => void; busy: boolean; err: string | null }) {
  const reduce = useReducedMotion();
  const gl = useMemo(() => webglAvailable(), []);
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] });
  const smooth = useSpring(scrollYProgress, { stiffness: 80, damping: 20 });
  return (
    <section ref={ref} className="theme-forest relative min-h-[100svh] overflow-hidden bg-forest text-ivory">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_72%_42%,#21443a_0%,#142d27_42%,#0b1a16_100%)]" aria-hidden />
      <div className="grid-fade absolute inset-0 opacity-60" aria-hidden />
      <div className="absolute inset-y-0 right-0 w-full opacity-[0.16] lg:w-[54%] lg:opacity-100">{gl ? <Suspense fallback={null}><Hero3D still={!!reduce} scroll={smooth} /></Suspense> : null}</div>
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,rgba(11,26,22,0.94)_0%,rgba(11,26,22,0.55)_44%,transparent_64%)]" aria-hidden />
      <div className="aurora pointer-events-none absolute inset-x-0 bottom-0 h-[55%]" aria-hidden />

      <div className="relative mx-auto flex min-h-[100svh] max-w-[1440px] flex-col justify-center px-5 pb-28 pt-28 md:px-10">
        <motion.p className="font-mono text-[11px] uppercase tracking-[0.2em] text-sage" initial={reduce ? false : { opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1, duration: 0.8 }}>
          Health insurance, read closely
        </motion.p>
        <h1 className="mt-6 max-w-[16ch] font-display text-[15vw] leading-[0.94] tracking-[-0.02em] sm:text-[10vw] lg:text-[6.1vw]">
          {["Insurance clarity.", "Backed by evidence."].map((w, i) => (
            <span key={w} className="block overflow-hidden pb-[0.08em]">
              <motion.span className={cn("block", i === 1 && "italic text-brass")} initial={reduce ? false : { y: "105%" }} animate={{ y: 0 }} transition={{ duration: 1.05, ease, delay: 0.2 + i * 0.16 }}>{w}{" "}</motion.span>
            </span>))}
        </h1>
        <p className="mt-7 max-w-[34rem] text-[17px] leading-relaxed text-ivory/75 md:text-[18px]">
          The hospital bill says one number. The insurer pays another. Nivaaran reads your policy and your bill side by side and shows you, line by line, what should be covered, what won't be, and why.
        </p>
        <AskBox onAsk={onAsk} busy={busy} />
        <div className="mt-5 flex flex-wrap items-center gap-x-7 gap-y-2 text-[14px]">
          <button className="inline-flex items-center gap-1.5 text-ivory underline decoration-brass/60 underline-offset-[6px] hover:decoration-brass" onClick={onStart} disabled={busy}>{busy ? "Opening the demo" : <>See a full claim breakdown <ArrowRight className="size-4" /></>}</button>
          <a href="#premise" className="text-ivory/60 hover:text-ivory">How it works</a>
        </div>
        {err && <p role="alert" className="mt-3 max-w-md rounded-[3px] bg-conflict-bg px-3 py-2 text-sm text-conflict">{err}</p>}
        <p className="mt-8 max-w-md font-mono text-[11px] leading-relaxed tracking-[0.04em] text-ivory/45">No sign-up needed. The demo runs on a made-up policy and bill in a private workspace that deletes itself after 24 hours.</p>
      </div>

      {/* architectural index strip */}
      <div className="absolute inset-x-0 bottom-0 hidden border-t border-white/10 md:block">
        <ol className="mx-auto grid max-w-[1440px] grid-cols-5 px-10 font-mono text-[10.5px] uppercase tracking-[0.16em] text-ivory/50">
          {["Policy wording", "Endorsements", "Hospital bill", "Exclusions & limits", "Calculation"].map((t, i) => (
            <li key={t} className={cn("flex items-center gap-3 py-4", i > 0 && "border-l border-white/10 pl-5")}><span className="text-brass">0{i + 1}</span>{t}</li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function Premise() {
  return (
    <section id="premise" className="paper-grain relative bg-paper px-5 py-28 md:px-10 md:py-36">
      <div className="mx-auto grid max-w-[1440px] gap-10 lg:grid-cols-12">
        <Chapter n="00" className="lg:col-span-3 lg:pt-4">Premise</Chapter>
        <div className="lg:col-span-9">
          <Reveal><p className="font-display text-[34px] leading-[1.1] tracking-[-0.01em] text-ink md:text-[54px]">
            You paid the premium every year. Then the discharge desk hands you a bill, the insurer cuts it, and <span className="italic text-accent">nobody can tell you which line of the policy says so.</span>
          </p></Reveal>
          <div className="mt-14 grid gap-10 border-t border-line pt-10 md:grid-cols-[1fr_1.3fr]">
            <p className="font-mono text-[11px] uppercase leading-relaxed tracking-[0.16em] text-muted">What Nivaaran does</p>
            <p className="text-[17px] leading-relaxed text-text">Nivaaran can. It reads your policy, its amendments, the brochure and the hospital bill together, finds the clause behind every deduction, and tells you what you're likely to get back, in English, Hindi or Marathi.</p>
          </div>
        </div>
      </div>
    </section>
  );
}

function Complexity() {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  const p = useSpring(scrollYProgress, { stiffness: 90, damping: 22 });
  const reduce = useReducedMotion();
  const x1 = useTransform(p, [0, 0.6], [reduce ? 0 : -140, 0]), x3 = useTransform(p, [0, 0.6], [reduce ? 0 : 140, 0]), y2 = useTransform(p, [0, 0.6], [reduce ? 0 : 90, 0]);
  const draw = useTransform(p, [0.45, 0.85], [0, 1]), a = useTransform(p, [0, 0.4, 0.5], [1, 1, 0]), b = useTransform(p, [0.5, 0.65], [0, 1]);
  const docs: [string, string, [string, string][], object][] = [
    ["Policy wording", "Effective 01 Apr 2025", [["2.2", "Room rent up to ₹5,000/day"], ["4.1", "Consumables excluded"], ["5.2", "Co-payment 10%"]], { x: x1 }],
    ["Endorsement E-01", "Effective 01 Oct 2025", [["E1.1", "Replaces 2.2: ₹7,500/day"], ["E1.3", "Consumables up to ₹5,000"], ["E1.2", "Replaces 5.2: co-pay 5%"]], { y: y2 }],
    ["Hospital bill", "Admitted 12 Nov 2025", [["01", "Deluxe room × 2: ₹18,000"], ["10", "Gloves, masks: ₹3,500"], ["Σ", "Total ₹1,25,900"]], { x: x3 }],
  ];
  return (
    <section id="policies" ref={ref} className="relative h-[220vh] border-t border-line bg-paper">
      <div className="sticky top-0 flex h-[100svh] flex-col justify-center overflow-hidden px-5 md:px-10">
        <div className="mx-auto w-full max-w-[1440px]">
          <Chapter n="01">Policies & versions</Chapter>
          <div className="relative mt-6 h-[120px] max-w-4xl md:h-[150px]">
            <motion.h2 style={{ opacity: a }} className={cn("absolute", H2)}>Three documents. Three different answers.</motion.h2>
            <motion.h2 style={{ opacity: b }} className={cn("absolute", H2)}>Read together, they give <span className="italic text-accent">one answer.</span></motion.h2>
          </div>
          <div className="relative mt-10 flex flex-col items-center gap-5 md:flex-row md:justify-center md:gap-0">
            {docs.map(([t, d, lines, style], i) => (
              <div key={t} className="contents">
                {i > 0 && (
                  <div className="relative hidden h-px w-12 md:block lg:w-20" aria-hidden>
                    <motion.div className="absolute inset-0 origin-left bg-brass" style={{ scaleX: draw }} />
                  </div>)}
                <motion.div style={style} className="w-[272px] rounded-[2px] border border-line bg-card shadow-[0_24px_50px_-30px_rgba(20,45,39,0.35)]">
                  <div className="h-[3px] bg-brass" aria-hidden />
                  <div className="p-5">
                    <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">{d}</p>
                    <p className="mt-1.5 font-display text-[24px] leading-tight text-ink">{t}</p>
                    <ul className="mt-4 space-y-2 border-t border-line pt-4 text-[13px] text-text">
                      {lines.map(([n, l]) => <li key={l} className="grid grid-cols-[38px_1fr] gap-2"><span className="font-mono text-[11px] text-brass">{n}</span><span>{l}</span></li>)}
                    </ul>
                  </div>
                </motion.div>
              </div>))}
          </div>
          <p className="mt-9 text-center font-mono text-[11px] tracking-[0.04em] text-faint">Synthetic example. The treatment date falls after the endorsement's effective date, so E-01 applies.</p>
        </div>
      </div>
    </section>
  );
}

const CHAIN = [["Every clause is pulled out", "With its page number and the exact wording, so nothing is paraphrased."], ["The right version is picked", "By effective date. An endorsement only counts from the day it starts."], ["The bill is itemised", "Each line is named, grouped and its arithmetic checked."],
  ["Limits are applied in order", "Room caps, co-pay and deductibles, in the sequence your policy sets out."], ["Each line gets its clause", "A clause only counts if its terms actually match that charge."], ["Mismatches are flagged", "If two documents disagree, you see both and decide what to ask."]];

function Activation() {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 70%", "end 60%"] });
  const [lit, setLit] = useState(0);
  useEffect(() => scrollYProgress.on("change", (v) => setLit(Math.ceil(v * CHAIN.length))), [scrollYProgress]);
  return (
    <section id="bills" ref={ref} className="border-t border-line bg-card px-5 py-28 md:px-10 md:py-36">
      <div className="mx-auto grid max-w-[1440px] gap-14 lg:grid-cols-12">
        <div className="lg:sticky lg:top-28 lg:col-span-5 lg:self-start">
          <Chapter n="02">Reading the bill</Chapter>
          <h2 className={cn("mt-6", H2)}>What happens after you upload.</h2>
          <p className="mt-6 max-w-sm text-[16px] leading-relaxed text-muted">Six steps, always in the same order, and every one of them can be inspected afterwards.</p>
        </div>
        <ol className="relative border-l border-line-2 lg:col-span-6 lg:col-start-7">
          {CHAIN.map(([t, d], i) => (
            <li key={t} className={cn("relative pb-12 pl-10 transition-opacity duration-500 last:pb-0", i < lit ? "opacity-100" : "opacity-35")}>
              <span className={cn("absolute -left-[5px] top-[10px] size-[9px] rotate-45 border transition-colors duration-500", i < lit ? (i === 5 ? "border-amber bg-amber" : "border-brass bg-brass") : "border-line-2 bg-card")} aria-hidden />
              <p className="font-mono text-[11px] tracking-[0.12em] text-brass">0{i + 1}</p>
              <p className="mt-1 font-display text-[28px] leading-tight text-ink md:text-[32px]">{t}</p>
              <p className="mt-1.5 max-w-md text-[15px] text-muted">{d}</p>
            </li>))}
        </ol>
      </div>
    </section>
  );
}

function Fairness() {
  return (
    <section id="exclusions" className="theme-forest relative overflow-hidden bg-forest px-5 py-28 md:px-10 md:py-36">
      <div className="mx-auto max-w-[1440px]">
        <Chapter n="03">Exclusions & disagreements</Chapter>
        <Reveal><h2 className={cn("mt-6 max-w-5xl", H2)}>Not every refusal is unfair. Some deserve a second look.</h2></Reveal>
        <div className="mt-16 grid items-center gap-8 border-y border-white/10 py-12 md:grid-cols-[1fr_auto_1fr] md:gap-12">
          <figure>
            <figcaption className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-sage">Benefits brochure · S1.1</figcaption>
            <blockquote className="mt-4 font-display text-[28px] italic leading-snug text-ivory md:text-[34px]">“Room rent … payable up to INR 10,000 per day.”</blockquote>
          </figure>
          <span className="font-display text-[64px] leading-none text-brass md:text-[96px]" aria-label="does not match">≠</span>
          <figure>
            <figcaption className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-sage">Endorsement E-01 · E1.1</figcaption>
            <blockquote className="mt-4 font-display text-[28px] italic leading-snug text-ivory md:text-[34px]">“Room rent … payable up to INR 7,500 per day.”</blockquote>
          </figure>
        </div>
        <div className="mt-10 grid gap-10 lg:grid-cols-12">
          <p className="max-w-xl text-[16px] leading-relaxed text-ivory/75 lg:col-span-6">The brochure your agent handed you promised ₹10,000 a day for the room. The endorsement caps it at ₹7,500. Nivaaran puts both in front of you and helps you ask the insurer which one applies. <span className="text-ivory">It doesn't shout fraud.</span></p>
          <div className="border-l border-white/15 pl-6 lg:col-span-5 lg:col-start-8">
            <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-sage">By contrast · documented restriction, not a discrepancy</p>
            <p className="mt-3 text-[15px] text-ivory/85">Policy wording, 4.3: “Television, telephone, laundry and attendant charges are not payable.”</p>
          </div>
        </div>
        <p className="mt-12 font-mono text-[11px] text-ivory/40">Excerpts from fictional, synthetic documents.</p>
      </div>
    </section>
  );
}

const STEPS = [["Original bill", "₹1,25,900.00", "16 items, as billed", ""], ["Excluded or unresolved, held out", "₹1,20,600.00", "TV and admission kit excluded; unresolved items not assumed payable", "−₹5,300.00"],
  ["Item limits", "₹1,14,600.00", "Room ₹7,500/day (E1.1), ICU (2.3), ambulance (2.8)", "−₹6,000.00"], ["Deductible", "₹1,04,600.00", "₹10,000 per policy year (5.1)", "−₹10,000.00"], ["Co-payment 5%", "₹99,370.00", "After the deductible (E1.2)", "−₹5,230.00"]];

function Calculation() {
  const reduce = useReducedMotion();
  return (
    <section id="calculation" className="paper-grain border-t border-line bg-paper px-5 py-28 md:px-10 md:py-36">
      <div className="mx-auto grid max-w-[1440px] gap-14 lg:grid-cols-12">
        <div className="lg:col-span-4">
          <Chapter n="04">Limits & the calculation</Chapter>
          <Reveal><h2 className={cn("mt-6", H2)}>Where every rupee went.</h2></Reveal>
          <p className="mt-6 max-w-xs font-mono text-[11px] uppercase leading-relaxed tracking-[0.12em] text-muted">Sample claim · an estimate, not the insurer's decision</p>
        </div>
        <div className="lg:col-span-7 lg:col-start-6">
          <div className="perforated bg-card px-6 py-9 shadow-[0_30px_60px_-36px_rgba(20,45,39,0.45)] md:px-10">
            <div className="flex items-baseline justify-between border-b border-dashed border-line-2 pb-4 font-mono text-[10.5px] uppercase tracking-[0.16em] text-muted"><span>Calculation trace</span><span>Running total</span></div>
            <ol>{STEPS.map(([l, v, w, d], i) => (
              <motion.li key={l} initial={reduce ? false : { opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1, duration: 0.6, ease }}
                className={cn("grid grid-cols-[1fr_auto] gap-x-6 gap-y-1 py-5", i < 4 && "border-b border-line")}>
                <p className={cn("text-[16px] font-medium", i === 4 ? "text-accent" : "text-ink")}>{l}</p>
                <p className={cn("text-right font-mono text-[17px] num md:text-[19px]", i === 4 ? "font-medium text-accent" : "text-ink")}>{v}</p>
                <p className="text-[13px] text-muted">{w}</p>
                <p className="text-right font-mono text-[12.5px] text-excluded num">{d}</p>
              </motion.li>))}</ol>
            <div className="mt-2 flex items-end justify-between bg-forest px-5 py-4 text-ivory">
              <span className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-sage">Estimated payable</span>
              <span className="font-display text-[34px] leading-none num">₹99,370.00</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function AssistantDemo({ onStart }: { onStart: (to?: string) => void }) {
  return (
    <section id="ask" className="border-t border-line bg-card px-5 py-28 md:px-10 md:py-36">
      <div className="mx-auto grid max-w-[1440px] items-start gap-14 lg:grid-cols-12">
        <div className="lg:col-span-5">
          <Chapter n="05">Questions</Chapter>
          <Reveal><h2 className={cn("mt-6", H2)}>Ask why. Get the clause.</h2></Reveal>
          <p className="mt-6 max-w-sm text-[16px] leading-relaxed text-muted">Ask the way you'd ask a relative who works in insurance, in English, Hindi or Marathi. If your documents don't answer it, Nivaaran says so instead of guessing.</p>
          <button className="btn-primary mt-8" onClick={() => onStart("/assistant")}><Bot className="size-4" strokeWidth={1.6} /> Ask it yourself in the demo</button>
        </div>
        <div className="lg:col-span-6 lg:col-start-7">
          <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-faint">Transcript · synthetic demo case</p>
          <div className="mt-6 border-t border-line pt-8">
            <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-muted">You asked</p>
            <p className="mt-3 font-display text-[30px] italic leading-snug text-ink md:text-[36px]">Why didn't they pay for the vitamin drip?</p>
            <p className="mt-2 text-[14px] text-muted" lang="hi">या पूछें: “विटामिन ड्रिप के पैसे क्यों काटे?”</p>
          </div>
          <div className="mt-10 border-l-2 border-brass pl-6">
            <p className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-muted">Nivaaran</p>
            <p className="mt-3 text-[17px] leading-relaxed text-text">Because one paper is missing. Clause 4.2 excludes vitamins “unless prescribed by the treating doctor”. The prescription isn't in your documents, so the drip isn't counted in your estimate yet. Ask the hospital for the doctor's prescription and it can be reconsidered.</p>
            <p className="mt-4 font-mono text-[11px] text-accent">Cites · policy wording, clause 4.2</p>
          </div>
        </div>
      </div>
    </section>
  );
}

const ACTIONS = ["Ask the insurer, politely and in writing", "Find the one missing paper", "Check the clause they are relying on", "See what a cheaper room would have changed", "Download a report for the TPA desk"];

const CAPABILITIES: [string, string][] = [
  ["Line-by-line coverage", "Every charge on the bill is matched to the clause that decides it, quoted word for word with the page number."],
  ["Claim map", "Follow any charge from the bill to the clause that applies and the step where the amount changed."],
  ["Assistant in English, Hindi and Marathi", "Ask in plain words. Answers come from your own documents, and the whole policy can be summarised and read out loud."],
  ["Mismatch checks", "Catches places where the brochure, policy and bill say different things, and drafts a polite letter asking why."],
  ["What-if calculator", "Try a cheaper room, a shorter stay or a different policy version and see how your share changes."],
  ["Clause search", "Search the whole policy by meaning, not just keywords, and see why each result came up."],
];

const SECURITY: [string, string][] = [["Hashed passwords", "Salted scrypt hashes only."], ["Secure sessions", "HTTP-only, same-site cookies with server-side expiry."], ["Per-account isolation", "Checked on the server for every request."],
  ["Local processing", "No external AI unless the operator configures it."], ["Private file storage", "Random identifiers, served only to the owner."], ["You control deletion", "Delete documents, claims or your whole account."]];

export default function Landing() {
  const { start, busy, err } = useStart();
  return (
    <div className="min-h-dvh overflow-x-clip bg-paper text-text">
      <CinematicIntro />
      <Nav onStart={() => start()} busy={busy} />
      <main>
        <Hero onStart={() => start()} onAsk={(q) => start(`/assistant?q=${encodeURIComponent(q)}`)} busy={busy} err={err} />
        <Premise />
        <Complexity />
        <Activation />
        <Fairness />
        <Calculation />
        <AssistantDemo onStart={start} />

        <section className="border-t border-line bg-paper px-5 py-28 md:px-10">
          <div className="mx-auto grid max-w-[1440px] gap-12 lg:grid-cols-12">
            <h2 className={cn("lg:col-span-5", H2)}>When something doesn't add up.</h2>
            <ul className="border-t border-line-2 lg:col-span-6 lg:col-start-7">
              {ACTIONS.map((t, i) => (
                <li key={t} className="group flex items-center gap-6 border-b border-line-2 py-5">
                  <span className="font-mono text-[11px] text-brass">0{i + 1}</span>
                  <span className="flex-1 font-display text-[24px] leading-tight text-ink transition-transform duration-300 group-hover:translate-x-1.5 md:text-[28px]">{t}</span>
                  <ArrowUpRight className="size-5 text-faint transition-colors group-hover:text-brass" strokeWidth={1.5} aria-hidden />
                </li>))}
            </ul>
          </div>
        </section>

        <section id="capabilities" className="border-t border-line bg-card px-5 py-28 md:px-10">
          <div className="mx-auto max-w-[1440px]">
            <div className="flex flex-wrap items-end justify-between gap-6"><h2 className={H2}>What's inside.</h2><p className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted">Six tools, one claim</p></div>
            <dl className="mt-14 grid gap-x-16 md:grid-cols-2">
              {CAPABILITIES.map(([c, d], i) => (
                <div key={c} className="grid grid-cols-[44px_1fr] border-t border-line py-8">
                  <span className="pt-2 font-mono text-[11px] text-brass">0{i + 1}</span>
                  <div><dt className="font-display text-[30px] leading-tight text-ink">{c}</dt><dd className="mt-2 max-w-md text-[15px] leading-relaxed text-muted">{d}</dd></div>
                </div>))}
            </dl>
          </div>
        </section>

        <section id="security" className="theme-forest border-t border-white/10 bg-forest px-5 py-28 md:px-10">
          <div className="mx-auto grid max-w-[1440px] gap-14 lg:grid-cols-12">
            <div className="lg:col-span-5">
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-sage">Security</p>
              <h2 className={cn("mt-6", H2)}>Your documents are <span className="italic text-brass">yours.</span></h2>
              <p className="mt-8 max-w-sm font-mono text-[11px] leading-relaxed text-ivory/45">Not claimed: no security certification or compliance attestation; files are not encrypted at rest; deletion is standard deletion.</p>
            </div>
            <dl className="lg:col-span-6 lg:col-start-7">
              {SECURITY.map(([t, d]) => (
                <div key={t} className="grid gap-1 border-b border-white/10 py-5 first:border-t sm:grid-cols-[200px_1fr] sm:gap-6">
                  <dt className="text-[15px] font-medium text-ivory">{t}</dt><dd className="text-[15px] text-sage">{d}</dd>
                </div>))}
            </dl>
          </div>
        </section>

        <section className="paper-grain bg-paper px-5 py-32 md:px-10">
          <div className="mx-auto max-w-[1440px]">
            <h2 className="max-w-[18ch] font-display text-[13vw] leading-[0.92] tracking-[-0.02em] text-ink md:text-[7vw]">Check your next claim <span className="italic text-accent">before you file it.</span></h2>
            <div className="mt-12 flex flex-wrap items-center gap-4 border-t border-line pt-8">
              <button className="btn-primary h-12 px-7" onClick={() => start()} disabled={busy}>Try the demo</button>
              <Link to="/register" className="btn-secondary h-12 px-7">Create an account</Link>
              <span className="ml-auto hidden font-mono text-[11px] uppercase tracking-[0.16em] text-muted md:inline">Synthetic demo · no account needed</span>
            </div>
          </div>
        </section>
      </main>
      <footer className="theme-forest bg-forest-2 px-5 py-12 text-ivory/60 md:px-10">
        <div className="mx-auto flex max-w-[1440px] flex-col gap-6 md:flex-row md:items-end">
          <div><span className="font-display text-[30px] leading-none text-ivory">Nivaaran</span>
            <p className="mt-2 font-mono text-[10.5px] uppercase tracking-[0.16em] text-sage/70">Insurance clarity. Backed by evidence.</p></div>
          <button onClick={replayIntro} className="text-left font-mono text-[11px] uppercase tracking-[0.14em] hover:text-brass md:ml-10">Replay intro</button>
          <div className="flex-1" /><p className="max-w-xl text-[13px]">Decision-support estimates only. No guarantee of insurer approval or reimbursement. Demo documents are synthetic.</p>
        </div>
      </footer>
    </div>
  );
}
