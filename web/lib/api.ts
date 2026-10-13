/**
 * Funciones para hablar con el backend de MAEstro.
 * La URL base sale de NEXT_PUBLIC_API_URL (por defecto http://localhost:8100).
 */

import type { ChatEntradaApi, ChatSalidaApi } from "./contrato";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100";

export type Ejercicio = {
  id: string;
  tema: string;
  area: string;
  enunciado: string;
  opciones: string[];
};

async function pedir<T>(ruta: string, opciones?: RequestInit): Promise<T> {
  const respuesta = await fetch(`${API_URL}${ruta}`, {
    headers: { "Content-Type": "application/json" },
    ...opciones,
  });
  if (!respuesta.ok) {
    throw new Error(`Error ${respuesta.status} al llamar ${ruta}`);
  }
  return respuesta.json() as Promise<T>;
}

/** GET /api/salud — indica si el backend está en línea. */
export function revisarSalud(): Promise<{ ok: boolean }> {
  return pedir("/api/salud");
}

/** GET /api/ejercicios — lista de ejercicios sin solución. */
export function obtenerEjercicios(): Promise<Ejercicio[]> {
  return pedir("/api/ejercicios");
}

/** POST /api/sesiones — abre una sesión anónima después de aceptar el aviso. */
export function crearSesion(datos: { acepto_aviso: boolean }): Promise<{ ok: boolean }> {
  return pedir("/api/sesiones", { method: "POST", body: JSON.stringify(datos) });
}

/** POST /api/chat — envía el mensaje (y opcionalmente una foto) con su historial y contexto. */
export function enviarMensaje(datos: ChatEntradaApi): Promise<ChatSalidaApi> {
  return pedir("/api/chat", { method: "POST", body: JSON.stringify(datos) });
}
