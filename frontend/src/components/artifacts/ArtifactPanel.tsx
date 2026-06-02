import { useState } from 'react';
import styles from './ArtifactPanel.module.css';

export function ArtifactPanel() {
  const [isOpen, setIsOpen] = useState(true);

  if (!isOpen) return null;

  return (
    <aside className={styles.panel}>
      <header className={styles.header}>
        <div className={styles.tabs}>
          <div className={styles.tabActive}>Dog SVG v1</div>
          <button className={styles.addTabBtn}>+</button>
        </div>
      </header>

      <div className={styles.content}>
        <pre className={styles.codeBlock}>
          <code>
{`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400">
  <!-- Body -->
  <path d="M 150 250 Q 200 350 250 250" fill="#a06a38" />
  
  <!-- Eyes -->
  <ellipse cx="180" cy="220" rx="8" ry="12" fill="white" />
  <ellipse cx="220" cy="220" rx="8" ry="12" fill="white" />
  <ellipse cx="180" cy="220" rx="4" ry="6" fill="#2c1810" />
  <ellipse cx="220" cy="220" rx="4" ry="6" fill="#2c1810" />

  <!-- Snout -->
  <ellipse cx="200" cy="240" rx="15" ry="10" fill="#d9b38c" />
  <ellipse cx="200" cy="235" rx="5" ry="3" fill="#2c1810" />

  <!-- Ears -->
  <path d="M 150 180 Q 120 220 140 260" fill="#8c5a2b" />
  <path d="M 250 180 Q 280 220 260 260" fill="#8c5a2b" />

  <!-- Collar -->
  <rect x="170" y="270" width="60" height="10" fill="#cc3333" rx="5" />
  <circle cx="200" cy="285" r="8" fill="#ffd700" />
</svg>`}
          </code>
        </pre>
      </div>

      <footer className={styles.footer}>
        <div className={styles.footerLeft}>
          <button className={styles.iconBtn} title="Undo">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 7v6h6"/><path d="M21 17a9 9 0 00-9-9 9 9 0 00-6 2.3L3 13"/></svg>
            Undo
          </button>
          <button className={styles.iconBtn} title="Redo">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 7v6h-6"/><path d="M3 17a9 9 0 019-9 9 9 0 016 2.3l3 2.7"/></svg>
          </button>
        </div>
        <div className={styles.footerRight}>
          <button className={styles.actionBtn}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
            Copy
          </button>
          <select className={styles.formatSelect} defaultValue="svg">
            <option value="svg">SVG</option>
            <option value="html">HTML</option>
          </select>
          <button className={styles.closeBtn} onClick={() => setIsOpen(false)}>
            ✕ Close
          </button>
        </div>
      </footer>
    </aside>
  );
}
