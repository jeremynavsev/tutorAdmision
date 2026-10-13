/** Tema claro/oscuro: se guarda en data-theme de <html> y en localStorage. */

export type Tema = "light" | "dark";

const CLAVE = "maestro-tema";

/** Tema que se ve ahora: el elegido a mano o, si no hay, el del sistema. */
export function temaActual(): Tema {
  const elegido = document.documentElement.dataset.theme;
  if (elegido === "light" || elegido === "dark") return elegido;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function aplicarTema(tema: Tema): void {
  document.documentElement.dataset.theme = tema;
  try {
    localStorage.setItem(CLAVE, tema);
  } catch {
    // Sin localStorage (modo privado): el cambio vale solo para esta visita.
  }
}

/** Lee y escribe una bandera en localStorage sin romperse si no está disponible. */
export function leerBandera(clave: string): boolean {
  try {
    return localStorage.getItem(clave) === "1";
  } catch {
    return false;
  }
}

export function guardarBandera(clave: string): void {
  try {
    localStorage.setItem(clave, "1");
  } catch {
    // Sin localStorage: no pasa nada, solo no se recuerda.
  }
}

export function prefiereMenosMovimiento(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
