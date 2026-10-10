import { ArrowRight } from "lucide-react";
import { useReducedMotion } from "motion/react";
import { useEffect, useState } from "react";

/** Example questions the assistant answers from the synthetic demo case, in English, Hindi and Marathi. */
const ASK_EXAMPLES = [
  "Why did they cut my room rent?",
  "क्या मेरे कमरे का पूरा किराया मिलेगा?",
  "Why didn't they pay for the vitamin drip?",
  "माझ्या खिशातून किती पैसे जातील?",
  "Is the ICU charge covered?",
  "मेरी जेब से कितना पैसा जाएगा?",
];

/** Typewriter placeholder cycling through the examples. Static under reduced motion or while the user is typing. */
function useTypedPlaceholder(active: boolean) {
  const reduce = useReducedMotion();
  const [text, setText] = useState(ASK_EXAMPLES[0]);
  useEffect(() => {
    if (reduce || !active) return;
    let i = 0, n = 0, del = false, t = 0;
    const tick = () => {
      const full = ASK_EXAMPLES[i];
      n += del ? -1 : 1;
      setText(full.slice(0, n));
      let wait = del ? 22 : 45;
      if (!del && n >= full.length) { del = true; wait = 1800; }
      else if (del && n <= 0) { del = false; i = (i + 1) % ASK_EXAMPLES.length; wait = 300; }
      t = window.setTimeout(tick, wait);
    };
    t = window.setTimeout(tick, 600);
    return () => clearTimeout(t);
  }, [reduce, active]);
  return text;
}

/** The hero's prompt box: the question is handed to the assistant in the user's (or a demo) workspace. */
export function AskBox({ onAsk, busy }: { onAsk: (q: string) => void; busy: boolean }) {
  const [q, setQ] = useState("");
  const [focus, setFocus] = useState(false);
  const typed = useTypedPlaceholder(!q && !focus);
  const submit = () => onAsk(q.trim() || ASK_EXAMPLES[0]);
  return (
    <form className="askbox mt-9 w-full max-w-2xl" onSubmit={(e) => { e.preventDefault(); submit(); }} data-testid="ask-box">
      <label htmlFor="ask" className="sr-only">Ask Nivaaran about a policy or claim</label>
      <textarea id="ask" rows={2} value={q} onChange={(e) => setQ(e.target.value)} maxLength={500}
        onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
        placeholder={focus ? "Ask about a charge, a limit or a clause" : typed}
        className="block w-full resize-none bg-transparent px-5 pt-4 text-[16px] leading-relaxed text-ivory placeholder:text-ivory/40 focus:outline-none" />
      <div className="flex items-center gap-2 px-3 pb-3 pt-1">
        <span className="rounded-[2px] border border-white/12 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-ivory/55">English · हिंदी · मराठी</span>
        <span className="hidden rounded-[2px] border border-white/12 px-2 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-ivory/55 sm:inline">Quotes the exact clause</span>
        <div className="flex-1" />
        <button type="submit" disabled={busy} aria-label="Ask" data-fx-btn
          className="grid size-10 place-items-center rounded-full bg-brass text-forest transition hover:bg-[#c8ad74] disabled:opacity-60">
          {busy ? <span className="size-4 animate-spin rounded-full border-2 border-current border-t-transparent" /> : <ArrowRight className="size-5" />}
        </button>
      </div>
    </form>
  );
}
