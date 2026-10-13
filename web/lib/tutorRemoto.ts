/**
 * Tutor REAL de MAEstro: le pasa el mensaje al backend (POST /api/chat), que es
 * el que consulta a la IA.
 *
 * Cumple el mismo tipo `Tutor` que el simulado; solo traduce entre los nombres
 * del frontend (camelCase) y los del backend (snake_case). Si algo falla lanza
 * un `ErrorDeApi`, cuyo mensaje ya está pensado para mostrárselo al estudiante.
 */

import { enviarMensaje } from "./api";
import { MAX_HISTORIAL, MAX_MENSAJE, type Tutor } from "./contrato";

/** Largo máximo de cada mensaje del historial que acepta el backend. */
const MAX_TEXTO_HISTORIAL = 4000;

export const tutorRemoto: Tutor = async (entrada, contexto) => {
  const respuesta = await enviarMensaje({
    mensaje: entrada.texto.slice(0, MAX_MENSAJE),
    imagen_base64: entrada.fotoBase64,
    historial: contexto.historial.slice(-MAX_HISTORIAL).map((m) => ({
      autor: m.autor,
      texto: m.texto.slice(0, MAX_TEXTO_HISTORIAL),
      pista: m.pista ?? null,
    })),
    contexto: {
      enunciado: contexto.enunciado?.slice(0, MAX_MENSAJE) ?? null,
      pistas_dadas: contexto.pistasDadas,
    },
  });
  return {
    texto: respuesta.texto,
    pista: respuesta.pista ?? undefined,
    anotaciones: respuesta.anotaciones,
  };
};
