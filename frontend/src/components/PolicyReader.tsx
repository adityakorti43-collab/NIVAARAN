import { BookOpenText, Loader2, Pause, Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { cn } from "../lib/format";
import { LANG_LABEL, speak, speakSequence, speechSupported, stopSpeaking, voiceNote, type Lang } from "../lib/speech";
import type { Clause, DocumentRecord, PolicySummary } from "../lib/types";
import { useClauseViewer } from "./ClauseViewer";

/**
 * Listen to a policy: the full wording read clause by clause (with the clause being read highlighted), or a short
 * summary in English, Hindi or Marathi. Summaries are built on the server from the clauses' structured reading, so
 * every point cites its clause; the original wording always governs.
 */
export function PolicyReader({ doc }: { doc: DocumentRecord }) {
  const { openClause } = useClauseViewer();
  const [lang, setLang] = useState<Lang>("hi");
  const [summary, setSummary] = useState<PolicySummary | null>(null);
  const [clauses, setClauses] = useState<Clause[] | null>(null);
  const [playing, setPlaying] = useState<"summary" | "full" | null>(null);
  const [loading, setLoading] = useState(false);
  const [current, setCurrent] = useState(-1);
  const [err, setErr] = useState<string | null>(null);
  const listRef = useRef<HTMLOListElement>(null);

  useEffect(() => { stopSpeaking(); setPlaying(null); setCurrent(-1); setSummary(null); setClauses(null); }, [doc.document_id]);
  useEffect(() => {
    let live = true;
    setLoading(true); setErr(null);
    api.policySummary(doc.document_id, lang).then((s) => live && setSummary(s)).catch((e) => live && setErr((e as Error).message)).finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [doc.document_id, lang]);
  useEffect(() => () => stopSpeaking(), []);
  useEffect(() => { listRef.current?.querySelector(`[data-i="${current}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [current]);

  if (!speechSupported()) return <p className="text-sm text-muted">Read-aloud isn't supported in this browser. The summary below can still be read.</p>;

  const stop = () => { stopSpeaking(); setPlaying(null); setCurrent(-1); };
  const playSummary = () => {
    if (playing) return stop();
    if (!summary) return;
    setPlaying("summary");
    speak(summary.text, lang, () => setPlaying(null));
  };
  const playFull = async () => {
    if (playing) return stop();
    setErr(null);
    const cl = clauses ?? (await api.document(doc.document_id)).clauses ?? [];
    setClauses(cl);
    if (!cl.length) { setErr("No clauses were extracted from this document."); return; }
    setPlaying("full");
    speakSequence(cl.map((c) => `Clause ${c.section}. ${c.heading}. ${c.text}`), "en", setCurrent, () => { setPlaying(null); setCurrent(-1); });
  };
  const note = voiceNote(lang);

  return (
    <div className="space-y-5" data-testid="policy-reader">
      <div className="flex flex-wrap items-center gap-3">
        <div className="seg" role="radiogroup" aria-label="Summary language">
          {(["en", "hi", "mr"] as Lang[]).map((l) => (
            <button key={l} type="button" role="radio" aria-checked={lang === l} onClick={() => { stop(); setLang(l); }} data-testid={`summary-${l}`}
              className={cn("rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors", lang === l ? "chip-on" : "text-muted hover:text-ink")}>{LANG_LABEL[l]}</button>))}
        </div>
        <button type="button" className="btn-primary" onClick={playSummary} disabled={!summary && !playing} data-testid="play-summary">
          {playing === "summary" ? <><Pause className="size-4" /> Stop</> : loading ? <><Loader2 className="size-4 animate-spin" /> Preparing</> : <><Volume2 className="size-4" /> Listen to the summary</>}
        </button>
        <button type="button" className="btn-secondary" onClick={playFull} data-testid="play-full">
          {playing === "full" ? <><Pause className="size-4" /> Stop reading</> : <><BookOpenText className="size-4" /> Read the full policy (English)</>}
        </button>
      </div>
      {note && lang !== "en" && <p className="text-[12px] text-faint">{note}</p>}
      {err && <p role="alert" className="text-sm text-excluded">{err}</p>}

      {playing === "full" && clauses && (
        <ol ref={listRef} className="max-h-72 space-y-1 overflow-y-auto border-l border-line-2 pl-4" aria-live="polite">
          {clauses.map((c, i) => (
            <li key={c.clause_id} data-i={i} className={cn("rounded-[3px] px-2 py-1 text-[13px] transition-colors", i === current ? "bg-brass/15 text-ink" : "text-muted")}>
              <span className="mr-2 font-mono text-[11px] text-brass">{c.section}</span>{c.heading}
            </li>))}
        </ol>
      )}

      {summary && (
        <article className="border-t border-line pt-5" lang={lang === "en" ? "en" : lang === "hi" ? "hi" : "mr"}>
          <p className="text-[14px] text-text">{summary.intro}</p>
          <div className="mt-4 grid gap-x-10 gap-y-6 md:grid-cols-2">
            {summary.sections.map((s) => (
              <section key={s.heading}>
                <h3 className="font-mono text-[10.5px] uppercase tracking-[0.16em] text-muted">{s.heading}</h3>
                <ul className="mt-2 space-y-1.5">
                  {s.items.map((it) => (
                    <li key={it.clause + it.text} className="grid grid-cols-[auto_1fr] gap-2 text-[13.5px] leading-snug text-text">
                      <button type="button" onClick={() => openClause(`${doc.document_id}:${it.clause}`)} className="font-mono text-[11px] text-accent hover:underline" aria-label={`Open clause ${it.clause}`}>{it.clause}</button>
                      <span>{it.text}</span>
                    </li>))}
                </ul>
              </section>))}
          </div>
          <p className="mt-5 text-[12px] text-faint">{summary.outro}</p>
        </article>
      )}
    </div>
  );
}
