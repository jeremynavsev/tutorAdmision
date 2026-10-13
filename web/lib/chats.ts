/**
 * Historial de chats de MAEstro.
 *
 * Por ahora se guarda solo en este navegador (localStorage). No se guardan las
 * fotos, solo una marca de que se mandó una. Cuando exista el backend, este
 * módulo es el que cambia por llamadas a la API.
 */

import type { Anotacion } from "./contrato";

export type Mensaje = {
  id: string;
  autor: "tutor" | "estudiante";
  texto: string;
  pista?: 1 | 2 | 3;
  foto?: boolean;
};

/** Anotación con un número de orden, para saber cuáles son nuevas y animarlas. */
export type AnotacionNumerada = Anotacion & { n: number };

export type Chat = {
  id: string;
  titulo: string;
  actualizado: number;
  mensajes: Mensaje[];
  anotaciones: AnotacionNumerada[];
};

const CLAVE = "maestro-chats";

export function nuevoId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function cargarChats(): Chat[] {
  try {
    const crudo = localStorage.getItem(CLAVE);
    const chats = crudo ? (JSON.parse(crudo) as Chat[]) : [];
    return Array.isArray(chats) ? chats : [];
  } catch {
    return [];
  }
}

export function guardarChats(chats: Chat[]): void {
  try {
    localStorage.setItem(CLAVE, JSON.stringify(chats));
  } catch {
    // Sin localStorage o sin espacio: el chat sigue funcionando, solo no se guarda.
  }
}

/** Título a partir del primer mensaje: las primeras palabras, sin cortar a media palabra. */
export function tituloDesde(texto: string): string {
  const limpio = texto.replace(/\s+/g, " ").trim();
  if (limpio.length <= 42) return limpio || "Chat nuevo";
  return `${limpio.slice(0, 42).replace(/\s+\S*$/, "")}…`;
}

export type Grupo = { nombre: string; chats: Chat[] };

/** Agrupa los chats como los agentes: Hoy, Ayer, Últimos 7 días y Antes. */
export function agruparPorFecha(chats: Chat[], ahora = new Date()): Grupo[] {
  const inicioHoy = new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate()).getTime();
  const dia = 86_400_000;
  const grupos: Grupo[] = [
    { nombre: "Hoy", chats: [] },
    { nombre: "Ayer", chats: [] },
    { nombre: "Últimos 7 días", chats: [] },
    { nombre: "Antes", chats: [] },
  ];
  for (const chat of [...chats].sort((a, b) => b.actualizado - a.actualizado)) {
    const i =
      chat.actualizado >= inicioHoy ? 0 : chat.actualizado >= inicioHoy - dia ? 1 : chat.actualizado >= inicioHoy - 7 * dia ? 2 : 3;
    grupos[i].chats.push(chat);
  }
  return grupos.filter((g) => g.chats.length > 0);
}
