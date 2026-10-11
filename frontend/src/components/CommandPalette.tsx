import { ArrowRight, Command, CornerDownLeft, Search } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { cn } from "../lib/format";
import { useApp } from "../lib/store";
import { NAV } from "./nav";

type Item = { id: string; label: string; hint: string; icon: typeof Search; run: () => void | Promise<void> };

/** Ctrl/⌘+K command palette: jump to any workspace or run a common action. */
export function CommandPalette({ open, setOpen }: { open: boolean; setOpen: (v: boolean) => void }) {
  const nav = useNavigate();
  const { refresh, setActiveClaimId, activeClaimId, claims } = useApp();
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const [busy, setBusy] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setOpen(!open); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);
  useEffect(() => { if (open) { setQ(""); setIdx(0); setTimeout(() => input.current?.focus(), 20); } }, [open]);

  const items: Item[] = useMemo(() => {
    const go = (to: string) => () => { nav(to); setOpen(false); };
    const base: Item[] = NAV.map((n) => ({ id: n.to, label: n.label, hint: "Go to", icon: n.icon, run: go(n.to) }));
    base.push({ id: "home", label: "Landing page", hint: "Go to", icon: ArrowRight, run: go("/") });
    if (activeClaimId) {
      base.push({ id: "pdf", label: "Download PDF report for active claim", hint: "Action", icon: ArrowRight, run: () => { window.location.href = api.reportUrl(activeClaimId, "pdf"); setOpen(false); } });
    }
    claims.forEach((c) => base.push({ id: `claim:${c.claim_id}`, label: `Switch to claim: ${c.title}`, hint: "Claim", icon: ArrowRight,
      run: () => { setActiveClaimId(c.claim_id); nav("/claim"); setOpen(false); } }));
    return base;
  }, [nav, setOpen, refresh, setActiveClaimId, activeClaimId, claims]);
  const shown = items.filter((i) => i.label.toLowerCase().includes(q.toLowerCase()));

  async function run(i: Item) {
    setBusy(i.id);
    try { await i.run(); } finally { setBusy(null); }
  }

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[70] flex items-start justify-center px-4 pt-[12vh]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-forest/45 backdrop-blur-sm" onClick={() => setOpen(false)} aria-hidden />
          <motion.div role="dialog" aria-modal="true" aria-label="Command palette" className="card-raised relative w-full max-w-xl overflow-hidden"
            initial={{ opacity: 0, y: -12, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -8, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 420, damping: 34 }}>
            <div className="flex items-center gap-3 border-b border-line px-4">
              <Search className="size-4 text-faint" aria-hidden />
              <input ref={input} value={q} onChange={(e) => { setQ(e.target.value); setIdx(0); }} placeholder="Search workspaces and actions…"
                aria-label="Search commands" className="h-12 w-full bg-transparent text-sm text-ink placeholder:text-faint focus:outline-none"
                onKeyDown={(e) => {
                  if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(i + 1, shown.length - 1)); }
                  if (e.key === "ArrowUp") { e.preventDefault(); setIdx((i) => Math.max(i - 1, 0)); }
                  if (e.key === "Enter" && shown[idx]) run(shown[idx]);
                  if (e.key === "Escape") setOpen(false);
                }} />
              <kbd className="rounded-md border border-line-2 px-1.5 py-0.5 text-[10px] text-faint">Esc</kbd>
            </div>
            <ul className="max-h-[50vh] overflow-y-auto p-1.5" role="listbox">
              {shown.map((i, n) => (
                <li key={i.id} role="option" aria-selected={n === idx}>
                  <button onMouseEnter={() => setIdx(n)} onClick={() => run(i)}
                    className={cn("flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm", n === idx ? "bg-accent/10 text-ink" : "text-text")}>
                    <i.icon className={cn("size-4", n === idx ? "text-accent" : "text-faint")} aria-hidden />
                    <span className="flex-1">{i.label}</span>
                    <span className="text-[11px] text-faint">{busy === i.id ? "Working…" : i.hint}</span>
                    {n === idx && <CornerDownLeft className="size-3.5 text-faint" aria-hidden />}
                  </button>
                </li>
              ))}
              {shown.length === 0 && <li className="px-3 py-6 text-center text-sm text-muted">No matching command.</li>}
            </ul>
            <div className="flex items-center gap-2 border-t border-line px-4 py-2 text-[11px] text-faint"><Command className="size-3" aria-hidden /> K to toggle · ↑↓ to move · Enter to run</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
