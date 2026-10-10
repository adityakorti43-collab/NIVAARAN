import { Command, LogOut, Menu, Search, Settings as SettingsIcon, X } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Suspense, useEffect, useState } from "react";
import { Link, Navigate, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { cn } from "../lib/format";
import { useApp } from "../lib/store";
import { AmbientField } from "./AmbientField";
import { CommandPalette } from "./CommandPalette";
import { Copilot } from "./Copilot";
import { NAV, NAV_GROUPS } from "./nav";
import { PageSkeleton } from "./ui";

export function LogoMark({ className = "size-8" }: { className?: string; onDark?: boolean }) {
  return (
    <svg viewBox="0 0 64 64" className={cn("shrink-0", className)} aria-hidden>
      <rect width="64" height="64" rx="7" fill="#b69a62" />
      <path d="M19 45V19l26 26V19" fill="none" stroke="#142d27" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo({ compact = false, onDark = false }: { compact?: boolean; onDark?: boolean }) {
  return (
    <Link to="/" className="flex items-center gap-2.5 rounded-lg" aria-label="Nivaaran home">
      <LogoMark onDark={onDark} />
      {!compact && (
        <span className="leading-tight">
          <span className={cn("block font-display text-[25px] leading-none tracking-[-0.01em]", onDark ? "text-white" : "text-ink")}>Nivaaran</span>
          <span className={cn("mt-1 block font-mono text-[9.5px] uppercase tracking-[0.14em]", onDark ? "text-sage/70" : "text-faint")}>Insurance clarity. Backed by evidence.</span>
        </span>
      )}
    </Link>
  );
}

function Nav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Main" className="space-y-5">
      {NAV_GROUPS.map((g) => (
        <div key={g.label}>
          <p className="mb-1.5 px-3 font-mono text-[10px] uppercase tracking-[0.18em] text-sage/55">{g.label}</p>
          <div className="flex flex-col gap-0.5">
            {g.items.map(({ to, label, icon: Icon }) => (
              <NavLink key={to} to={to} onClick={onNavigate}
                className={({ isActive }) => cn("relative flex items-center gap-3 rounded-[3px] px-3 py-[7px] text-[14px] transition-colors",
                  isActive ? "font-semibold text-ivory" : "font-medium text-ivory/70 hover:bg-white/[0.05] hover:text-ivory")}>
                {({ isActive }) => (
                  <>
                    {isActive && <motion.span layoutId="nav-active" className="absolute inset-0 rounded-[3px] bg-white/[0.07] shadow-[inset_2px_0_0_#b69a62]" transition={{ type: "spring", stiffness: 500, damping: 40 }} />}
                    <Icon className={cn("relative size-4 shrink-0", isActive ? "text-brass" : "")} strokeWidth={1.6} aria-hidden />
                    <span className="relative">{label}</span>
                  </>
                )}
              </NavLink>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}

function ClaimPicker() {
  const { claims, activeClaimId, setActiveClaimId } = useApp();
  if (!claims.length) return null;
  return (
    <div>
      <label htmlFor="claim-picker" className="mb-1.5 block px-1 font-mono text-[10px] uppercase tracking-[0.18em] text-sage/55">Active claim</label>
      <select id="claim-picker" value={activeClaimId ?? ""} onChange={(e) => setActiveClaimId(e.target.value)}
        className="w-full rounded-[3px] border border-white/15 bg-white/[0.05] px-3 py-2 text-[13px] text-ivory focus:outline-none focus:ring-2 focus:ring-brass/50">
        {claims.map((c) => <option key={c.claim_id} value={c.claim_id}>{c.title}</option>)}
      </select>
    </div>
  );
}

function UserMenu() {
  const { user, signOut } = useApp();
  const nav = useNavigate();
  const [open, setOpen] = useState(false);
  if (!user) return null;
  return (
    <div className="relative">
      <button onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Account menu" data-testid="user-menu"
        className="flex items-center gap-2 rounded-full border border-line-2 py-1 pl-1 pr-3 text-xs text-text hover:border-brass">
        <span className="grid size-7 place-items-center rounded-full bg-forest text-[12px] font-semibold text-ivory">{user.name.slice(0, 1).toUpperCase()}</span>
        <span className="hidden max-w-[120px] truncate sm:inline">{user.is_demo ? "Demo workspace" : user.name}</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: -6, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6 }}
            className="card-raised absolute right-0 top-11 z-50 w-60 p-1.5" onMouseLeave={() => setOpen(false)}>
            <p className="px-3 py-2 text-xs text-muted">{user.is_demo ? "Synthetic demo workspace (deleted after 24 h)" : user.phone ?? user.email}</p>
            <Link to="/settings" onClick={() => setOpen(false)} className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-text hover:bg-ink/[0.05]"><SettingsIcon className="size-4" /> Settings</Link>
            <button onClick={async () => { nav("/", { replace: true }); await signOut(); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-text hover:bg-ink/[0.05]" data-testid="sign-out"><LogOut className="size-4" /> Sign out</button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function Shell() {
  const { user, authLoading } = useApp();
  const [open, setOpen] = useState(false);
  const [palette, setPalette] = useState(false);
  const loc = useLocation();
  const reduce = useReducedMotion();
  const current = NAV.find((n) => n.to === loc.pathname);
  useEffect(() => { setOpen(false); window.scrollTo({ top: 0 }); }, [loc.pathname]);
  if (authLoading) return <div className="min-h-dvh bg-paper p-10"><PageSkeleton /></div>;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;

  return (
    <>
    <AmbientField />
    <div className="relative min-h-dvh lg:grid lg:grid-cols-[268px_minmax(0,1fr)]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[80] btn-primary">Skip to content</a>
      <aside className="theme-forest relative z-10 hidden flex-col gap-6 overflow-hidden lg:col-start-1 lg:row-start-1 border-r border-line bg-ink-2 px-4 py-6 lg:sticky lg:top-0 lg:flex lg:h-dvh">
        <div className="pointer-events-none absolute -bottom-24 -left-24 size-72 rounded-full bg-brass/[0.08] blur-3xl" aria-hidden />
        <div className="relative"><Logo onDark /></div>
        <div className="relative"><ClaimPicker /></div>
        <div className="relative -mx-1 flex-1 overflow-y-auto px-1"><Nav /></div>
        <p className="relative border-t border-white/10 px-1 pt-4 font-mono text-[10px] uppercase leading-relaxed tracking-[0.12em] text-sage/50">Estimates only · not an insurer decision</p>
      </aside>

      <div className="ambient relative z-10 min-w-0 lg:col-start-2 lg:row-start-1">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-line bg-paper/85 px-4 backdrop-blur-md md:px-8">
          <button className="btn-ghost -ml-2 p-2 lg:hidden" aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open} onClick={() => setOpen(!open)}>
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
          <div className="lg:hidden"><Logo compact /></div>
          <p className="hidden truncate font-mono text-[11px] uppercase tracking-[0.14em] text-muted md:block"><Link to="/" className="hover:text-ink">Nivaaran</Link> <span className="text-brass">/</span> <span className="text-ink">{current?.label ?? "Workspace"}</span></p>
          <div className="flex-1" />
          <button onClick={() => setPalette(true)} className="btn-secondary h-9 gap-2 px-3.5 text-xs font-medium text-muted" aria-label="Open command palette">
            <Search className="size-3.5" /> <span className="hidden sm:inline">Search or jump to</span>
            <kbd className="hidden items-center gap-0.5 rounded-md border border-line-2 bg-paper px-1 text-[10px] sm:inline-flex"><Command className="size-2.5" />K</kbd>
          </button>
          <UserMenu />
        </header>

        <AnimatePresence>
          {open && (
            <motion.div className="fixed inset-0 z-40 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <div className="absolute inset-0 bg-forest/40 backdrop-blur-sm" onClick={() => setOpen(false)} aria-hidden />
              <motion.div className="theme-forest absolute inset-y-0 left-0 flex w-[86%] max-w-[320px] flex-col gap-5 overflow-y-auto bg-ink-2 px-4 py-5"
                initial={{ x: "-100%" }} animate={{ x: 0 }} exit={{ x: "-100%" }} transition={{ type: "spring", stiffness: 380, damping: 38 }}>
                <div className="flex items-center justify-between"><Logo onDark />
                  <button className="rounded-full p-2 text-white/70 hover:bg-white/10 hover:text-white" aria-label="Close menu" onClick={() => setOpen(false)}><X className="size-5" /></button></div>
                <ClaimPicker />
                <Nav onNavigate={() => setOpen(false)} />
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        <main id="main" className="mx-auto w-full max-w-[1440px] px-4 py-7 md:px-8 md:py-10">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={loc.pathname} initial={reduce ? false : { opacity: 0, y: 10, filter: "blur(4px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              exit={reduce ? undefined : { opacity: 0, y: -6 }} transition={{ duration: 0.32, ease: [0.22, 1, 0.36, 1] }}>
              <Suspense fallback={<PageSkeleton />}><Outlet /></Suspense>
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
      <CommandPalette open={palette} setOpen={setPalette} />
      <Copilot />
    </div>
    </>
  );
}
