/**
 * Trazos "a mano" para la pizarra: círculos ovalados y torcidos que se pasan
 * al cerrar, cheques y tachones. Cada trazo usa una semilla para que la forma
 * sea irregular pero estable (no cambia cada vez que se redibuja).
 */

export type Caja = { x: number; y: number; ancho: number; alto: number };

/** Generador pseudoaleatorio pequeño y determinista (mulberry32). */
function azar(semilla: string) {
  let h = 1779033703;
  for (let i = 0; i < semilla.length; i++) h = Math.imul(h ^ semilla.charCodeAt(i), 3432918353);
  return () => {
    h = (h + 0x6d2b79f5) | 0;
    let t = Math.imul(h ^ (h >>> 15), 1 | h);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const r1 = (n: number) => Math.round(n * 10) / 10;

/** Óvalo un poco torcido que da más de una vuelta, como un círculo hecho con tiza. */
export function circuloAMano(caja: Caja, semilla: string): string {
  const al = azar(semilla);
  const cx = caja.x + caja.ancho / 2;
  const cy = caja.y + caja.alto / 2;
  // Un dato corto (un solo dígito) igual lleva un círculo redondo, no una ranura.
  const rx = Math.max(caja.ancho / 2 + 6, caja.alto / 2 + 5);
  const ry = caja.alto / 2 + 5;
  const giro = ((al() - 0.5) * 8 * Math.PI) / 180;
  const inicio = -Math.PI * (0.55 + al() * 0.3);
  const vuelta = Math.PI * 2 + 0.5 + al() * 0.3; // se pasa al cerrar
  const pasos = 56;
  const puntos: string[] = [];
  for (let i = 0; i <= pasos; i++) {
    const t = i / pasos;
    const a = inicio + vuelta * t;
    // El radio crece un poco a lo largo del trazo para que la punta no caiga encima del inicio.
    const escala = 0.97 + t * 0.07 + Math.sin(a * 3 + al()) * 0.012;
    const ex = Math.cos(a) * rx * escala;
    const ey = Math.sin(a) * ry * escala;
    const x = cx + ex * Math.cos(giro) - ey * Math.sin(giro);
    const y = cy + ex * Math.sin(giro) + ey * Math.cos(giro);
    puntos.push(`${i === 0 ? "M" : "L"}${r1(x)} ${r1(y)}`);
  }
  return puntos.join(" ");
}

/** Cheque al lado derecho de una caja. */
export function chequeAMano(caja: Caja): string {
  const x = caja.x + caja.ancho - 40;
  const y = caja.y + caja.alto / 2;
  return `M${r1(x)} ${r1(y + 1)} Q${r1(x + 6)} ${r1(y + 6)} ${r1(x + 11)} ${r1(y + 12)} Q${r1(x + 20)} ${r1(y - 4)} ${r1(x + 34)} ${r1(y - 16)}`;
}

/** Línea levemente ondulada que tacha una caja de lado a lado. */
export function tachonAMano(caja: Caja, semilla: string): string {
  const al = azar(semilla);
  const y = caja.y + caja.alto / 2;
  const x0 = caja.x + 4;
  const x1 = caja.x + caja.ancho - 4;
  const medio = (x0 + x1) / 2;
  return `M${r1(x0)} ${r1(y + 4 + al() * 3)} Q${r1(medio)} ${r1(y - 6 - al() * 4)} ${r1(x1)} ${r1(y - 3 + al() * 3)}`;
}
