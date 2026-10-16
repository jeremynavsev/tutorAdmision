/**
 * Tutor SIMULADO de MAEstro.
 *
 * Imita al tutor real mientras el chat no está conectado al backend. No trae
 * ejercicios cargados: la persona manda su problema (de razonamiento
 * matemático o verbal, como en la Prueba de Aptitud Académica de la UCR y la UNA), el
 * tutor lo copia en la pizarra, encierra los datos y guía con tres niveles de
 * pista, sin dar nunca la respuesta.
 *
 * Es una función sin memoria propia: todo lo que necesita sale del `Contexto`
 * (lo que ya está en la pizarra, cuántas pistas se dieron y el historial).
 * Cumple el tipo `Tutor` de ./contrato.ts, igual que lo hará el tutor real.
 */

import type { Contexto, EntradaTutor, RespuestaTutor, Tutor } from "./contrato";

const PISTAS: RespuestaTutor[] = [
  {
    pista: 1,
    texto:
      "Empecemos por los datos que encerré en la pizarra. ¿Qué representa cada uno? Y con tus palabras: ¿qué te está pidiendo el problema?",
    anotaciones: [{ tipo: "apunte", texto: "1. ¿Qué me dan? ¿Qué me piden?" }],
  },
  {
    pista: 2,
    texto:
      "Ahora buscá la relación entre esos datos. ¿Hay alguna operación, fórmula o patrón que los conecte? No hace falta resolver todavía, solo plantear.",
    anotaciones: [{ tipo: "apunte", texto: "2. ¿Qué relación hay entre los datos?" }],
  },
  {
    pista: 3,
    texto:
      "Último empujón: escribí la operación que planteaste y mandámela antes de resolverla. Si va bien encaminada, la resolvés vos y revisamos el resultado juntos.",
    anotaciones: [{ tipo: "apunte", texto: "3. Plantear → resolver → revisar" }],
  },
];

/** Quita tildes y pasa a minúsculas para comparar con calma. */
function normalizar(texto: string) {
  return texto
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "");
}

/** Saca hasta cuatro datos numéricos del enunciado (montos, porcentajes, números). */
export function extraerDatos(enunciado: string): string[] {
  const encontrados = enunciado.match(/₡?\s?\d+(?:[ .,]\d+)*(?:\s?%)?/g) ?? [];
  const limpios = encontrados.map((d) => d.trim()).filter((d) => d.length > 0);
  return [...new Set(limpios)].slice(0, 4);
}

/** ¿Parece el enunciado de un problema y no una charla? */
export function pareceProblema(texto: string) {
  const t = normalizar(texto);
  const tieneNumeros = /\d/.test(t);
  const tienePregunta = /\?|cual|cuanto|cuantos|calcule|determine|encuentre|halle|que numero|sigue/.test(t);
  // Una ecuación u operación con números ("3x-5+20=50", "6000 ÷ 40 000") ya es un problema, aunque sea corta.
  const tieneOperacion = /\d\s*[a-z]?\s*[=+\-*/×÷^<>]\s*[\d(a-z]/.test(t);
  return tieneOperacion || (tieneNumeros && tienePregunta) || (texto.length >= 35 && (tieneNumeros || tienePregunta));
}

const pausa = (ms: number) => new Promise((r) => setTimeout(r, ms));

function siguientePista(pistasDadas: number, prefacio = ""): RespuestaTutor {
  if (pistasDadas >= PISTAS.length) {
    return {
      texto: `${prefacio}Ya te di las tres pistas. Hacé el planteamiento en el cuaderno y contame qué te dio: estás a un paso.`,
      anotaciones: [],
    };
  }
  const pista = PISTAS[pistasDadas];
  return { ...pista, texto: prefacio + pista.texto };
}

function responderSincrono({ texto, fotoBase64 }: EntradaTutor, { enunciado, pistasDadas }: Contexto): RespuestaTutor {
  const t = normalizar(texto);

  if (fotoBase64) {
    return {
      texto:
        "Modo de prueba: todavía no puedo leer fotos. Escribime el enunciado y lo copio en la pizarra para trabajarlo juntos.",
      anotaciones: [],
    };
  }

  const pideRespuesta = /(decime|dame|deci|cual es|pasame).*(respuesta|resultado|solucion)|la respuesta/.test(t);

  if (!enunciado) {
    if (pareceProblema(texto)) {
      const datos = extraerDatos(texto);
      return {
        texto:
          datos.length > 0
            ? "Listo, ya lo copié en la pizarra y encerré los datos. Antes de hacer cuentas: con tus palabras, ¿qué te está pidiendo el problema?"
            : "Listo, ya lo copié en la pizarra. Antes de empezar: con tus palabras, ¿qué te está pidiendo el problema?",
        anotaciones: [{ tipo: "enunciado", texto }, ...datos.map((dato) => ({ tipo: "circulo" as const, dato }))],
      };
    }
    if (pideRespuesta) {
      return {
        texto: "La respuesta no te la voy a dar, pero sí te acompaño. Primero mandame el problema: escribilo o tomale una foto.",
        anotaciones: [],
      };
    }
    return {
      texto:
        "¡Hola! Mandame el problema que querés practicar: escribilo completo, con las opciones si las tiene, y lo copio en la pizarra.",
      anotaciones: [],
    };
  }

  if (pideRespuesta) {
    return siguientePista(pistasDadas, "Eso no te lo voy a dar: si te lo digo, no aprendés el truco. Pero te ayudo: ");
  }

  if (/pista|ayuda|no se|no entiendo|por donde|empiezo|empezar|perdid/.test(t)) {
    return siguientePista(pistasDadas);
  }

  // Propone una operación o un resultado: el tutor pide que lo justifique.
  if (/\d/.test(t)) {
    return {
      texto:
        "Vamos bien. Antes de seguir: ¿por qué hiciste esa operación? Explicame el paso y revisamos juntos si tiene sentido con lo que pide el problema.",
      anotaciones: [{ tipo: "apunte", texto: `vos: ${texto.length > 38 ? `${texto.slice(0, 38)}…` : texto}` }],
    };
  }

  return {
    texto: "Contame un poquito más de cómo lo estás pensando. Si te trabás, pedime una pista.",
    anotaciones: [],
  };
}

/** Tutor simulado: espera un poco, como si el modelo estuviera pensando, y responde. */
export const tutorSimulado: Tutor = async (entrada, contexto) => {
  await pausa(entrada.fotoBase64 ? 1300 : 900);
  return responderSincrono(entrada, contexto);
};
