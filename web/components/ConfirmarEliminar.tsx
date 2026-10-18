"use client";

import { useEffect, useRef } from "react";

type Props = {
  /** Título del chat que se quiere eliminar; null si el diálogo está cerrado. */
  titulo: string | null;
  onConfirmar: () => void;
  onCancelar: () => void;
};

/**
 * Pide confirmación antes de eliminar un chat: se borra de este dispositivo y no
 * se puede recuperar. El foco empieza en "Cancelar", para que un Enter sin querer
 * no borre nada.
 */
export default function ConfirmarEliminar({ titulo, onConfirmar, onCancelar }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const abierto = titulo !== null;

  useEffect(() => {
    const el = dialogo.current;
    if (!el) return;
    if (abierto && !el.open) el.showModal();
    if (!abierto && el.open) el.close();
  }, [abierto]);

  return (
    <dialog
      ref={dialogo}
      className="dialogo"
      aria-labelledby="titulo-eliminar"
      aria-describedby="detalle-eliminar"
      onCancel={(e) => {
        e.preventDefault();
        onCancelar();
      }}
    >
      <div className="dialogo-contenido">
        <h2 id="titulo-eliminar">¿Eliminar este chat?</h2>
        <p id="detalle-eliminar">
          Vas a eliminar <strong>«{titulo}»</strong>. Se borra de este dispositivo con su pizarra y no se puede
          recuperar.
        </p>
        <div className="dialogo-botones">
          <button type="button" className="boton boton-secundario" onClick={onCancelar} autoFocus>
            Cancelar
          </button>
          <button type="button" className="boton boton-peligro" onClick={onConfirmar}>
            Sí, eliminar
          </button>
        </div>
      </div>
    </dialog>
  );
}
