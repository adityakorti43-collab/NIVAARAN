import { BookOpenText, Gauge, ListChecks, Loader2, Pause, Volume2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/api";
import { cn } from "../lib/format";
import { getSpeed, prefetchSpeech, setSpeed, speak, speakSequence, SPEEDS, speechSupported, stopSpeaking, usingNeuralVoice, voiceNote, type Lang } from "../lib/speech";
import type { Clause, DocumentRecord, PolicySummary } from "../lib/types";
import { PolicyBrief } from "./PolicyBrief";

// Read-aloud is in English, in a natural female voice. (The page text itself can be shown in any Indian language
// with the site-wide language switcher.)
const LANGS: Lang[] = ["en"];
type Mode = "quick" | "summary" | "full";

/**
 * A policy in plain words: a practical summary (every point cites its clause) plus a spoken explanation in English,
 * Hindi. "Explain it to me" talks you through the policy in plain words; the full summary and the full wording can also be
 * read out. Summaries are built on the server from the clauses' structured reading; the original wording governs.
 */
export function PolicyReader({ doc }: { doc: DocumentRecord }) {
  const lang: Lang = "en";
  const [summaries, setSummaries] = useState<Partial<Record<Lang, PolicySummary>>>({});
  const [clauses, setClauses] = useState<Clause[] | null>(null);
  const [playing, setPlaying] = useState<Mode | null>(null);
  const [speed, setSpeedState] = useState(getSpeed);
  const [current, setCurrent] = useState(-1);
  const [err, setErr] = useState<string | null>(null);
  const listRef = useRef<HTMLOListElement>(null);
  const summary = summaries[lang];

  // Fetch all three languages at once so switching language is instant.
  useEffect(() => {
    let live = true;
    stopSpeaking(); setPlaying(null); setCurrent(-1); setSummaries({}); setClauses(null); setErr(null);
    for (const l of LANGS) {
      api.policySummary(doc.document_id, l)
        .then((s) => live && setSummaries((m) => ({ ...m, [l]: s })))
        .catch((e) => live && l === "en" && setErr((e as Error).message));
    }
    return () => { live = false; };
  }, [doc.document_id]);
  useEffect(() => () => stopSpeaking(), []);
  // Warm up the voice for the language on screen, so "Explain it to me" starts straight away.
  useEffect(() => { if (summary) prefetchSpeech(summary.quick_text, lang); }, [summary, lang]);
  const [neural, setNeural] = useState(false);
  useEffect(() => { void usingNeuralVoice().then(setNeural); }, []);
  useEffect(() => { listRef.current?.querySelector(`[data-i="${current}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [current]);

  const stop = () => { stopSpeaking(); setPlaying(null); setCurrent(-1); };
  const play = (mode: "quick" | "summary", l: Lang = lang, restart = false) => {
    const s = summaries[l];
    if (!restart && playing === mode) return stop();
    if (!s) return;
    setPlaying(mode);
    speak(mode === "quick" ? s.quick_text : s.text, l, () => setPlaying(null));
  };
  const playFull = async () => {
    if (playing === "full") return stop();
    setErr(null);
    const cl = clauses ?? (await api.document(doc.document_id)).clauses ?? [];
    setClauses(cl);
    if (!cl.length) { setErr("No clauses were extracted from this document."); return; }
    setPlaying("full");
    speakSequence(cl.map((c) => `Clause ${c.section}. ${c.heading}. ${c.text}`), "en", setCurrent, () => { setPlaying(null); setCurrent(-1); });
  };
  const changeSpeed = (v: number) => {
    setSpeed(v); setSpeedState(v);
    if (playing === "quick" || playing === "summary") play(playing, lang, true);   // restart at the new speed
  };
  const note = neural ? null : voiceNote(lang);
  const canSpeak = speechSupported() || neural;

  return (
    <div className="space-y-5" data-testid="policy-reader">
      <div className="flex flex-wrap items-center gap-2.5">
        {canSpeak && <>
          <button type="button" className="btn-primary" onClick={() => play("quick")} disabled={!summary} data-testid="play-quick">
            {playing === "quick" ? <><Pause className="size-4" /> Stop</> : !summary ? <><Loader2 className="size-4 animate-spin" /> Preparing</> : <><Volume2 className="size-4" /> Explain it to me</>}
          </button>
          <label className="inline-flex items-center gap-1.5 text-[13px] text-muted">
            <Gauge className="size-4" aria-hidden />
            <select aria-label="Reading speed" className="input h-9 w-[78px] py-0 text-[13px]" value={speed} onChange={(e) => changeSpeed(Number(e.target.value))} data-testid="speed">
              {SPEEDS.map((v) => <option key={v} value={v}>{v}×</option>)}
            </select>
          </label>
        </>}
      </div>
      {canSpeak && (
        <div className="-mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[13px]">
          <button type="button" className="inline-flex items-center gap-1.5 text-accent hover:underline disabled:text-faint" onClick={() => play("summary")} disabled={!summary} data-testid="play-summary">
            {playing === "summary" ? <><Pause className="size-3.5" /> Stop</> : <><ListChecks className="size-3.5" /> Read every point</>}
          </button>
          <button type="button" className="inline-flex items-center gap-1.5 text-accent hover:underline" onClick={playFull} data-testid="play-full">
            {playing === "full" ? <><Pause className="size-3.5" /> Stop reading</> : <><BookOpenText className="size-3.5" /> Read the full wording (English)</>}
          </button>
        </div>
      )}
      {!canSpeak && <p className="text-sm text-muted">Read-aloud isn't supported in this browser. The summary below can still be read.</p>}
      {note && <p className="text-[12px] text-faint">{note}</p>}
      {err && <p role="alert" className="text-sm text-excluded">{err}</p>}

      {playing === "full" && clauses && (
        <ol ref={listRef} className="max-h-72 space-y-1 overflow-y-auto border-l border-line-2 pl-4" aria-live="polite">
          {clauses.map((c, i) => (
            <li key={c.clause_id} data-i={i} className={cn("rounded-[3px] px-2 py-1 text-[13px] transition-colors", i === current ? "bg-brass/15 text-ink" : "text-muted")}>
              <span className="mr-2 font-mono text-[11px] text-brass">{c.section}</span>{c.heading}
            </li>))}
        </ol>
      )}

      {summary ? (
        <PolicyBrief summary={summary} docId={doc.document_id} lang={lang} clauseCount={doc.clause_count} title={doc.metadata.title ?? undefined} />
      ) : !err && <p className="flex items-center gap-2 border-t border-line pt-5 text-sm text-muted"><Loader2 className="size-4 animate-spin" /> Preparing the summary…</p>}
    </div>
  );
}
