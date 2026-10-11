import { Check, Languages, Loader2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { initLanguage, setLanguage, subscribe, type Language } from "../lib/i18n";
import { cn } from "../lib/format";

let cache: Promise<{ enabled: boolean; languages: Language[]; provider?: string | null }> | null = null;
const loadLanguages = () => (cache ??= fetch("/api/translate/languages").then((r) => r.json()).catch(() => ({ enabled: false, languages: [] })));
let started = false;

/** The page-language menu. Every language of India that the translation service supports, in its own script. */
export function LanguagePicker({ dark = false }: { dark?: boolean }) {
  const [open, setOpen] = useState(false);
  const [info, setInfo] = useState<{ enabled: boolean; languages: Language[]; provider?: string | null } | null>(null);
  const [st, setSt] = useState({ lang: "en", busy: false, error: null as string | null });
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => subscribe(setSt), []);
  useEffect(() => { void loadLanguages().then((i) => { setInfo(i); if (!started && i.enabled) { started = true; initLanguage(i.languages); } }); }, []);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!box.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  const current = info?.languages.find((l) => l.code === st.lang);

  return (
    <div className="relative" ref={box} translate="no">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Change language" data-testid="language-picker"
        className={cn("inline-flex h-9 items-center gap-1.5 rounded-full border px-3 text-[13px] font-medium transition-colors",
          dark ? "border-white/20 text-ivory hover:border-brass" : "border-line-2 text-text hover:border-brass")}>
        {st.busy ? <Loader2 className="size-4 animate-spin" /> : <Languages className="size-4" />}
        <span className="hidden sm:inline">{current?.native ?? "English"}</span>
      </button>
      <AnimatePresence>
        {open && (
          <motion.div initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }}
            className="card-raised absolute right-0 top-11 z-[60] w-[min(92vw,300px)] p-1.5 text-ink" role="listbox" aria-label="Languages">
            <p className="px-3 pb-1.5 pt-2 text-[11.5px] text-muted">
              {info?.enabled ? `${info.provider ?? "Machine translation"}. Amounts and clause numbers stay exactly as in your policy.` : "Translation isn't set up on this server yet. The site operator needs to add a Gemini (or Azure) key."}
            </p>
            <ul className="max-h-[min(60vh,420px)] overflow-y-auto">
              {(info?.languages ?? [{ code: "en", name: "English", native: "English", rtl: false }]).map((l) => (
                <li key={l.code}>
                  <button type="button" role="option" aria-selected={st.lang === l.code} disabled={!info?.enabled && l.code !== "en"}
                    onClick={() => { setLanguage(l.code, l.rtl); setOpen(false); }}
                    className="flex w-full items-center gap-3 rounded-[6px] px-3 py-2 text-left hover:bg-paper disabled:cursor-not-allowed disabled:opacity-40" data-testid={`lang-${l.code}`}>
                    <span className="min-w-0 flex-1"><span className="block text-[14px] text-ink">{l.native}</span><span className="block text-[11.5px] text-muted">{l.name}</span></span>
                    {st.lang === l.code && <Check className="size-4 text-accent" />}
                  </button>
                </li>))}
            </ul>
            {st.error && <p className="px-3 py-2 text-[12px] text-excluded">{st.error}</p>}
          </motion.div>)}
      </AnimatePresence>
    </div>
  );
}
