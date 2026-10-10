// Kept separate from Hero3D so the landing page doesn't load three.js unless WebGL is used.
export function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch { return false; }
}

/** Static fallback (no WebGL): the same receipt, flat and gently tilted. */
export function HeroFallback() {
  const rows = ["Deluxe room x 2", "Surgeon fee", "USG abdomen", "MVI infusion", "TV & telephone", "Nebulizer kit"];
  const stamps = [["PARTIAL", "#74b0ee"], ["COVERED", "#b69a62"], ["COVERED", "#b69a62"], ["CONDITION", "#f2b35b"], ["EXCLUDED", "#f2806f"], ["CONFLICT", "#cf96ea"]];
  return (
    <svg viewBox="0 0 400 520" className="h-full w-full" aria-hidden>
      <g transform="translate(110 20) rotate(8)">
        <rect width="200" height="470" rx="6" fill="#fff" />
        <text x="100" y="40" textAnchor="middle" fontFamily="monospace" fontWeight="700" fontSize="13" fill="#000000">SYNTHETIC CARE HOSPITAL</text>
        {rows.map((r, i) => (
          <g key={r} transform={`translate(0 ${80 + i * 62})`}>
            <text x="14" y="0" fontFamily="monospace" fontSize="11" fill="#000000">{r}</text>
            <rect x="110" y="12" width="76" height="20" rx="5" fill="none" stroke={stamps[i][1]} strokeWidth="2" />
            <text x="148" y="26" textAnchor="middle" fontFamily="monospace" fontSize="9" fontWeight="800" fill={stamps[i][1]}>{stamps[i][0]}</text>
          </g>
        ))}
      </g>
    </svg>
  );
}
