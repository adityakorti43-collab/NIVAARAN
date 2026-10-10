import { motion, useInView, useReducedMotion, type Variants } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { inr } from "../lib/format";

export const ease = [0.22, 1, 0.36, 1] as const;

export const stagger: Variants = { hidden: {}, show: { transition: { staggerChildren: 0.06, delayChildren: 0.04 } } };
export const rise: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: { opacity: 1, y: 0, transition: { duration: 0.55, ease } },
};

/** Fades/rises children into view once. Disabled under reduced motion. */
export function Reveal({ children, className, delay = 0, y = 18 }: { children: ReactNode; className?: string; delay?: number; y?: number }) {
  const reduce = useReducedMotion();
  return (
    <motion.div className={className} initial={reduce ? false : { opacity: 0, y }} whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }} transition={{ duration: 0.7, ease, delay }}>
      {children}
    </motion.div>
  );
}

export function Stagger({ children, className }: { children: ReactNode; className?: string }) {
  return <motion.div className={className} variants={stagger} initial="hidden" animate="show">{children}</motion.div>;
}
export function StaggerItem({ children, className }: { children: ReactNode; className?: string }) {
  return <motion.div className={className} variants={rise}>{children}</motion.div>;
}

/**
 * Money value from the rules engine. The text is always the exact decimal string returned by the engine
 * (formatted, never recomputed or interpolated), so no intermediate amount is ever shown. Motion is limited to
 * a reveal on first view and a brief highlight when the engine actually returns a different value.
 */
export function MoneyTicker({ value, className }: { value: string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const reduce = useReducedMotion();
  const prev = useRef(value);
  const [changed, setChanged] = useState(0);
  useEffect(() => {
    if (prev.current !== value) { prev.current = value; setChanged((n) => n + 1); }
  }, [value]);
  return (
    <span ref={ref} className={className}>
      <motion.span key={changed} className="inline-block rounded-[0.15em]"
        initial={reduce ? false : changed ? { backgroundColor: "rgba(182,154,98,0.25)" } : { opacity: 0, filter: "blur(6px)" }}
        animate={inView || reduce ? { opacity: 1, filter: "blur(0px)", backgroundColor: "rgba(182,154,98,0)" } : undefined}
        transition={{ duration: changed ? 1.2 : 0.6, ease }}>
        {inr(value)}
      </motion.span>
    </span>
  );
}

export function MoneyRange({ low, high }: { low: string; high: string }) {
  if (low === high) return <MoneyTicker value={low} className="num" />;
  return (
    <span className="num">
      <MoneyTicker value={low} /> <span className="font-normal text-faint">–</span> <MoneyTicker value={high} />
    </span>
  );
}
