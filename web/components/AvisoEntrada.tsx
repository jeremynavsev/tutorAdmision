"use client";

import { useEffect, useRef } from "react";
import Logo from "./Logo";

type Props = {
  abierto: boolean;
  /** La primera vez hay que aceptar: Escape no lo cierra. */
  obligatorio: boolean;
  onAceptar: () => void;
};

/** Aviso de entrada en un <dialog> modal con el fondo desenfocado. */
export default function AvisoEntrada({ abierto, obligatorio, onAceptar }: Props) {
  const dialogo = useRef<HTMLDialogElement>(null);

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
      aria-labelledby="titulo-aviso"
      onCancel={(e) => {
        e.preventDefault();
        if (!obligatorio) onAceptar();
      }}
    >
      <div className="dialogo-contenido">
        <Logo ancho={150} />
        <h2 id="titulo-aviso">Antes de practicar</h2>
        <p>
          MAEstro es un tutor de inteligencia artificial gratuito para preparar las pruebas de admisión de la UCR,
          la UNA y el TEC.
        </p>
        <ul>
          <li>No te da la respuesta: te hace preguntas y te da pistas para que llegués vos.</li>
          <li>Traé tu propio problema: escribilo o mandá una foto de tu cuaderno.</li>
          <li>Tus chats se guardan solo en este dispositivo.</li>
          <li>Es una herramienta de práctica y puede equivocarse. Revisá siempre tu trabajo.</li>
        </ul>
        <p className="dialogo-cuidado">
          <strong>No compartás datos personales:</strong> nombre completo, cédula, teléfono, dirección ni fotos de
          tu cara.
        </p>
        <button type="button" className="boton boton-principal brillo" onClick={onAceptar} autoFocus>
          Acepto y quiero practicar
        </button>
      </div>
    </dialog>
  );
}
