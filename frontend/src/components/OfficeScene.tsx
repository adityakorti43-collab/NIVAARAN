import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

/*
 * An original real-time scene: a high-end insurance office at night. A translucent policy document floats at
 * the centre of the room; a scan line sweeps it, clauses light up, evidence links run from a clause to a bill
 * item to a calculation, and one discrepancy is marked in amber. Two professionals (stylised figures) stand at
 * the display. All geometry is procedural; textures are drawn on canvases; no remote assets.
 *
 * mode "intro": choreographed timeline (~6 s). mode "hero": settled state with slow camera drift.
 * Critical information is never carried by in-scene text — the page renders it as real HTML.
 */

const CYAN = new THREE.Color("#b69a62");
const ICE = new THREE.Color("#d6c496");
const AMBER = new THREE.Color("#f2b35b");
const clamp01 = (x: number) => Math.min(1, Math.max(0, x));
const ease = (x: number) => 1 - Math.pow(1 - clamp01(x), 3);

function canvasTex(w: number, h: number, draw: (g: CanvasRenderingContext2D) => void) {
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  draw(c.getContext("2d")!);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  return t;
}

const ROWS = 9;
const DOC_W = 2.4, DOC_H = 3.1;
const rowY = (i: number) => DOC_H / 2 - 0.62 - i * 0.27;

function useTextures() {
  return useMemo(() => ({
    doc: canvasTex(600, 775, (g) => {
      g.strokeStyle = "rgba(182,154,98,0.6)"; g.lineWidth = 3; g.strokeRect(4, 4, 592, 767);
      g.fillStyle = "rgba(169,184,165,0.95)"; g.font = "700 34px Inter, 'Segoe UI', sans-serif"; g.fillText("Health Policy Wording", 34, 66);
      g.fillStyle = "rgba(169,184,165,0.55)"; g.font = "500 18px 'Instrument Sans', sans-serif"; g.fillText("Synthetic demonstration document", 34, 96);
      for (let i = 0; i < ROWS; i++) {
        const y = 150 + i * 67;
        g.fillStyle = "rgba(182,154,98,0.55)"; g.fillRect(34, y, 40, 9);
        g.fillStyle = "rgba(169,184,165,0.28)"; g.fillRect(90, y, 330 + ((i * 47) % 110), 9); g.fillRect(90, y + 22, 240 + ((i * 31) % 150), 7);
      }
    }),
    bill: canvasTex(400, 260, (g) => {
      g.fillStyle = "rgba(14,33,28,0.9)"; g.fillRect(0, 0, 400, 260);
      g.strokeStyle = "rgba(169,184,165,0.5)"; g.lineWidth = 3; g.strokeRect(3, 3, 394, 254);
      g.fillStyle = "rgba(241,236,223,0.95)"; g.font = "700 24px Inter, system-ui, sans-serif"; g.fillText("Hospital bill", 24, 46);
      for (let i = 0; i < 4; i++) { g.fillStyle = i === 1 ? "rgba(182,154,98,0.9)" : "rgba(241,236,223,0.35)"; g.fillRect(24, 82 + i * 40, 220, 10); g.fillRect(300, 82 + i * 40, 70, 10); }
    }),
    calc: canvasTex(400, 260, (g) => {
      g.fillStyle = "rgba(14,33,28,0.9)"; g.fillRect(0, 0, 400, 260);
      g.strokeStyle = "rgba(182,154,98,0.55)"; g.lineWidth = 3; g.strokeRect(3, 3, 394, 254);
      g.fillStyle = "rgba(241,236,223,0.95)"; g.font = "700 24px Inter, system-ui, sans-serif"; g.fillText("Calculation", 24, 46);
      [0.9, 0.7, 0.55, 0.42].forEach((w, i) => { g.fillStyle = i === 3 ? "rgba(182,154,98,0.95)" : "rgba(169,184,165,0.4)"; g.fillRect(24, 84 + i * 40, 340 * w, 14); });
    }),
    windows: canvasTex(1024, 512, (g) => {
      g.fillStyle = "#040a08"; g.fillRect(0, 0, 1024, 512);
      for (let x = 0; x < 1024; x += 18) for (let y = 120; y < 512; y += 14) {
        if (Math.sin(x * 12.9898 + y * 78.233) * 43758.5453 % 1 > 0.55) { g.fillStyle = `rgba(${150 + (x % 80)},${190 + (y % 50)},255,${0.15 + ((x * y) % 7) / 30})`; g.fillRect(x, y, 6, 4); }
      }
    }),
  }), []);
}

