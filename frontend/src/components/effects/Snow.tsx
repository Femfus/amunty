import { useEffect, useRef } from 'react';

interface Flake {
  x: number;
  y: number;
  r: number;       // radius
  speed: number;
  drift: number;   // horizontal wobble speed
  phase: number;   // wobble phase offset
  opacity: number;
}

const FLAKE_COUNT = 60;
const TARGET_FPS  = 30;
const FRAME_MS    = 1000 / TARGET_FPS;

function makeFlake(w: number, h: number): Flake {
  return {
    x:       Math.random() * w,
    y:       Math.random() * h - h,   // start above viewport
    r:       Math.random() * 2 + 0.8, // 0.8–2.8 px
    speed:   Math.random() * 0.6 + 0.3,
    drift:   Math.random() * 0.4 + 0.1,
    phase:   Math.random() * Math.PI * 2,
    opacity: Math.random() * 0.35 + 0.1, // 0.1–0.45 — very subtle
  };
}

export function Snow() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let w = window.innerWidth;
    let h = window.innerHeight;
    canvas.width  = w;
    canvas.height = h;

    // Initialise flakes scattered across the full height
    const flakes: Flake[] = Array.from({ length: FLAKE_COUNT }, () =>
      makeFlake(w, h)
    );
    // Spread them vertically so there's no "wave" at start
    flakes.forEach((f) => { f.y = Math.random() * h; });

    let raf = 0;
    let lastTime = 0;
    let t = 0; // time accumulator for wobble

    const draw = (now: number) => {
      raf = requestAnimationFrame(draw);

      const delta = now - lastTime;
      if (delta < FRAME_MS) return; // frame-rate cap
      lastTime = now - (delta % FRAME_MS);
      t += delta * 0.001; // seconds

      ctx.clearRect(0, 0, w, h);

      for (const f of flakes) {
        // Drift left/right with a sine wave
        const dx = Math.sin(t * f.drift + f.phase) * 0.5;
        f.x += dx;
        f.y += f.speed;

        // Wrap around
        if (f.y > h + 4) {
          f.y = -4;
          f.x = Math.random() * w;
        }
        if (f.x > w + 4) f.x = -4;
        if (f.x < -4)    f.x = w + 4;

        ctx.beginPath();
        ctx.arc(f.x, f.y, f.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(156, 222, 242, ${f.opacity})`; // --fg cyan tint
        ctx.fill();
      }
    };

    raf = requestAnimationFrame(draw);

    const onResize = () => {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width  = w;
      canvas.height = h;
    };
    window.addEventListener('resize', onResize);

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', onResize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        inset: 0,
        pointerEvents: 'none',
        zIndex: 0,
      }}
      aria-hidden="true"
    />
  );
}
