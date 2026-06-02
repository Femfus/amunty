import { useEffect, useRef } from 'react';

interface Pulse {
  x: number;
  y: number;
  dx: number;
  dy: number;
}

export function Synapse() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let W = window.innerWidth;
    let H = window.innerHeight;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const GRID = 24;
    const MAX_PULSES = 20;
    const SPEED_MIN = 2;
    const SPEED_MAX = 22;
    const TRAIL_LEN = 12;
    
    let cols = Math.ceil(W / GRID);
    let rows = Math.ceil(H / GRID);
    const pulses: Pulse[] = [];

    const resize = () => {
      W = window.innerWidth;
      H = window.innerHeight;
      canvas.width = W * dpr;
      canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      cols = Math.ceil(W / GRID);
      rows = Math.ceil(H / GRID);
    };
    resize();
    window.addEventListener('resize', resize);

    const spawnPulse = () => {
      const speed = SPEED_MIN + Math.random() * (SPEED_MAX - SPEED_MIN);
      if (Math.random() > 0.5) {
        const row = Math.floor(Math.random() * (rows + 1));
        pulses.push({ x: -TRAIL_LEN, y: row * GRID, dx: speed, dy: 0 });
      } else {
        const col = Math.floor(Math.random() * (cols + 1));
        pulses.push({ x: col * GRID, y: -TRAIL_LEN, dx: 0, dy: speed });
      }
    };

    let raf: number;
    const draw = () => {
      raf = requestAnimationFrame(draw);
      ctx.clearRect(0, 0, W, H);
      
      const s = getComputedStyle(document.documentElement);
      const c = s.getPropertyValue('--bg-effect-color').trim() || s.getPropertyValue('--fg').trim() || '#9cdef2';

      if (pulses.length < MAX_PULSES && Math.random() < 0.12) spawnPulse();

      for (let i = pulses.length - 1; i >= 0; i--) {
        const p = pulses[i];
        p.x += p.dx;
        p.y += p.dy;

        if (p.x > W + TRAIL_LEN || p.y > H + TRAIL_LEN) {
          pulses.splice(i, 1);
          continue;
        }

        const tx = p.x - (p.dx > 0 ? TRAIL_LEN : 0);
        const ty = p.y - (p.dy > 0 ? TRAIL_LEN : 0);
        const grad = ctx.createLinearGradient(tx, ty, p.x, p.y);
        grad.addColorStop(0, 'transparent');
        grad.addColorStop(1, c);
        
        ctx.strokeStyle = grad;
        ctx.globalAlpha = 0.35;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(tx, ty);
        ctx.lineTo(p.x, p.y);
        ctx.stroke();

        ctx.globalAlpha = 0.55;
        ctx.fillStyle = c;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.2, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
    };
    draw();

    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return <canvas ref={canvasRef} style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 0 }} aria-hidden="true" />;
}