function Room() {
  const tex = useTextures();
  const strips = [-6, -3.6, -1.2, 1.2, 3.6, 6];
  return (
    <group>
      {/* reflective floor */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.8, 0]}>
        <planeGeometry args={[40, 40]} />
        <meshStandardMaterial color="#07100d" metalness={0.75} roughness={0.32} />
      </mesh>
      {/* city beyond the glass */}
      <mesh position={[0, 1.4, -9.5]}><planeGeometry args={[30, 12]} /><meshBasicMaterial map={tex.windows} toneMapped={false} /></mesh>
      {/* glass wall mullions + light strips */}
      {strips.map((x) => (
        <group key={x} position={[x, 1, -7]}>
          <mesh><boxGeometry args={[0.08, 6.2, 0.08]} /><meshStandardMaterial color="#1b2c27" metalness={0.8} roughness={0.3} /></mesh>
          <mesh position={[0.06, 0, 0.05]}><boxGeometry args={[0.02, 5.8, 0.02]} /><meshBasicMaterial color={ICE} toneMapped={false} transparent opacity={0.45} /></mesh>
        </group>
      ))}
      <mesh position={[0, 1, -7.05]}><planeGeometry args={[16, 6.2]} /><meshStandardMaterial color="#0b1814" transparent opacity={0.35} metalness={0.9} roughness={0.1} /></mesh>
      {/* side columns */}
      {[-7.5, 7.5].map((x) => <mesh key={x} position={[x, 1, -3]}><boxGeometry args={[0.7, 6.4, 0.7]} /><meshStandardMaterial color="#0e1a17" roughness={0.6} /></mesh>)}
      {/* ceiling light lines */}
      {[-4, 0, 4].map((z, i) => <mesh key={z} position={[0, 4.1, z - 2]}><boxGeometry args={[9, 0.03, 0.12]} /><meshBasicMaterial color={i === 1 ? "#ffe2b0" : ICE} toneMapped={false} /></mesh>)}
      {/* reception desk */}
      <mesh position={[-4.6, -1.25, -3.6]}><boxGeometry args={[3.2, 1.1, 0.9]} /><meshStandardMaterial color="#111e1a" metalness={0.5} roughness={0.4} /></mesh>
      <mesh position={[-4.6, -0.68, -3.14]}><boxGeometry args={[3.2, 0.02, 0.02]} /><meshBasicMaterial color={AMBER} toneMapped={false} /></mesh>
    </group>
  );
}

function Person({ position, rot = 0, height = 1.75 }: { position: [number, number, number]; rot?: number; height?: number }) {
  const s = height / 1.75;
  return (
    <group position={position} rotation={[0, rot, 0]} scale={s}>
      <mesh position={[0, -0.95, 0]}><capsuleGeometry args={[0.2, 0.9, 6, 12]} /><meshStandardMaterial color="#0d1915" roughness={0.55} metalness={0.2} /></mesh>
      <mesh position={[0, -0.05, 0]}><capsuleGeometry args={[0.27, 0.55, 6, 12]} /><meshStandardMaterial color="#14241f" roughness={0.5} metalness={0.25} /></mesh>
      <mesh position={[0, 0.58, 0]}><sphereGeometry args={[0.17, 20, 20]} /><meshStandardMaterial color="#1a2b26" roughness={0.45} /></mesh>
      {/* raised arm gesturing at the display */}
      <mesh position={[0.3, 0.12, 0.18]} rotation={[-0.9, 0, -0.5]}><capsuleGeometry args={[0.06, 0.5, 4, 8]} /><meshStandardMaterial color="#14241f" /></mesh>
    </group>
  );
}

