import { Canvas, useFrame, useThree } from "@react-three/fiber";
import type { MotionValue } from "motion/react";
import { useMemo, useRef } from "react";
import * as THREE from "three";

/*
 * Signature scene: a long hospital receipt — the thing every claim starts with — curls and twists in space
 * under real lighting. It is printed with the synthetic demo bill and the verdict Nivaaran reaches for
 * each line. The paper is a deformable mesh: vertices are bent every frame, normals recomputed, so the
 * light rolls across the folds. No external assets; the print is drawn on a canvas.
 */

const LINES: [string, string, string, string][] = [
  ["Deluxe room x 2", "18,000.00", "PARTIAL", "#3c5e7f"], ["ICU charges", "12,000.00", "PARTIAL", "#3c5e7f"],
  ["Surgeon fee - lap.", "45,000.00", "COVERED", "#2e6b50"], ["Anaesthetist fee", "12,000.00", "COVERED", "#2e6b50"],
  ["OT charges", "18,000.00", "COVERED", "#2e6b50"], ["CBC, LFT, RFT", "3,200.00", "COVERED", "#2e6b50"],
  ["USG abdomen", "2,500.00", "COVERED", "#2e6b50"], ["Inj. ceftriaxone", "2,400.00", "COVERED", "#2e6b50"],
  ["MVI infusion", "1,800.00", "CONDITION", "#946617"], ["Gloves, masks", "3,500.00", "COVERED", "#2e6b50"],
  ["Admission kit", "1,200.00", "EXCLUDED", "#a2463a"], ["Nebulizer kit", "900.00", "CONFLICT", "#7a4e86"],
  ["TV & telephone", "600.00", "EXCLUDED", "#a2463a"], ["Ambulance", "3,000.00", "PARTIAL", "#3c5e7f"],
  ["Dietitian", "800.00", "NO EVIDENCE", "#73786f"], ["Follow-up consult", "1,000.00", "COVERED", "#2e6b50"],
];

function receiptTexture() {
  const W = 600, H = 2400;
  const c = document.createElement("canvas");
  c.width = W; c.height = H;
  const g = c.getContext("2d")!;
  g.fillStyle = "#fffefa"; g.fillRect(0, 0, W, H);
  // faint thermal-paper grain
  for (let i = 0; i < 2600; i++) { g.fillStyle = `rgba(34,37,33,${Math.random() * 0.035})`; g.fillRect(Math.random() * W, Math.random() * H, 1.5, 1.5); }
  const mono = "'IBM Plex Mono', ui-monospace, Consolas, 'Courier New', monospace";
  g.fillStyle = "#222521"; g.textAlign = "center";
  g.font = `700 34px ${mono}`; g.fillText("SYNTHETIC CARE HOSPITAL", W / 2, 120);
  g.font = `400 22px ${mono}`; g.fillStyle = "#6c7068";
  g.fillText("Itemised final bill  ·  synthetic demo", W / 2, 162);
  g.fillText("Admission 12-11-2025", W / 2, 196);
  g.strokeStyle = "#222521"; g.setLineDash([10, 8]); g.lineWidth = 2;
  g.beginPath(); g.moveTo(40, 236); g.lineTo(W - 40, 236); g.stroke();
  g.textAlign = "left";
  let y = 300;
  LINES.forEach(([d, amt, verdict, col], i) => {
    g.fillStyle = "#222521"; g.font = `600 30px ${mono}`;
    g.fillText(`${String(i + 1).padStart(2, "0")} ${d}`, 44, y);
    g.textAlign = "right"; g.fillText(amt, W - 44, y); g.textAlign = "left";
    // verdict stamp
    g.save(); g.translate(W - 150, y + 40); g.rotate((i % 3 - 1) * 0.06);
    g.strokeStyle = col; g.fillStyle = col; g.setLineDash([]); g.lineWidth = 3;
    g.font = `800 22px ${mono}`;
    const tw = g.measureText(verdict).width + 26;
    g.beginPath(); g.roundRect(-tw / 2, -18, tw, 34, 8); g.stroke();
    g.textAlign = "center"; g.fillText(verdict, 0, 6); g.restore(); g.textAlign = "left";
    y += 120;
  });
  g.setLineDash([10, 8]); g.beginPath(); g.moveTo(40, y - 40); g.lineTo(W - 40, y - 40); g.stroke();
  g.font = `800 32px ${mono}`; g.fillStyle = "#222521";
  g.fillText("TOTAL", 44, y + 20); g.textAlign = "right"; g.fillText("1,25,900.00", W - 44, y + 20);
  g.font = `400 21px ${mono}`; g.fillStyle = "#6c7068"; g.textAlign = "center";
  g.fillText("Estimated payable 99,370.00 - 1,02,695.00", W / 2, y + 80);
  g.fillText("estimate only, not an insurer decision", W / 2, y + 114);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8;
  return t;
}

