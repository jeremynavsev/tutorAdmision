"use client";

import { IconoAlerta, IconoCerrar, IconoListo } from "./Iconos";

export type Toast = { id: number; texto: string; tipo: "ok" | "error" };

/** Avisos cortos que entran desde la derecha y se van solos: confirmaciones y errores. */
export default function Toasts({ toasts, onCerrar }: { toasts: Toast[]; onCerrar: (id: number) => void }) {
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        // Un error se anuncia de inmediato a los lectores de pantalla (role="alert").
        <div key={t.id} className={`toast ${t.tipo === "error" ? "toast-error" : ""}`} role={t.tipo === "error" ? "alert" : undefined}>
          {t.tipo === "error" ? <IconoAlerta /> : <IconoListo />}
          <p>{t.texto}</p>
          <button type="button" className="boton-icono" onClick={() => onCerrar(t.id)} aria-label="Cerrar aviso">
            <IconoCerrar className="icono" />
          </button>
        </div>
      ))}
    </div>
  );
}
