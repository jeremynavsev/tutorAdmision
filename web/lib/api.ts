/**
 * Funciones para hablar con el backend de MAEstro.
 * La URL base sale de NEXT_PUBLIC_API_URL (por defecto http://localhost:8100).
 */

import type { ChatEntradaApi, ChatSalidaApi } from "./contrato";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100";

/** Segundos máximos de espera: una foto puede pasar por varios proveedores antes de responder. */
const TIEMPO_MAXIMO_MS = 90_000;

/** Error al hablar con el backend. `message` ya es un texto que se le puede mostrar al estudiante. */
export class ErrorDeApi extends Error {
  constructor(
    mensaje: string,
    /** Código HTTP, o 0 si no hubo respuesta (sin conexión, backend apagado o tiempo agotado). */
    public readonly estado: number,
  ) {
    super(mensaje);
    this.name = "ErrorDeApi";
  }
}

const MENSAJE_SIN_CONEXION = "No hay conexión con el tutor. Revisá tu internet y probá de nuevo.";
const MENSAJE_GENERICO = "Algo salió mal. Probá de nuevo en un ratito.";

async function pedirConEncabezados<T>(ruta: string, opciones?: RequestInit): Promise<{ datos: T; encabezados: Headers }> {
  let respuesta: Response;
  try {
    respuesta = await fetch(`${API_URL}${ruta}`, {
      headers: { "Content-Type": "application/json" },
      signal: AbortSignal.timeout(TIEMPO_MAXIMO_MS),
      ...opciones,
    });
  } catch {
    throw new ErrorDeApi(MENSAJE_SIN_CONEXION, 0);
  }
  if (!respuesta.ok) {
    // El backend manda en `detail` un mensaje pensado para el estudiante (400, 401, 429 y 503).
    // En un 422 (datos que no cumplen el contrato) `detail` es una lista técnica: no se muestra.
    let detalle: unknown;
    try {
      detalle = (await respuesta.json()).detail;
    } catch {
      detalle = undefined;
    }
    throw new ErrorDeApi(typeof detalle === "string" && detalle ? detalle : MENSAJE_GENERICO, respuesta.status);
  }
  return { datos: (await respuesta.json()) as T, encabezados: respuesta.headers };
}

async function pedir<T>(ruta: string, opciones?: RequestInit): Promise<T> {
  return (await pedirConEncabezados<T>(ruta, opciones)).datos;
}

/** GET /api/salud — indica si el backend está en línea. */
export function revisarSalud(): Promise<{ ok: boolean }> {
  return pedir("/api/salud");
}

/** POST /api/sesiones — crea la sesión anónima después de aceptar el aviso. */
export function crearSesion(datos: { acepto_aviso: boolean }): Promise<{ sesion_id: string }> {
  return pedir("/api/sesiones", { method: "POST", body: JSON.stringify(datos) });
}

/**
 * POST /api/chat — envía el mensaje (y opcionalmente una foto) con su historial y contexto.
 * Devuelve también cuántos mensajes le quedan hoy al estudiante.
 */
export async function enviarMensaje(datos: ChatEntradaApi): Promise<{ salida: ChatSalidaApi; restantes: number | null }> {
  const { datos: salida, encabezados } = await pedirConEncabezados<ChatSalidaApi>("/api/chat", {
    method: "POST",
    body: JSON.stringify(datos),
  });
  const restantes = encabezados.get("X-Mensajes-Restantes");
  return { salida, restantes: restantes === null ? null : Number(restantes) };
}
