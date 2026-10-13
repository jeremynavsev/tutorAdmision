/**
 * Contrato del tutor de MAEstro.
 *
 * Es lo mismo que define el backend en backend/app/esquemas.py (POST /api/chat).
 * Si cambia allá, cambia aquí. La interfaz solo conoce el tipo `Tutor`: hoy lo
 * cumple el tutor simulado y después lo cumplirá la llamada real al backend.
 */

/** Lo que el tutor le pide a la pizarra que dibuje. */
export type Anotacion =
  /** Copia el problema en la pizarra. */
  | { tipo: "enunciado"; texto: string }
  /** Encierra en un círculo un dato que aparece tal cual en el enunciado. */
  | { tipo: "circulo"; dato: string }
  /** Escribe una línea con tiza en la zona de apuntes. */
  | { tipo: "apunte"; texto: string };

export type NumeroPista = 1 | 2 | 3;

/** Un mensaje anterior de la conversación. */
export type MensajeHistorial = { autor: "estudiante" | "tutor"; texto: string; pista?: NumeroPista };

export type EntradaTutor = {
  texto: string;
  /** Foto del cuaderno en base64 (sin el prefijo data:). */
  fotoBase64?: string;
};

export type Contexto = {
  /** Problema que ya está en la pizarra, si hay. */
  enunciado: string | null;
  /** Pistas que ya se dieron en esta conversación. */
  pistasDadas: number;
  /** Mensajes anteriores, del más viejo al más nuevo (sin el mensaje actual). */
  historial: MensajeHistorial[];
};

export type RespuestaTutor = {
  texto: string;
  pista?: NumeroPista;
  anotaciones: Anotacion[];
};

export type Tutor = (entrada: EntradaTutor, contexto: Contexto) => Promise<RespuestaTutor>;

// ---------- Forma exacta en que viaja por la red (snake_case, como en Python) ----------

export type ChatEntradaApi = {
  sesion_id?: string;
  mensaje: string;
  imagen_base64?: string;
  historial: { autor: "estudiante" | "tutor"; texto: string; pista: NumeroPista | null }[];
  contexto: { enunciado: string | null; pistas_dadas: number };
};

export type ChatSalidaApi = {
  texto: string;
  pista: NumeroPista | null;
  anotaciones: Anotacion[];
  proveedor: string;
};

/** Límites que también valida el backend. */
export const MAX_MENSAJE = 2000;
export const MAX_HISTORIAL = 40;
