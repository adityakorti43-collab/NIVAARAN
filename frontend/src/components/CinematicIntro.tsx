import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { webglAvailable } from "./HeroFallback";

const OfficeScene = lazy(() => import("./OfficeScene"));
export const INTRO_KEY = "nivaaran.introSeen.v2";

// Plays once per page load: every time the site is opened (or reloaded), but not when navigating back to the
// landing page from inside the app.
let playedThisLoad = false;

export function replayIntro() {
  window.location.assign("/");
}

/**
 * Cinematic opening: the insurance office emerges from darkness, the camera moves in, the policy is scanned,
 * evidence links form, a discrepancy is marked amber, and the brand appears. Shown every time the site is opened;
 * skippable at any time; never shown under reduced motion or with ?nointro; text-only without WebGL.
 */
export function CinematicIntro() {
  const reduce = useReducedMotion();
  const gl = useMemo(() => webglAvailable(), []);
  const [show, setShow] = useState(() => !playedThisLoad && !reduce && !/[?&]nointro\b/.test(window.location.search));
  const done = () => { playedThisLoad = true; setShow(false); };
  useEffect(() => {
    if (!show) return;
    const t = setTimeout(done, gl ? 6800 : 2400);
    const k = (e: KeyboardEvent) => (e.key === "Escape" || e.key === "Enter") && done();
    window.addEventListener("keydown", k);
    return () => { clearTimeout(t); window.removeEventListener("keydown", k); };
  }, [show, gl]);
  const brandAt = gl ? 4.8 : 0.2;
  return (
    <AnimatePresence>
      {show && (
        <motion.div key="intro" className="fixed inset-0 z-[90] overflow-hidden bg-[#0b1714]" role="dialog" aria-label="Nivaaran introduction"
          exit={{ opacity: 0, filter: "blur(10px)", scale: 1.03 }} transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}>
          {gl && <div className="absolute inset-0"><Suspense fallback={null}><OfficeScene mode="intro" /></Suspense></div>}
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_40%,rgba(5,12,10,0.85))]" aria-hidden />
          {gl && (
            <div className="pointer-events-none absolute left-6 top-6 space-y-1 font-mono text-[11px] text-sage/80 md:left-10 md:top-10" aria-hidden>
              {["Reading policy wording", "Resolving applicable version", "Tracing evidence", "Checking for discrepancies"].map((s, i) => (
                <motion.p key={s} initial={{ opacity: 0, x: -6 }} animate={{ opacity: [0, 1, 1, 0.45] }} transition={{ delay: 1.6 + i * 0.85, duration: 1.4, times: [0, 0.2, 0.8, 1] }}>▸ {s}</motion.p>
              ))}
            </div>
          )}
          <div className="pointer-events-none absolute inset-x-0 bottom-[12vh] flex flex-col items-center px-6 text-center">
            <motion.h1 className="font-display text-[17vw] leading-none tracking-[-0.02em] text-ivory sm:text-[9vw] lg:text-[7vw]"
              initial={{ opacity: 0, y: 30, filter: "blur(12px)" }} animate={{ opacity: 1, y: 0, filter: "blur(0px)" }} transition={{ delay: brandAt, duration: 0.9, ease: [0.22, 1, 0.36, 1] }}>
              Nivaaran
            </motion.h1>
            <motion.p className="mt-3 font-display text-[19px] italic text-brass md:text-[24px]" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: brandAt + 0.6, duration: 0.8 }}>
              Insurance clarity. Backed by evidence.
            </motion.p>
          </div>
          <button onClick={done} className="absolute right-5 top-5 rounded-full border border-white/20 bg-black/30 px-4 py-2 text-[13px] text-white/85 backdrop-blur transition-colors hover:border-brass hover:text-brass" data-testid="skip-intro">
            Skip intro
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
