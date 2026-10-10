/**
 * Global interaction effects, installed once via event delegation so every button and card in the app gets them:
 *  - buttons: magnetic pull + 3D tilt toward the pointer, a light sheen that follows it, and a click ripple
 *  - cards:   gentle 3D tilt and a pointer spotlight
 * Disabled under prefers-reduced-motion and on touch-only devices. Pure transforms, no layout work.
 */
const BTN = "button.btn, button.btn-primary, button.btn-secondary, a.btn, a.btn-primary, a.btn-secondary, [data-fx-btn]";
const CARD = ".card, .card-raised";

export function installFx() {
  if (typeof window === "undefined") return;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  const fine = window.matchMedia("(pointer: fine)");
  let active: HTMLElement | null = null;
  let card: HTMLElement | null = null;

  const reset = (el: HTMLElement | null) => { if (el) { el.style.transform = ""; el.removeAttribute("data-fx-on"); } };

  window.addEventListener("pointermove", (e) => {
    if (reduce.matches || !fine.matches) return;
    const t = e.target as Element | null;
    const btn = t?.closest?.(BTN) as HTMLElement | null;
    if (btn !== active) { reset(active); active = btn; }
    if (btn && !(btn as HTMLButtonElement).disabled) {
      const r = btn.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
      btn.setAttribute("data-fx-on", "");
      btn.style.setProperty("--fx-x", `${x * 100}%`);
      btn.style.setProperty("--fx-y", `${y * 100}%`);
      btn.style.transform = `perspective(500px) translate(${(x - 0.5) * 6}px, ${(y - 0.5) * 5}px) rotateX(${(0.5 - y) * 14}deg) rotateY(${(x - 0.5) * 16}deg) translateZ(6px)`;
    }
    const c = btn ? null : (t?.closest?.(CARD) as HTMLElement | null);
    if (c !== card) { reset(card); card = c; }
    if (c && c.getBoundingClientRect().height < 700) {
      const r = c.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
      c.setAttribute("data-fx-on", "");
      c.style.setProperty("--fx-x", `${x * 100}%`);
      c.style.setProperty("--fx-y", `${y * 100}%`);
      c.style.transform = `perspective(1200px) rotateX(${(0.5 - y) * 3}deg) rotateY(${(x - 0.5) * 4}deg)`;
    }
  }, { passive: true });

  window.addEventListener("pointerleave", () => { reset(active); reset(card); active = card = null; });

  window.addEventListener("pointerdown", (e) => {
    if (reduce.matches) return;
    const btn = (e.target as Element | null)?.closest?.(BTN) as HTMLElement | null;
    if (!btn || (btn as HTMLButtonElement).disabled) return;
    const r = btn.getBoundingClientRect();
    const s = document.createElement("span");
    s.className = "fx-ripple";
    const size = Math.max(r.width, r.height) * 2;
    s.style.cssText = `width:${size}px;height:${size}px;left:${e.clientX - r.left - size / 2}px;top:${e.clientY - r.top - size / 2}px`;
    btn.appendChild(s);
    setTimeout(() => s.remove(), 650);
  });
}
