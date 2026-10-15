"use client";

import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { MAX_MENSAJE } from "@/lib/contrato";
import { IconoBrujula, IconoCamara, IconoCandado, IconoEnviar, IconoLapiz } from "./Iconos";

const ATAJOS = [
  { texto: "No sé por dónde empezar", Icono: IconoBrujula },
  { texto: "Dame una pista", Icono: IconoLapiz },
  { texto: "Decime la respuesta", Icono: IconoCandado },
];

type Props = {
  ocupado: boolean;
  /** Sin mensajes por hoy: no se puede ni escribir. */
  bloqueado?: boolean;
  /** Los atajos solo tienen sentido cuando ya hay un problema en la pizarra. */
  conAtajos: boolean;
  placeholder: string;
  onEnviar: (texto: string) => void;
  onFoto: (archivo: File) => void;
};

/** Atajos, botón de cámara, campo de texto y botón "Enviar". */
export default function Redactor({ ocupado, bloqueado = false, conAtajos, placeholder, onEnviar, onFoto }: Props) {
  const [texto, setTexto] = useState("");
  const campo = useRef<HTMLTextAreaElement>(null);
  const idCampo = useId();
  const idFoto = useId();

  // Al abrir un chat, el cursor queda listo para escribir (solo con teclado físico).
  useEffect(() => {
    if (window.matchMedia("(pointer: fine)").matches) campo.current?.focus();
  }, [placeholder]);

  function ajustarAltura() {
    const el = campo.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }

  function enviar(evento?: FormEvent) {
    evento?.preventDefault();
    const limpio = texto.trim();
    if (!limpio || ocupado) return;
    onEnviar(limpio);
    setTexto("");
    requestAnimationFrame(ajustarAltura);
  }

  // Enter envía; Shift+Enter hace un salto de línea.
  function alPresionar(evento: KeyboardEvent<HTMLTextAreaElement>) {
    if (evento.key === "Enter" && !evento.shiftKey) {
      evento.preventDefault();
      enviar();
    }
  }

  return (
    <form className="redactor" onSubmit={enviar}>
      {conAtajos && (
        <ul className="atajos" aria-label="Atajos">
          {ATAJOS.map(({ texto: atajo, Icono }) => (
            <li key={atajo}>
              <button type="button" className="atajo" disabled={ocupado} onClick={() => onEnviar(atajo)}>
                <Icono className="icono" />
                {atajo}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="redactor-caja">
        <label htmlFor={idCampo} className="solo-lectores">
          Tu mensaje para MAEstro
        </label>
        <textarea
          ref={campo}
          id={idCampo}
          className="campo"
          rows={1}
          disabled={bloqueado}
          maxLength={MAX_MENSAJE}
          value={texto}
          placeholder={placeholder}
          onChange={(e) => {
            setTexto(e.target.value);
            ajustarAltura();
          }}
          onKeyDown={alPresionar}
        />
        <div className="redactor-fila">
          <input
            id={idFoto}
            type="file"
            accept="image/*"
            className="solo-lectores entrada-archivo"
            disabled={ocupado}
            onChange={(e) => {
              const archivo = e.target.files?.[0];
              if (archivo) onFoto(archivo);
              e.target.value = "";
            }}
          />
          <label htmlFor={idFoto} className="boton-icono" title="Mandar una foto del cuaderno">
            <IconoCamara />
            <span className="solo-lectores">Mandar una foto del cuaderno</span>
          </label>
          <span className="redactor-nota">Enter para enviar · Shift+Enter para otra línea</span>
          <button type="submit" className="boton boton-principal brillo" disabled={ocupado || !texto.trim()}>
            {ocupado && !bloqueado ? <span className="spinner" aria-hidden="true" /> : <IconoEnviar />}
            Enviar
          </button>
        </div>
      </div>
    </form>
  );
}
