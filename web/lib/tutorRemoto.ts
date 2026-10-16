/**
 * Tutor REAL de MAEstro: le pasa el mensaje al backend (POST /api/chat), que es
 * el que consulta a la IA.
 *
 * Cumple el mismo tipo `Tutor` que el simulado; solo traduce entre los nombres
 * del frontend (camelCase) y los del backend (snake_case). Si algo falla lanza
 * un `ErrorDeApi`, cuyo mensaje ya está pensado para mostrárselo al estudiante.
 *
 * Cada mensaje lleva la sesión anónima del estudiante. Si el backend dice que ya
 * no vale (401), se crea otra y se reintenta una vez, sin que el estudiante lo note.
 */

import { ErrorDeApi, enviarMensaje } from "./api";
import { MAX_HISTORIAL, MAX_MENSAJE, type ChatEntradaApi, type Tutor } from "./contrato";
import { obtenerSesion, renovarSesion } from "./sesion";

/** Largo máximo de cada mensaje del historial que acepta el backend. */
const MAX_TEXTO_HISTORIAL = 4000;

export const tutorRemoto: Tutor = async (entrada, contexto) => {
  const datos: Omit<ChatEntradaApi, "sesion_id"> = {
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
  };

  let respuesta;
  try {
    respuesta = await enviarMensaje({ ...datos, sesion_id: await obtenerSesion() });
  } catch (error) {
    if (!(error instanceof ErrorDeApi && error.estado === 401)) throw error;
    respuesta = await enviarMensaje({ ...datos, sesion_id: await renovarSesion() });
  }
  const { salida, restantes } = respuesta;
  return {
    texto: salida.texto,
    pista: salida.pista ?? undefined,
    anotaciones: salida.anotaciones,
    restantes: restantes ?? undefined,
  };
};
