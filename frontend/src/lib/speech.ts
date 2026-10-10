/** Read-aloud via the browser's built-in speech synthesis (no audio leaves the device). */
export type Lang = "en" | "hi" | "mr";

export const LANG_LABEL: Record<Lang, string> = { en: "English", hi: "हिंदी", mr: "मराठी" };
const LOCALE: Record<Lang, string> = { en: "en-IN", hi: "hi-IN", mr: "mr-IN" };
// Marathi is written in Devanagari, so a Hindi voice is the closest fallback when no Marathi voice is installed.
const PREFERRED: Record<Lang, string[]> = { en: ["en-IN", "en-GB", "en-US", "en"], hi: ["hi-IN", "hi"], mr: ["mr-IN", "mr", "hi-IN", "hi"] };

export const speechSupported = () => typeof window !== "undefined" && "speechSynthesis" in window;

function pickVoice(lang: Lang): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis.getVoices();
  for (const w of PREFERRED[lang]) {
    const v = voices.find((x) => x.lang.toLowerCase().startsWith(w.toLowerCase()));
    if (v) return v;
  }
  return undefined;
}

/** True only when a voice for exactly this language is installed (not a fallback). */
export function hasVoice(lang: Lang): boolean {
  if (!speechSupported()) return false;
  const prefix = LOCALE[lang].slice(0, 2);
  return window.speechSynthesis.getVoices().some((v) => v.lang.toLowerCase().startsWith(prefix));
}

export function voiceNote(lang: Lang): string | null {
  if (lang === "en" || hasVoice(lang)) return null;
  if (lang === "mr") return hasVoice("hi")
    ? "No Marathi voice is installed on this device, so a Hindi voice is reading the Marathi text. Install a Marathi voice in your system's speech settings for the best result."
    : "No Marathi or Hindi voice is installed on this device; another voice may read it. Install a Marathi voice in your system's speech settings.";
  return "No Hindi voice is installed on this device; it may be read with a different voice. Install a Hindi voice in your system's speech settings for best results.";
}

/** Speak `text`; long texts are queued in sentence-sized chunks (some engines stop after ~15 seconds otherwise). */
export function speak(text: string, lang: Lang, onEnd?: () => void): boolean {
  if (!speechSupported()) return false;
  window.speechSynthesis.cancel();
  const parts = text.replace(/\s+/g, " ").match(/[^.।!?]+[.।!?]?/g) ?? [text];
  const voice = pickVoice(lang);
  parts.forEach((p, i) => {
    const u = new SpeechSynthesisUtterance(p.trim());
    u.lang = voice?.lang ?? LOCALE[lang];
    if (voice) u.voice = voice;
    u.rate = lang === "en" ? 1 : 0.95;
    if (i === parts.length - 1 && onEnd) { u.onend = onEnd; u.onerror = onEnd; }
    window.speechSynthesis.speak(u);
  });
  return true;
}

/** Speak a list of passages in order, reporting which one is being read (for following along on screen). */
export function speakSequence(passages: string[], lang: Lang, onIndex: (i: number) => void, onEnd: () => void): void {
  if (!speechSupported() || !passages.length) { onEnd(); return; }
  window.speechSynthesis.cancel();
  const voice = pickVoice(lang);
  let cancelled = false;
  const next = (i: number) => {
    if (cancelled) return;
    if (i >= passages.length) { onEnd(); return; }
    onIndex(i);
    const chunks = passages[i].replace(/\s+/g, " ").match(/[^.।!?]+[.।!?]?/g) ?? [passages[i]];
    chunks.forEach((c, k) => {
      const u = new SpeechSynthesisUtterance(c.trim());
      u.lang = voice?.lang ?? LOCALE[lang];
      if (voice) u.voice = voice;
      if (k === chunks.length - 1) { u.onend = () => next(i + 1); u.onerror = () => { cancelled = true; onEnd(); }; }
      window.speechSynthesis.speak(u);
    });
  };
  next(0);
}

export function stopSpeaking() {
  if (speechSupported()) window.speechSynthesis.cancel();
}
