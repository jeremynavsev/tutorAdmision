/**
 * Detección de datos personales antes de enviar un mensaje.
 *
 * Es una copia de las reglas de backend/app/servicios/privacidad.py: si cambian
 * allá, cambian aquí. La página la usa para avisarle al estudiante antes de
 * enviar; el backend igual oculta los datos por su cuenta, por si algo se escapa.
 *
 * Se cuida de no confundir los números de un ejercicio con datos personales:
 * un teléfono sin +506 o un número largo suelto solo cuentan si hay palabras
 * como "cédula", "cel" o "WhatsApp" cerca.
 */

export type TipoDato = "cedula" | "telefono" | "correo" | "nombre";
export type Hallazgo = { tipo: TipoDato; inicio: number; fin: number };

const MARCAS: Record<TipoDato, string> = {
  cedula: "[cédula oculta]",
  telefono: "[teléfono oculto]",
  correo: "[correo oculto]",
  nombre: "[nombre oculto]",
};

/** Cómo se nombra cada dato en el aviso al estudiante. */
export const NOMBRES_DE_DATOS: Record<TipoDato, string> = {
  cedula: "una cédula",
  telefono: "un teléfono",
  correo: "un correo",
  nombre: "tu nombre completo",
};

const LETRA = "A-Za-zÁÉÍÓÚÜÑáéíóúüñ";
const MAYUSCULA = "A-ZÁÉÍÓÚÜÑ";

const CORREO = /[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g;
const CEDULA = /(?<![\d-])[1-9][- .]\d{4}[- .]\d{4}(?![\d-])/g;
const TELEFONO = /(?:(?:\+|\b00)?\(?506\)?[\s-]?)?(?<![\d-])[245678]\d{3}[\s-]\d{4}(?![\d-])/g;
const TELEFONO_CON_PREFIJO = /(?:\+|\b00)\(?506\)?[\s-]?[245678]\d{7}(?!\d)/g;
const NUMERO_LARGO = /(?<![\d.,])\d{8,12}(?![\d.,])/g;
const CONTEXTO =
  /\b(c[ée]dula|c[ée]d\.?|identificaci[óo]n|dimex|tel[ée]fono|tel\.?|cel(?:ular)?|whats?app|mi\s+n[úu]mero|n[úu]mero\s+(?:de\s+)?(?:tel|cel|c[ée]d)|ll[áa]mame|escribime)(?![A-Za-zÁÉÍÓÚÜÑáéíóúüñ])/gi;
const PALABRAS_DE_TELEFONO = ["tel", "cel", "whats", "llam", "escrib", "mi n"];
const NOMBRE = new RegExp(
  `\\b(?:me\\s+llamo|mi\\s+nombre\\s+es|soy)\\s+((?:[${MAYUSCULA}][${LETRA}]+)(?:\\s+(?:de\\s+(?:la\\s+)?)?[${MAYUSCULA}][${LETRA}]+){1,4})`,
  "gi",
);

/** La palabra de contexto más cercana en los 40 caracteres anteriores, si hay. */
function contextoAntes(texto: string, inicio: number): string | null {
  const hallados = [...texto.slice(Math.max(0, inicio - 40), inicio).matchAll(CONTEXTO)];
  return hallados.length ? hallados[hallados.length - 1][0].toLowerCase() : null;
}

function pareceNombre(texto: string): boolean {
  const palabras = texto.split(/\s+/).filter(Boolean);
  if (!palabras.length || palabras[0][0] !== palabras[0][0].toUpperCase()) return false;
  const nombres = palabras.filter((p) => !["de", "la"].includes(p.toLowerCase()));
  return nombres.length >= 2 && nombres.every((p) => p[0] === p[0].toUpperCase() && p[0] !== p[0].toLowerCase());
}

/** Los datos personales del texto, en orden y sin superponerse. */
export function encontrarDatos(texto: string): Hallazgo[] {
  const hallazgos: Hallazgo[] = [];
  const agregar = (tipo: TipoDato, m: RegExpMatchArray, desde = m.index ?? 0, largo = m[0].length) =>
    hallazgos.push({ tipo, inicio: desde, fin: desde + largo });

  for (const m of texto.matchAll(CORREO)) agregar("correo", m);
  for (const m of texto.matchAll(CEDULA)) agregar("cedula", m);
  for (const m of texto.matchAll(TELEFONO_CON_PREFIJO)) agregar("telefono", m);
  for (const m of texto.matchAll(TELEFONO)) {
    if (m[0].includes("506") || contextoAntes(texto, m.index ?? 0)) agregar("telefono", m);
  }
  for (const m of texto.matchAll(NUMERO_LARGO)) {
    const palabra = contextoAntes(texto, m.index ?? 0);
    if (palabra) agregar(PALABRAS_DE_TELEFONO.some((p) => palabra.includes(p)) ? "telefono" : "cedula", m);
  }
  for (const m of texto.matchAll(NOMBRE)) {
    if (pareceNombre(m[1])) agregar("nombre", m, (m.index ?? 0) + m[0].lastIndexOf(m[1]), m[1].length);
  }

  hallazgos.sort((a, b) => a.inicio - b.inicio || b.fin - b.inicio - (a.fin - a.inicio));
  const limpios: Hallazgo[] = [];
  for (const h of hallazgos) {
    if (!limpios.length || h.inicio >= limpios[limpios.length - 1].fin) limpios.push(h);
  }
  return limpios;
}

/** Reemplaza los datos personales por marcas como "[cédula oculta]". */
export function ocultarDatos(texto: string): string {
  let resultado = "";
  let ultimo = 0;
  for (const h of encontrarDatos(texto)) {
    resultado += texto.slice(ultimo, h.inicio) + MARCAS[h.tipo];
    ultimo = h.fin;
  }
  return resultado + texto.slice(ultimo);
}