const STRIP_W = 2.1, STRIP_H = 5.2, SEG_X = 24, SEG_Y = 160;

function Receipt({ scroll }: { scroll?: MotionValue<number> }) {
  const tex = useMemo(receiptTexture, []);
  const geo = useMemo(() => new THREE.PlaneGeometry(STRIP_W, STRIP_H, SEG_X, SEG_Y), []);
  const base = useMemo(() => Float32Array.from(geo.attributes.position.array as Float32Array), [geo]);
  const mesh = useRef<THREE.Mesh>(null);
  const group = useRef<THREE.Group>(null);
  const { pointer } = useThree();

  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const s = scroll?.get() ?? 0;
    const pos = geo.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) {
      const x = base[i * 3], y = base[i * 3 + 1];
      const v = (y + STRIP_H / 2) / STRIP_H; // 0 bottom .. 1 top
      const twist = Math.sin(t * 0.32 + v * 2.2) * 0.42 + (1 - v) * 0.55 - 0.25 + s * 1.6;
      const curl = Math.sin(v * 3.2 + t * 0.42) * 0.4 + Math.pow(1 - v, 2.4) * 1.2;
      const cx = x * Math.cos(twist), cz = x * Math.sin(twist) + curl;
      pos.setXYZ(i, cx, y + Math.sin(v * 6 + t) * 0.02, cz);
    }
    pos.needsUpdate = true;
    geo.computeVertexNormals();
    if (group.current) {
      group.current.rotation.y += (pointer.x * 0.35 + s * 0.8 - group.current.rotation.y) * 0.05;
      group.current.rotation.x += (-pointer.y * 0.12 - group.current.rotation.x) * 0.05;
      group.current.position.y = Math.sin(t * 0.6) * 0.06 - 0.45 + s * 1.2;
    }
  });

  return (
    <group ref={group} rotation={[0, 0, 0.12]}>
      <mesh ref={mesh} geometry={geo} castShadow>
        <meshStandardMaterial map={tex} side={THREE.DoubleSide} roughness={0.78} metalness={0} />
      </mesh>
    </group>
  );
}

function Tag({ text, color, position, speed, dark = false }: { text: string; color: string; position: [number, number, number]; speed: number; dark?: boolean }) {
  const tex = useMemo(() => {
    const c = document.createElement("canvas"); c.width = 256; c.height = 96;
    const g = c.getContext("2d")!;
    g.fillStyle = color; g.beginPath(); g.roundRect(4, 4, 248, 88, 44); g.fill();
    g.fillStyle = dark ? "#000" : "#fff"; g.font = "700 40px Inter, 'Segoe UI', sans-serif"; g.textAlign = "center"; g.fillText(text, 128, 62);
    const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
  }, [text, color, dark]);
  const ref = useRef<THREE.Sprite>(null);
  useFrame(({ clock }) => {
    if (!ref.current) return;
    ref.current.position.y = position[1] + Math.sin(clock.elapsedTime * speed) * 0.12;
  });
  return <sprite ref={ref} position={position} scale={[0.95, 0.36, 1]}><spriteMaterial map={tex} transparent depthWrite={false} /></sprite>;
}

export default function Hero3D({ still = false, scroll }: { still?: boolean; scroll?: MotionValue<number> }) {
  return (
    <Canvas dpr={[1, 1.8]} camera={{ position: [-0.35, 0, 8.4], fov: 42 }} frameloop={still ? "demand" : "always"}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }} aria-hidden>
      <ambientLight intensity={0.55} />
      <directionalLight position={[-3, 4, 5]} intensity={2.1} color="#ffffff" />
      <directionalLight position={[4, -2, 2]} intensity={1.6} color="#b69a62" />
      <pointLight position={[2.5, 1, 2]} intensity={14} distance={8} color="#b69a62" /><pointLight position={[-2, -2, 3]} intensity={5} distance={9} color="#ffffff" />
      <Receipt scroll={scroll} />
      <Tag text="2.5 covers" color="#b69a62" dark position={[-0.95, 1.75, 0.6]} speed={0.9} />
      <Tag text="4.3 excludes" color="#d08a78" dark position={[1.45, 0.25, 0.4]} speed={1.1} />
      <Tag text="A1.4 conflicts" color="#bfa3cb" dark position={[-0.95, -1.55, 0.8]} speed={0.8} />
    </Canvas>
  );
}
