/**
 * Sesión anónima del estudiante.
 *
 * Es solo un identificador al azar que da el backend cuando se acepta el aviso
 * de entrada. Se guarda en este navegador y sirve para contar los mensajes del
 * día. No identifica a la persona.
 */

import { crearSesion } from "./api";

const CLAVE = "maestro-sesion";

function leer(): string | null {
  try {
    return localStorage.getItem(CLAVE);
  } catch {
    return null;
  }
}

function guardar(id: string): void {
  try {
    localStorage.setItem(CLAVE, id);
  } catch {
    // Sin localStorage: la sesión vale mientras la página esté abierta.
  }
}

let enMemoria: string | null = null;
let pidiendo: Promise<string> | null = null;

async function pedirNueva(): Promise<string> {
  // Si se piden dos a la vez (por ejemplo, dos mensajes seguidos), se comparte el mismo pedido.
  pidiendo ??= crearSesion({ acepto_aviso: true })
    .then(({ sesion_id }) => {
      enMemoria = sesion_id;
      guardar(sesion_id);
      return sesion_id;
    })
    .finally(() => {
      pidiendo = null;
    });
  return pidiendo;
}

/** La sesión de este navegador; si no hay una, la crea. */
export async function obtenerSesion(): Promise<string> {
  return enMemoria ?? leer() ?? pedirNueva();
}

/** Crea una sesión nueva, para cuando el backend dice que la anterior ya no vale. */
export async function renovarSesion(): Promise<string> {
  enMemoria = null;
  try {
    localStorage.removeItem(CLAVE);
  } catch {
    // Sin localStorage: no hay nada que borrar.
  }
  return pedirNueva();
}
