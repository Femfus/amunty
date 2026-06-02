import { useEffect, useRef } from 'react';

interface Drop {
  x: number;
  y: number;
  len: number;
  speed: number;
  opacity: number;
}

export function Rain() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let W = window.innerWidth;
    let H = window.innerHeight;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    
    const MAX_DROPS = 130;
    const drops: Drop[] = [];

    const resize = () => {
      W = window.innerWidth;
      H = window.innerHeight;
      canvas.width = W * dpr;
      canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener('resize', resize);

    for (let i = 0; i < MAX_DROPS; i++) {
      drops.push({
        x: Math.random() * W,
        y: Math.random() * H - H,
        len: Math.random() * 20 + 10,
        speed: Math.random() * 8 + 6,
        opacity: Math.random() * 0.3 + 0.1
      });
    }

    let raf: number;
    const draw = () => {
      raf = requestAnimationFrame(draw);
      ctx.clearRect(0, 0, W, H);
      
      const s = getComputedStyle(document.documentElement);
      const c = s.getPropertyValue('--bg-effect-color').trim() || s.getPropertyValue('--fg').trim() || '#9cdef2';

      for (const d of drops) {
        d.y += d.speed;
        if (d.y > H + d.len) {
          d.y = -d.len;
          d.x = Math.random() * W;
        }

        ctx.strokeStyle = c;
        ctx.globalAlpha = d.opacity;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(d.x, d.y);
        ctx.lineTo(d.x, d.y + d.len);
        ctx.stroke();
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
