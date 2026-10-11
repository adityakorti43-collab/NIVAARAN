import { Volume2 } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

export const INTRO_KEY = "nivaaran.introSeen.v2";
const INTRO_SRC = "/intro.mp4";

// Plays once per page load: every time the site is opened (or reloaded), but not when navigating back to the
// landing page from inside the app.
let playedThisLoad = false;

export function replayIntro() {
  window.location.assign("/");
}

/**
 * Opening video (public/intro.mp4). Shown every time the site is opened; skippable at any time (button, Esc or Enter);
 * never shown under reduced motion or with ?nointro. Browsers may block autoplay with sound, in which case the video
 * plays muted and a "Sound on" button appears.
 */
export function CinematicIntro() {
  const reduce = useReducedMotion();
  const [show, setShow] = useState(() => !playedThisLoad && !reduce && !/[?&]nointro\b/.test(window.location.search));
  const [muted, setMuted] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const done = () => { playedThisLoad = true; setShow(false); video.current?.pause(); };

  useEffect(() => {
    if (!show) return;
    const v = video.current;
    if (v) {
      v.muted = false;
      v.play().catch(() => { v.muted = true; setMuted(true); v.play().catch(() => done()); });
    }
    const safety = setTimeout(done, 20000);   // never trap visitors if the video stalls
    const k = (e: KeyboardEvent) => (e.key === "Escape" || e.key === "Enter") && done();
    window.addEventListener("keydown", k);
    return () => { clearTimeout(safety); window.removeEventListener("keydown", k); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [show]);

  return (
    <AnimatePresence>
      {show && (
        <motion.div key="intro" className="fixed inset-0 z-[90] overflow-hidden bg-black" role="dialog" aria-label="Nivaaran introduction"
          exit={{ opacity: 0 }} transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}>
          <video ref={video} src={INTRO_SRC} className="absolute inset-0 h-full w-full object-contain" playsInline preload="auto"
            onEnded={done} onError={done} aria-label="Nivaaran introduction video" data-testid="intro-video" />
          <div className="absolute right-5 top-5 flex items-center gap-2">
            {muted && (
              <button onClick={() => { const v = video.current; if (v) { v.muted = false; setMuted(false); } }}
                className="inline-flex items-center gap-1.5 rounded-full border border-white/20 bg-black/30 px-4 py-2 text-[13px] text-white/85 backdrop-blur transition-colors hover:border-brass hover:text-brass">
                <Volume2 className="size-4" /> Sound on
              </button>
            )}
            <button onClick={done} className="rounded-full border border-white/20 bg-black/30 px-4 py-2 text-[13px] text-white/85 backdrop-blur transition-colors hover:border-brass hover:text-brass" data-testid="skip-intro">
              Skip intro
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