function Hologram({ mode, start }: { mode: "intro" | "hero"; start: number }) {
  const tex = useTextures();
  const group = useRef<THREE.Group>(null);
  const scan = useRef<THREE.Mesh>(null);
  const rows = useRef<THREE.Mesh[]>([]);
  const nodes = useRef<THREE.Mesh[]>([]);
  const links = useRef<THREE.Mesh[]>([]);
  const amber = useRef<THREE.Mesh>(null);
  const cards = useRef<THREE.Mesh[]>([]);
  const clauseRow = 3, discrepancyRow = 6;
  const p0 = useMemo(() => new THREE.Vector3(DOC_W / 2, rowY(clauseRow), 0.02), []);
  const billPos = useMemo(() => new THREE.Vector3(2.55, 0.55, 0.35), []);
  const calcPos = useMemo(() => new THREE.Vector3(2.55, -0.85, 0.35), []);
  const curves = useMemo(() => [
    new THREE.CatmullRomCurve3([p0, new THREE.Vector3(1.6, rowY(clauseRow) + 0.15, 0.4), billPos.clone().add(new THREE.Vector3(-0.85, -0.05, 0))]),
    new THREE.CatmullRomCurve3([billPos.clone().add(new THREE.Vector3(0, -0.45, 0)), new THREE.Vector3(2.75, -0.15, 0.45), calcPos.clone().add(new THREE.Vector3(0, 0.45, 0))]),
  ], [p0, billPos, calcPos]);
  const tubes = useMemo(() => curves.map((c) => new THREE.TubeGeometry(c, 40, 0.011, 6, false)), [curves]);

  useFrame(({ clock }) => {
    const t = clock.elapsedTime - start;
    const loop = mode === "hero" ? (t % 7) + 1.6 : t;          // hero replays the scan gently
    const appear = mode === "hero" ? 1 : ease((t - 1.6) / 1.0);
    if (group.current) {
      group.current.scale.setScalar(0.85 + appear * 0.15);
      group.current.position.y = 0.35 + Math.sin(clock.elapsedTime * 0.6) * 0.04;
      group.current.children.forEach((c) => {
        const m = (c as THREE.Mesh).material as THREE.Material & { opacity?: number; userData: { base?: number } };
        if (m && "opacity" in m && m.userData.base !== undefined) m.opacity = m.userData.base * appear;
      });
    }
    const scanP = clamp01((loop - 2.2) / 1.5);
    const scanY = DOC_H / 2 - scanP * DOC_H;
    if (scan.current) { scan.current.position.y = scanY; (scan.current.material as THREE.MeshBasicMaterial).opacity = scanP > 0 && scanP < 1 ? 0.9 : 0; }
    rows.current.forEach((m, i) => {
      const mat = m.material as THREE.MeshBasicMaterial;
      const lit = scanP > 0 && scanY < rowY(i);
      const target = !lit ? 0 : i === clauseRow ? 0.55 : i === discrepancyRow ? 0 : 0.12;
      mat.opacity += (target - mat.opacity) * 0.12;
    });
    const nodeP = ease((loop - 3.0) / 0.6);
    nodes.current.forEach((n) => n.scale.setScalar(Math.max(0.001, nodeP)));
    const linkP = [ease((loop - 3.5) / 0.6), ease((loop - 4.0) / 0.6)];
    links.current.forEach((l, i) => {
      const g = l.geometry as THREE.TubeGeometry;
      g.setDrawRange(0, Math.floor((g.index?.count ?? 0) * linkP[i]));
    });
    cards.current.forEach((c, i) => {
      const m = c.material as THREE.MeshBasicMaterial;
      m.opacity = 0.95 * ease((loop - (3.3 + i * 0.5)) / 0.6);
    });
    if (amber.current) {
      const a = ease((loop - 4.4) / 0.5);
      const pulse = 0.65 + Math.sin(clock.elapsedTime * 4) * 0.35;
      (amber.current.material as THREE.MeshBasicMaterial).opacity = a * 0.5 * pulse;
    }
  });

  const mat = (base: number, extra: Partial<THREE.MeshBasicMaterialParameters> = {}) => {
    const m = new THREE.MeshBasicMaterial({ transparent: true, opacity: base, depthWrite: false, ...extra });
    m.userData.base = base;
    return m;
  };

  return (
    <group ref={group} position={[-0.6, 0.35, 0]}>
      <mesh material={mat(0.95, { map: tex.doc, blending: THREE.AdditiveBlending })}><planeGeometry args={[DOC_W, DOC_H]} /></mesh>
      <mesh position={[0, 0, -0.02]} material={mat(0.55, { color: "#06120f" })}><planeGeometry args={[DOC_W, DOC_H]} /></mesh>
      <mesh position={[0, -DOC_H / 2 - 0.05, 0.1]} rotation={[-Math.PI / 2, 0, 0]} material={mat(0.35, { color: CYAN, blending: THREE.AdditiveBlending })}>
        <ringGeometry args={[0.9, 1.25, 64]} />
      </mesh>
      {Array.from({ length: ROWS }).map((_, i) => (
        <mesh key={i} ref={(m) => { if (m) rows.current[i] = m; }} position={[0, rowY(i) + 0.02, 0.01]}>
          <planeGeometry args={[DOC_W - 0.18, 0.2]} /><meshBasicMaterial color={CYAN} transparent opacity={0} blending={THREE.AdditiveBlending} depthWrite={false} />
        </mesh>
      ))}
      <mesh ref={amber} position={[0, rowY(discrepancyRow) + 0.02, 0.015]}>
        <planeGeometry args={[DOC_W - 0.18, 0.2]} /><meshBasicMaterial color={AMBER} transparent opacity={0} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      <mesh ref={scan} position={[0, DOC_H / 2, 0.03]}>
        <planeGeometry args={[DOC_W + 0.3, 0.025]} /><meshBasicMaterial color={CYAN} transparent opacity={0} blending={THREE.AdditiveBlending} toneMapped={false} />
      </mesh>
      {[billPos, calcPos].map((p, i) => (
        <mesh key={i} ref={(m) => { if (m) cards.current[i] = m; }} position={p}>
          <planeGeometry args={[1.7, 1.1]} /><meshBasicMaterial map={i === 0 ? tex.bill : tex.calc} transparent opacity={0} depthWrite={false} />
        </mesh>
      ))}
      {tubes.map((g, i) => (
        <mesh key={i} ref={(m) => { if (m) links.current[i] = m; }} geometry={g}>
          <meshBasicMaterial color={CYAN} transparent opacity={0.85} blending={THREE.AdditiveBlending} toneMapped={false} />
        </mesh>
      ))}
      {[p0, new THREE.Vector3(DOC_W / 2 + 0.08, rowY(discrepancyRow), 0.05), billPos.clone().add(new THREE.Vector3(-0.85, -0.05, 0))].map((p, i) => (
        <mesh key={i} ref={(m) => { if (m) nodes.current[i] = m; }} position={p} scale={0.001}>
          <sphereGeometry args={[0.05, 16, 16]} /><meshBasicMaterial color={i === 1 ? AMBER : ICE} toneMapped={false} />
        </mesh>
      ))}
      <pointLight position={[0, 0, 1.2]} color={CYAN} intensity={6} distance={6} />
    </group>
  );
}

