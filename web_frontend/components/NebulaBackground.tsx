"use client";

/**
 * Fixed, full-viewport background: a deep-space base color, a few
 * softly drifting gradient "nebula blobs" in the brand colors, and a
 * sprinkling of static star points. Pure CSS/SVG, no canvas or heavy
 * animation libraries -- keeps this cheap to render and easy for Sina
 * to tweak later (it's just divs with Tailwind classes).
 *
 * Rendered once near the root layout; every page sits on top of it
 * with a transparent/semi-transparent surface.
 */
export default function NebulaBackground() {
  return (
    <div aria-hidden="true" className="fixed inset-0 -z-10 overflow-hidden bg-nebula-bg">
      {/* Base radial glow wash, from the Tailwind theme's bg-nebula-glow */}
      <div className="absolute inset-0 bg-nebula-glow" />

      {/* Drifting blobs -- soft, blurred, slow */}
      <div className="absolute -top-32 -left-20 h-[36rem] w-[36rem] rounded-full bg-nebula-purple/20 blur-[110px] animate-drift-slow" />
      <div className="absolute top-1/3 -right-32 h-[30rem] w-[30rem] rounded-full bg-nebula-blue/15 blur-[100px] animate-drift-slower" />
      <div className="absolute bottom-[-10rem] left-1/4 h-[28rem] w-[28rem] rounded-full bg-nebula-pink/15 blur-[100px] animate-drift-slow" />

      {/* Star points */}
      <Starfield />

      {/* Subtle top-to-bottom vignette so content near the edges stays readable */}
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-nebula-bg/60" />
    </div>
  );
}

function Starfield() {
  // Deterministic pseudo-random star positions (seeded, not
  // Math.random()) so server-rendered and client-rendered markup match
  // exactly -- avoids a Next.js hydration mismatch warning, which
  // Math.random() in a component body would otherwise trigger.
  const stars = generateStars(90);
  return (
    <svg className="absolute inset-0 h-full w-full opacity-70" preserveAspectRatio="none">
      {stars.map((s, i) => (
        <circle
          key={i}
          cx={`${s.x}%`}
          cy={`${s.y}%`}
          r={s.r}
          fill="#F5F5F5"
          opacity={s.opacity}
        />
      ))}
    </svg>
  );
}

function generateStars(count: number) {
  // Simple seeded LCG so output is stable across server/client renders.
  let seed = 42;
  const next = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    return (seed % 10000) / 10000;
  };
  return Array.from({ length: count }, () => ({
    x: next() * 100,
    y: next() * 100,
    r: 0.4 + next() * 1.1,
    opacity: 0.25 + next() * 0.5,
  }));
}
