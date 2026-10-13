"use client";

import { IconoCerrar, IconoListo } from "./Iconos";

export type Toast = { id: number; texto: string };

/** Confirmaciones cortas que entran desde la derecha y se van solas. */
export default function Toasts({ toasts, onCerrar }: { toasts: Toast[]; onCerrar: (id: number) => void }) {
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className="toast">
          <IconoListo />
          <p>{t.texto}</p>
          <button type="button" className="boton-icono" onClick={() => onCerrar(t.id)} aria-label="Cerrar aviso">
            <IconoCerrar className="icono" />
          </button>
        </div>
      ))}
    </div>
  );
}