function Rig({ mode, start }: { mode: "intro" | "hero"; start: number }) {
  const { camera, pointer, scene, size } = useThree();
  const amb = useRef<THREE.AmbientLight>(null);
  const spots = useRef<THREE.SpotLight[]>([]);
  const shift = useRef(0);
  useFrame(({ clock }) => {
    // Hero on wide screens: slide the projected image right (a view offset, so no extra perspective skew) and pull the
    // camera back slightly, so the whole hologram sits beside the HTML headline instead of behind it.
    const wide = mode === "hero" && size.width >= 1024 && size.width / size.height > 1.2;
    shift.current += ((wide ? 0.27 : 0) - shift.current) * 0.06;
    const cam = camera as THREE.PerspectiveCamera;
    if (Math.abs(shift.current) > 0.002) cam.setViewOffset(size.width, size.height, -shift.current * size.width, 0, size.width, size.height);
    else if (cam.view) cam.clearViewOffset();
    const t = clock.elapsedTime - start;
    const reveal = mode === "hero" ? 1 : ease(t / 1.6);
    const dolly = mode === "hero" ? 1 : ease(t / 4.2);
    if (amb.current) amb.current.intensity = 0.06 + reveal * 0.32;
    spots.current.forEach((s, i) => { s.intensity = reveal * (i === 0 ? 55 : 30); });
    const fog = scene.fog as THREE.Fog | null;
    if (fog) fog.far = 8 + reveal * 18;
    const drift = mode === "hero" ? Math.sin(clock.elapsedTime * 0.12) * 0.5 : 0;
    const x = THREE.MathUtils.lerp(-3.2, 0.9, dolly) + drift + pointer.x * 0.35;
    const z = THREE.MathUtils.lerp(13, 7.4, dolly) + shift.current * 9;
    const y = THREE.MathUtils.lerp(1.6, 0.55, dolly) + pointer.y * 0.18;
    camera.position.lerp(new THREE.Vector3(x, y, z), 0.08);
    camera.lookAt(0.5, 0.2, 0);
  });
  return (
    <>
      <ambientLight ref={amb} intensity={0.06} color="#c9d4c4" />
      <spotLight ref={(s) => { if (s) spots.current[0] = s; }} position={[0, 4, 2]} angle={0.55} penumbra={0.8} intensity={0} color="#f1ecdf" distance={14} />
      <spotLight ref={(s) => { if (s) spots.current[1] = s; }} position={[-4.6, 3.8, -2.5]} angle={0.5} penumbra={0.9} intensity={0} color="#ffd9a0" distance={10} />
    </>
  );
}

export default function OfficeScene({ mode = "hero", still = false }: { mode?: "intro" | "hero"; still?: boolean }) {
  const start = useRef(0);
  return (
    <Canvas dpr={[1, 1.6]} camera={{ position: [-3.2, 1.6, 13], fov: 38 }} frameloop={still ? "demand" : "always"}
      gl={{ antialias: true, powerPreference: "high-performance" }} onCreated={({ clock, scene }) => { start.current = clock.elapsedTime; scene.background = new THREE.Color("#050c0a"); }} aria-hidden>
      <fog attach="fog" args={["#050c0a", 6, 26]} />
      <Rig mode={still ? "hero" : mode} start={start.current} />
      <Room />
      <Person position={[-2.35, -0.05, 0.9]} rot={0.7} />
      <Person position={[1.15, -0.1, 1.6]} rot={-0.9} height={1.68} />
      <Hologram mode={still ? "hero" : mode} start={start.current} />
    </Canvas>
  );
}
