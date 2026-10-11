/**
 * Site-wide translation. The app is written in English; when another language is chosen, every visible piece of text
 * (including policy summaries and assistant answers) is sent to the server, translated once with Azure AI Translator,
 * cached, and swapped into the page. New text that appears later (navigation, answers) is translated as it arrives.
 *
 * Only text is replaced, never elements, so React keeps working normally. Text inside inputs, code, and anything
 * marked translate="no" (amounts, clause numbers) is left as it is.
 */
export interface Language { code: string; name: string; native: string; rtl: boolean }

const KEY = "nivaaran.lang";
const SKIP = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "TEXTAREA", "INPUT", "CODE", "KBD", "SVG", "OPTION", "SELECT"]);
// Letters plus combining marks: Indian scripts write vowels as marks (e.g. Bengali "হিসাব"), so \p{L} alone misses them.
const HAS_WORD = /[\p{L}\p{M}]{2,}/u;
const ATTRS = ["placeholder", "title", "aria-label"] as const;

let lang = "en";
const memo = new Map<string, string>();               // `${lang}|${text}` → translation
const originals = new WeakMap<Text, string>();        // text node → its English text
const mine = new WeakMap<Text, string>();             // text node → the translation we wrote (to ignore our own edits)
const attrOrig = new WeakMap<Element, Record<string, string>>();
let queue = new Set<string>();
let timer: number | null = null;
let failures = 0;
let observer: MutationObserver | null = null;
const listeners = new Set<(s: { lang: string; busy: boolean; error: string | null }) => void>();
let state = { lang: "en", busy: false, error: null as string | null };
const emit = (p: Partial<typeof state>) => { state = { ...state, ...p }; listeners.forEach((f) => f(state)); };

export const subscribe = (f: (s: typeof state) => void) => { listeners.add(f); f(state); return () => { listeners.delete(f); }; };
export const currentLang = () => lang;
export function savedLang(): string { try { return localStorage.getItem(KEY) || "en"; } catch { return "en"; } }

function skip(el: Element | null): boolean {
  for (let e = el; e; e = e.parentElement) {
    if (SKIP.has(e.tagName) || e.getAttribute("translate") === "no" || e.classList.contains("notranslate") || (e as HTMLElement).isContentEditable) return true;
  }
  return false;
}

function split(s: string): [string, string, string] {
  const m = s.match(/^(\s*)([\s\S]*?)(\s*)$/)!;
  return [m[1], m[2], m[3]];
}

function textNodes(root: Node): Text[] {
  const out: Text[] = [];
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    const t = n as Text;
    // Anything we changed is always revisited (so switching back restores it), plus any text with words in it.
    if (originals.has(t) || (t.nodeValue && HAS_WORD.test(t.nodeValue) && !skip(t.parentElement))) out.push(t);
  }
  return out;
}

function apply(t: Text) {
  const orig = originals.get(t) ?? t.nodeValue ?? "";
  originals.set(t, orig);
  const [a, core, b] = split(orig);
  if (lang === "en") { if (t.nodeValue !== orig) { mine.set(t, orig); t.nodeValue = orig; } return; }
  const tr = memo.get(`${lang}|${core}`);
  if (tr === undefined) { queue.add(core); schedule(); return; }
  const next = a + tr + b;
  if (t.nodeValue !== next) { mine.set(t, next); t.nodeValue = next; }
}

function applyAttrs(el: Element) {
  if (el.closest(`[translate="no"], .notranslate`)) return;   // placeholders on inputs are still translated
  let rec = attrOrig.get(el);
  if (!rec) { rec = {}; attrOrig.set(el, rec); }
  for (const name of ATTRS) {
    const v = el.getAttribute(name);
    if (!v || !HAS_WORD.test(v)) continue;
    if (rec[`w:${name}`] !== v) rec[name] = v;                 // not our own write: this is the (new) English value
    const orig = rec[name];
    const target = lang === "en" ? orig : memo.get(`${lang}|${orig}`);
    if (target === undefined) { queue.add(orig); schedule(); continue; }
    if (v !== target) { rec[`w:${name}`] = target; el.setAttribute(name, target); }
  }
}

