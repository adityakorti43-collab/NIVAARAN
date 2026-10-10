import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cn } from "../lib/format";

/** Accessible modal: portal, Esc to close, focus moved in and restored, scroll locked, spring transition. */
export function Modal({ open, onClose, title, subtitle, children, size = "lg", footer }: {
  open: boolean; onClose: () => void; title: ReactNode; subtitle?: ReactNode; children: ReactNode; size?: "md" | "lg" | "xl"; footer?: ReactNode;
}) {
  const panel = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEffect(() => {
    if (!open) return;
    const prevFocus = document.activeElement as HTMLElement | null;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const t = setTimeout(() => panel.current?.focus(), 30);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && panel.current) {
        const f = panel.current.querySelectorAll<HTMLElement>('a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])');
        if (!f.length) return;
        const first = f[0], last = f[f.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => { clearTimeout(t); window.removeEventListener("keydown", onKey); document.body.style.overflow = prevOverflow; prevFocus?.focus?.(); };
  }, [open, onClose]);
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-[60] flex items-end justify-center p-0 sm:items-center sm:p-6" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-forest/45 backdrop-blur-sm" onClick={onClose} aria-hidden />
          <motion.div ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
            initial={{ opacity: 0, y: 24, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 380, damping: 32 }}
            className={cn("card-raised relative flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-b-none outline-none sm:rounded-2xl",
              size === "md" ? "sm:max-w-lg" : size === "lg" ? "sm:max-w-3xl" : "sm:max-w-5xl")}>
            <div className="flex items-start gap-3 border-b border-line px-5 py-4">
              <div className="min-w-0 flex-1">
                <h2 id={titleId} className="text-base font-semibold text-ink">{title}</h2>
                {subtitle && <div className="mt-0.5 text-xs text-muted">{subtitle}</div>}
              </div>
              <button onClick={onClose} className="btn-ghost -mr-2 -mt-1 p-2" aria-label="Close dialog"><X className="size-4" /></button>
            </div>
            <div className="overflow-y-auto px-5 py-4">{children}</div>
            {footer && <div className="border-t border-line px-5 py-3">{footer}</div>}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

/** Hover/focus tooltip for short contextual explanations. */
export function Tip({ content, children, className }: { content: ReactNode; children: ReactNode; className?: string }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <span className={cn("relative inline-flex", className)} onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}>
      <span aria-describedby={open ? id : undefined} className="inline-flex">{children}</span>
      <AnimatePresence>
        {open && (
          <motion.span role="tooltip" id={id} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 4 }} transition={{ duration: 0.14 }}
            className="pointer-events-none absolute bottom-[calc(100%+8px)] left-1/2 z-50 w-max max-w-[260px] -translate-x-1/2 rounded-lg border border-forest bg-forest px-2.5 py-1.5 text-xs font-normal normal-case tracking-normal text-ivory shadow-xl">
            {content}
          </motion.span>
        )}
      </AnimatePresence>
    </span>
  );
}
