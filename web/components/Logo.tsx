/**
 * Wordmark de MAEstro: "MAE" en Bricolage 800 (cafetal) y "stro" en 400 (carbón).
 * Debajo, dos trazos irregulares en guaria que se dibujan al cargar, como tiza.
 */
export default function Logo({ ancho = 132 }: { ancho?: number }) {
  return (
    <svg
      className="logo"
      role="img"
      aria-label="MAEstro"
      width={ancho}
      height={(ancho * 50) / 150}
      viewBox="0 0 150 50"
      xmlns="http://www.w3.org/2000/svg"
    >
      <text x="1" y="31" fontSize="32" letterSpacing="-0.6">
        <tspan className="logo-mae">MAE</tspan>
        <tspan className="logo-stro">stro</tspan>
      </text>
      <path className="logo-trazo" pathLength={1} strokeWidth="2.8" d="M3 40.5 C 14 38.2, 25 41.6, 38 39.2 S 56 37.6, 66 39.8" />
      <path className="logo-trazo" pathLength={1} strokeWidth="1.8" d="M12 45.2 C 22 43.6, 33 46.1, 46 44.3" />
    </svg>
  );
}
