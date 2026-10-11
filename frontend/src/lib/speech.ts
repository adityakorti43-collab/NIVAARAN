/** Read-aloud via the browser's built-in speech synthesis (no audio leaves the device). */
export type Lang = "en" | "hi";

export const LANG_LABEL: Record<Lang, string> = { en: "English", hi: "हिंदी" };
const LOCALE: Record<Lang, string> = { en: "en-IN", hi: "hi-IN" };

/** Reading speed. Brisk by default; the choice is remembered on this device. */
export const SPEEDS = [1, 1.25, 1.5, 1.75] as const;
const SPEED_KEY = "nivaaran.speechRate";
export function getSpeed(): number {
  try { const v = Number(localStorage.getItem(SPEED_KEY)); return SPEEDS.includes(v as (typeof SPEEDS)[number]) ? v : 1.25; } catch { return 1.25; }
}
export function setSpeed(v: number) { try { localStorage.setItem(SPEED_KEY, String(v)); } catch { /* ignore */ } }

// Each new reading (or a stop) bumps this, so callbacks from a cancelled reading can't clobber the new one.
let generation = 0;

export const speechSupported = () => typeof window !== "undefined" && "speechSynthesis" in window;

/**
 * Pick the most natural-sounding voice the device has. Neural "Natural"/"Online" voices (Microsoft Edge, Windows 11),
 * Apple's enhanced/premium voices and Google's voices sound close to a phone assistant; the old built-in desktop
 * voices sound robotic, so they are only used when nothing better is installed.
 */
function score(v: SpeechSynthesisVoice, lang: Lang): number {
  const n = v.name.toLowerCase();
  let s = 0;
  if (/natural|neural|premium|enhanced|siri/.test(n)) s += 6;
  else if (/online/.test(n)) s += 5;
  if (/google/.test(n)) s += 4;
  if (!v.localService) s += 1;
  if (v.lang.toLowerCase().replace("_", "-") === LOCALE[lang].toLowerCase()) s += 2;   // Indian English / Hindi accent
  if (/neerja|swara|aria|jenny|ava|samantha|heera|kalpana|female/.test(n)) s += 1;      // a warm assistant-style voice
  return s;
}

function pickVoice(lang: Lang): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith(lang));
  return voices.sort((a, b) => score(b, lang) - score(a, lang))[0];
}

/** True when a voice for this language is installed. */
export function hasVoice(lang: Lang): boolean {
  if (!speechSupported()) return false;
  return window.speechSynthesis.getVoices().some((v) => v.lang.toLowerCase().startsWith(lang));
}

/** A hint when the device's voices will sound poor, or when there is no Hindi voice at all. */
export function voiceNote(lang: Lang): string | null {
  if (!speechSupported() || !window.speechSynthesis.getVoices().length) return null;
  if (lang === "hi" && !hasVoice("hi")) return "No Hindi voice is installed on this device, so it may be read with another voice. Add Hindi in your system's speech settings, or open Nivaaran in Microsoft Edge, which has natural Hindi voices built in.";
  const v = pickVoice(lang);
  if (v && score(v, lang) < 4) return "Your browser only has basic voices. For a smoother, more natural voice, open Nivaaran in Microsoft Edge or Chrome.";
  return null;
}

/** Make text sound right when spoken: "₹10,000.00" → "10,000 rupees", no bullets or symbols read out. */
function forSpeech(text: string, lang: Lang): string {
  const rupees = lang === "hi" ? "रुपये" : "rupees";
  return text
    .replace(/(?:₹|INR|Rs\.?)\s?(\d[\d,]*)(?:\.00)?(?:\.(\d{1,2}))?/g, (_m, n: string, p?: string) => `${n}${p ? `.${p}` : ""} ${rupees}`)
    .replace(/(\d)\.00\b/g, "$1")
    .replace(/^\s*[-•*·]\s+/gm, "")
    .replace(/[*_#`>]/g, "")
    .replace(/\s*\n+\s*/g, ". ")
    .replace(/\.\s*\./g, ".")
    .replace(/\s+/g, " ")
    .trim();
}

/** Strip on-screen references ("(clause 4.1)", "[2]") from an answer before it is spoken. */
export function conversational(text: string): string {
  return text.replace(/\s*\((?:clause|cl\.|section|धारा|see)[^)]*\)/gi, "").replace(/\s*\[[^\]]*\]/g, "");
}

/**
 * Sentence-sized pieces, merged up to ~220 characters. Fewer, longer pieces mean fewer pauses (so it flows), while
 * staying under the length at which some engines stop mid-sentence. Never split inside an amount like "10,000.50".
 */
function chunks(t: string): string[] {
  const parts = t.split(/(?<=[।!?;]|\.(?!\d))\s+/).filter((x) => x.trim());
  const out: string[] = [];
  for (const p of parts) {
    if (out.length && out[out.length - 1].length + p.length < 220) out[out.length - 1] += " " + p;
    else out.push(p);
  }
  return out;
}

function utter(text: string, lang: Lang, voice: SpeechSynthesisVoice | undefined, rate: number) {
  const u = new SpeechSynthesisUtterance(text);
  u.lang = voice?.lang ?? LOCALE[lang];
  if (voice) u.voice = voice;
  u.rate = rate;
  u.pitch = 1;
  return u;
}

