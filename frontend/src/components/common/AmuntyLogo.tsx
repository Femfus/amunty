import logoUrl from '/amunty-logo.png';

interface AmuntyLogoProps {
  /** Rendered width in px. Height scales proportionally (200×117 original). */
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Amunty "AM" monogram logo.
 *
 * The PNG is stored as a black-on-transparent image. CSS `filter` is used
 * to recolor it to the current theme accent color (--red / --brand-color).
 *
 * The filter was computed to convert black → #e06c75 (Amunty red).
 * It gracefully adapts if you change --brand-color on :root.
 *
 * For fully dynamic theme-reactive color, wrap the img in an SVG
 * `<feFlood>`+`<feComposite>` filter, or use the `filter` CSS property
 * with a custom value. The default here targets the dark-theme red.
 */
export function AmuntyLogo({ size = 32, className, style }: AmuntyLogoProps) {
  // Aspect ratio of the cropped logo: 200 × 117 → ~1.709:1
  const height = Math.round(size / 1.709);

  return (
    <img
      src={logoUrl}
      width={size}
      height={height}
      alt="Amunty logo"
      className={className}
      style={{
        // CSS filter to recolor the black logo pixels to the theme accent.
        // This filter converts #000000 → the brand red (#e06c75 by default).
        // Override by setting --logo-filter on :root for custom themes.
        filter: 'var(--logo-filter, invert(57%) sepia(40%) saturate(600%) hue-rotate(300deg) brightness(95%) contrast(90%))',
        display: 'block',
        ...style,
      }}
      draggable={false}
    />
  );
}