function sweep(root: Node = document.body) {
  textNodes(root).forEach(apply);
  if (root instanceof Element || root === document.body) {
    const scope = root as Element;
    scope.querySelectorAll?.("[placeholder],[title],[aria-label]").forEach(applyAttrs);
  }
}

function schedule() {
  if (timer !== null) return;
  timer = window.setTimeout(flush, 120);
}

async function flush() {
  timer = null;
  const target = lang;
  const batch = [...queue].filter((s) => !memo.has(`${target}|${s}`)).slice(0, 40);   // small batches: the page fills in progressively
  queue = new Set([...queue].filter((s) => !batch.includes(s)));
  if (!batch.length || target === "en") return;
  emit({ busy: true });
  try {
    const r = await fetch("/api/translate", { method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lang: target, texts: batch }) });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.detail || body.message || `Translation failed (${r.status})`);
    (body.translations as string[]).forEach((tr, i) => memo.set(`${target}|${batch[i]}`, tr));
    persist(target);
    if (lang === target) sweep();
    emit({ error: null });
    failures = 0;
  } catch (e) {
    emit({ error: (e as Error).message });
    if ((e as Error).message.includes("isn't set up")) { setLanguage("en"); return; }
    // A busy or slow service: put the batch back and try again shortly (up to 4 times in a row).
    if (++failures <= 4 && lang === target) { batch.forEach((x) => queue.add(x)); window.setTimeout(schedule, 4000 * failures); }
    return;
  } finally {
    emit({ busy: queue.size > 0 });
  }
  if (queue.size) schedule();
}

function persist(l: string) {
  try {
    const entries = [...memo].filter(([k]) => k.startsWith(`${l}|`)).slice(-4000);
    localStorage.setItem(`nivaaran.tr.${l}`, JSON.stringify(entries));
  } catch { /* storage full or blocked: the server cache still works */ }
}
function restore(l: string) {
  try { (JSON.parse(localStorage.getItem(`nivaaran.tr.${l}`) || "[]") as [string, string][]).forEach(([k, v]) => memo.set(k, v)); } catch { /* ignore */ }
}

function watch() {
  if (observer) return;
  observer = new MutationObserver((muts) => {
    for (const m of muts) {
      if (m.type === "characterData") {
        const t = m.target as Text;
        if (mine.get(t) === t.nodeValue) continue;              // our own write
        originals.set(t, t.nodeValue ?? "");                     // React changed the English text
        if (HAS_WORD.test(t.nodeValue ?? "") && !skip(t.parentElement)) apply(t);
      } else if (m.type === "childList") {
        m.addedNodes.forEach((n) => {
          if (n.nodeType === Node.TEXT_NODE) { const t = n as Text; originals.delete(t); if (HAS_WORD.test(t.nodeValue ?? "") && !skip(t.parentElement)) apply(t); }
          else if (n.nodeType === Node.ELEMENT_NODE) sweep(n);
        });
      } else if (m.type === "attributes" && m.target instanceof Element) {
        applyAttrs(m.target);
      }
    }
  });
  observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: [...ATTRS] });
}

export function setLanguage(code: string, rtl = false) {
  lang = code;
  try { localStorage.setItem(KEY, code); } catch { /* ignore */ }
  document.documentElement.lang = code === "en" ? "en" : code;
  document.documentElement.dataset.textDir = rtl ? "rtl" : "ltr";
  emit({ lang: code, error: null });
  if (code !== "en") { restore(code); watch(); }
  sweep();
}

/** Start in the language chosen on a previous visit. */
export function initLanguage(langs?: Language[]) {
  const l = savedLang();
  if (l !== "en") setLanguage(l, !!langs?.find((x) => x.code === l)?.rtl);
}