// ---- Natural (neural) voice from the server, when the operator has configured one (Azure AI Speech).
let neuralCheck: Promise<boolean> | null = null;
function neuralAvailable(): Promise<boolean> {
  neuralCheck ??= fetch("/api/speech", { credentials: "same-origin" })
    .then((r) => (r.ok ? r.json() : { neural: false })).then((j) => !!j.neural).catch(() => false);
  return neuralCheck;
}
const audioUrls = new Map<string, Promise<string>>();
function neuralAudio(text: string, lang: Lang): Promise<string> {
  const k = `${lang}|${text}`;
  let p = audioUrls.get(k);
  if (!p) {
    p = fetch("/api/speech", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, lang }) })
      .then((r) => { if (!r.ok) throw new Error(`voice ${r.status}`); return r.blob(); })
      .then((b) => URL.createObjectURL(b));
    p.catch(() => audioUrls.delete(k));
    audioUrls.set(k, p);
  }
  return p;
}
/** Start generating the audio early (e.g. when a summary loads) so pressing play starts instantly. */
export function prefetchSpeech(text: string, lang: Lang) {
  // Only the opening piece, so pressing play starts at once without spending quota on audio nobody plays.
  void neuralAvailable().then((ok) => { const first = pieces(forSpeech(text, lang))[0]; if (ok && first) neuralAudio(first, lang).catch(() => {}); });
}
/** Whether the neural voice is in use (so the page can skip "install a voice" hints). */
export const usingNeuralVoice = () => neuralAvailable();
let audio: HTMLAudioElement | null = null;

function browserSpeak(text: string, lang: Lang, done: () => void, rate: number) {
  if (!speechSupported()) { done(); return; }
  const voice = pickVoice(lang);
  const parts = chunks(text);
  parts.forEach((p, i) => {
    const u = utter(p, lang, voice, rate);
    if (i === parts.length - 1) { u.onend = done; u.onerror = done; }
    window.speechSynthesis.speak(u);
  });
}

/** Speak `text` smoothly: the server's neural voice when available (same quality for Hindi and English), otherwise
 *  the most natural voice the browser has. */
/**
 * Pieces for the natural voice: a short first piece so speech starts within seconds, then ~400-character pieces that
 * are generated in the background while the earlier ones play. Each piece is cached on the server.
 */
function pieces(text: string): string[] {
  const out: string[] = [];
  for (const sent of text.split(/(?<=[।!?;]|\.(?!\d))\s+/).filter((x) => x.trim())) {
    const limit = out.length <= 1 ? 160 : 400;
    if (out.length && out[out.length - 1].length + sent.length < limit) out[out.length - 1] += " " + sent;
    else out.push(sent);
  }
  return out;
}

export function speak(text: string, lang: Lang, onEnd?: () => void, rate = getSpeed()): boolean {
  stopSpeaking();
  const mine = generation;
  const done = () => { if (mine === generation) onEnd?.(); };
  const clean = forSpeech(text, lang);
  void neuralAvailable().then(async (ok) => {
    if (mine !== generation) return;
    if (!ok) { browserSpeak(clean, lang, done, rate); return; }
    const parts = pieces(clean);
    // Generate one piece after another (gentle on the free quota), starting now; playback follows behind.
    const urls: Promise<string>[] = [];
    parts.reduce<Promise<unknown>>((prev, part, i) => { const u = prev.then(() => neuralAudio(part, lang)); urls[i] = u; return u.catch(() => {}); }, Promise.resolve());
    for (let i = 0; i < parts.length; i++) {
      let url: string;
      try { url = await urls[i]; } catch { if (mine === generation) browserSpeak(parts.slice(i).join(" "), lang, done, rate); return; }
      if (mine !== generation) return;
      const ended = await new Promise<boolean>((resolve) => {
        audio = new Audio(url);
        audio.playbackRate = rate * 0.9;          // the natural voice is already brisk; 1.25× in the menu ≈ 1.1× here
        audio.onended = () => resolve(true);
        audio.onerror = () => resolve(false);
        audio.play().catch(() => resolve(false));
      });
      if (mine !== generation) return;
      if (!ended) { browserSpeak(parts.slice(i).join(" "), lang, done, rate); return; }
    }
    done();
  });
  return true;
}

/** Speak a list of passages in order, reporting which one is being read (for following along on screen). */
export function speakSequence(passages: string[], lang: Lang, onIndex: (i: number) => void, onEnd: () => void): void {
  if (!speechSupported() || !passages.length) { onEnd(); return; }
  window.speechSynthesis.cancel();
  const voice = pickVoice(lang);
  const mine = ++generation;
  const next = (i: number) => {
    if (mine !== generation) return;
    if (i >= passages.length) { onEnd(); return; }
    onIndex(i);
    const parts = chunks(forSpeech(passages[i], lang));
    parts.forEach((c, k) => {
      const u = utter(c, lang, voice, getSpeed());
      if (k === parts.length - 1) { u.onend = () => next(i + 1); u.onerror = () => { if (mine === generation) { generation++; onEnd(); } }; }
      window.speechSynthesis.speak(u);
    });
  };
  next(0);
}

export function stopSpeaking() {
  generation++;
  if (audio) { audio.pause(); audio.onended = audio.onerror = null; audio = null; }
  if (speechSupported()) window.speechSynthesis.cancel();
}

// Voices load asynchronously in Chrome; ask early so the best voice is ready by the first click.
if (speechSupported()) window.speechSynthesis.getVoices();
