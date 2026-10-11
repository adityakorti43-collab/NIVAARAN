import { useEffect, useRef } from "react";

/**
 * A slowly rotating 3D "evidence network" behind the workspace: points in 3D space, perspective-projected onto a
 * 2D canvas, with links drawn between near neighbours and a few pulses travelling along them. It drifts toward
 * the pointer for parallax. Cheap (2D canvas, ~70 points, throttled when the tab is hidden); off for reduced motion.
 */
export function AmbientField() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current!;
    const ctx = canvas.getContext("2d")!;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const N = 70;
    const rnd = (s: number) => Math.abs(Math.sin(s) * 43758.5453) % 1;   // deterministic 0..1
    const pts = Array.from({ length: N }, (_, i) => ({ x: rnd(i * 12.9898) * 2 - 1, y: rnd(i * 78.233) * 2 - 1, z: rnd(i * 39.425) * 2 - 1 }));
    let w = 0, h = 0, raf = 0, t = 0, px = 0, py = 0;
    const resize = () => { const d = Math.min(devicePixelRatio, 1.5); w = canvas.clientWidth; h = canvas.clientHeight; canvas.width = w * d; canvas.height = h * d; ctx.setTransform(d, 0, 0, d, 0, 0); };
    const onMove = (e: PointerEvent) => { px = e.clientX / innerWidth - 0.5; py = e.clientY / innerHeight - 0.5; };
    resize(); addEventListener("resize", resize); addEventListener("pointermove", onMove, { passive: true });
    const frame = () => {
      t += 0.0016;
      ctx.clearRect(0, 0, w, h);
      const ay = t + px * 0.6, ax = 0.35 + py * 0.4;
      const proj = pts.map((p) => {
        const x1 = p.x * Math.cos(ay) - p.z * Math.sin(ay), z1 = p.x * Math.sin(ay) + p.z * Math.cos(ay);
        const y1 = p.y * Math.cos(ax) - z1 * Math.sin(ax), z2 = p.y * Math.sin(ax) + z1 * Math.cos(ax);
        const s = 1.8 / (2.6 + z2);
        return { x: w * 0.5 + x1 * s * w * 0.55, y: h * 0.5 + y1 * s * h * 0.6, s, z: z2 };
      });
      for (let i = 0; i < N; i++) for (let j = i + 1; j < N; j++) {
        const a = proj[i], b = proj[j];
        const d = Math.hypot(a.x - b.x, a.y - b.y);
        if (d < 140) {
          ctx.strokeStyle = `rgba(182,154,98,${(1 - d / 140) * 0.3 * Math.min(a.s, b.s)})`;
          ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
          if ((i * 7 + j) % 41 === 0) {               // a few evidence pulses moving along links
            const k = (t * 40 + i) % 1;
            ctx.fillStyle = "rgba(182,154,98,0.85)"; ctx.beginPath(); ctx.arc(a.x + (b.x - a.x) * k, a.y + (b.y - a.y) * k, 1.6, 0, 6.3); ctx.fill();
          }
        }
      }
      for (const p of proj) { ctx.fillStyle = `rgba(20,45,39,${0.08 + p.s * 0.16})`; ctx.beginPath(); ctx.arc(p.x, p.y, 1.2 + p.s * 1.4, 0, 6.3); ctx.fill(); }
      raf = document.hidden ? window.setTimeout(() => requestAnimationFrame(frame), 500) as unknown as number : requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => { cancelAnimationFrame(raf); removeEventListener("resize", resize); removeEventListener("pointermove", onMove); };
  }, []);
  return <canvas ref={ref} className="pointer-events-none fixed inset-0 z-0 h-full w-full opacity-70" aria-hidden />;
}
