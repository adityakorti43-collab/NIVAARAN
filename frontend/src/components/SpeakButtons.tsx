import { Loader2, Square, Volume2 } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { speak, speechSupported, stopSpeaking, voiceNote, type Lang } from "../lib/speech";
import { cn } from "../lib/format";

function Wave() {
  return (
    <span className="flex h-3.5 items-end gap-[2px]" aria-hidden>
      {[0, 1, 2, 3].map((i) => (
        <motion.span key={i} className="w-[3px] rounded-full bg-current" animate={{ height: ["30%", "100%", "40%", "80%", "30%"] }}
          transition={{ duration: 0.9, repeat: Infinity, delay: i * 0.12 }} />))}
    </span>
  );
}

/**
 * English / Hindi / Marathi read-aloud. `getText(lang)` returns the text to speak (it may call the server for an
 * explanation in that language); returning null shows the reason instead of speaking.
 */
export function SpeakButtons({ getText, className, compact, langs = ["en", "hi", "mr"] }: { getText: (lang: Lang) => Promise<string | null>; className?: string; compact?: boolean; langs?: Lang[] }) {
  const [state, setState] = useState<{ lang: Lang; phase: "loading" | "speaking" } | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [, force] = useState(0);
  useEffect(() => {
    if (!speechSupported()) return;
    const f = () => force((n) => n + 1);
    window.speechSynthesis.addEventListener?.("voiceschanged", f);
    return () => { window.speechSynthesis.removeEventListener?.("voiceschanged", f); stopSpeaking(); };
  }, []);
  if (!speechSupported()) return <span className="text-[11px] text-faint">Read-aloud isn't supported in this browser.</span>;

  async function go(lang: Lang) {
    if (state) { stopSpeaking(); setState(null); return; }
    setNote(null); setState({ lang, phase: "loading" });
    try {
      const text = await getText(lang);
      if (!text) { setState(null); return; }
      setNote(voiceNote(lang));
      setState({ lang, phase: "speaking" });
      speak(text, lang, () => setState(null));
    } catch (e) { setNote((e as Error).message); setState(null); }
  }

  const Btn = ({ lang, label }: { lang: Lang; label: string }) => {
    const active = state?.lang === lang;
    return (
      <button type="button" onClick={() => go(lang)} aria-pressed={active} data-testid={`speak-${lang}`}
        className={cn("inline-flex items-center gap-1.5 rounded-[3px] border px-2.5 py-1 text-[12px] font-medium transition-all",
          active ? "border-accent bg-accent/10 text-accent" : "border-line-2 text-muted hover:border-accent/60 hover:text-accent")}>
        {active ? (state!.phase === "loading" ? <Loader2 className="size-3.5 animate-spin" /> : <><Wave /><Square className="size-3" /></>) : <Volume2 className="size-3.5" />}
        {!compact && label}
        {compact && <span>{lang === "hi" ? "हिं" : lang === "mr" ? "मरा" : "EN"}</span>}
      </button>
    );
  };
  return (
    <span className={cn("inline-flex flex-wrap items-center gap-1.5", className)}>
      {langs.includes("en") && <Btn lang="en" label="Listen" />}
      {langs.includes("hi") && <Btn lang="hi" label="हिंदी में सुनें" />}
      {langs.includes("mr") && <Btn lang="mr" label="मराठीत ऐका" />}
      {note && <span className="w-full text-[11px] text-faint">{note}</span>}
    </span>
  );
}
