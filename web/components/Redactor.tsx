"use client";

import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { MAX_MENSAJE } from "@/lib/contrato";
import { NOMBRES_DE_DATOS, encontrarDatos, ocultarDatos, type TipoDato } from "@/lib/privacidad";
import { IconoBrujula, IconoCamara, IconoCandado, IconoFlechaArriba, IconoLapiz, IconoMas } from "./Iconos";

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

/** Atajos, campo de texto, menú "+" (foto del cuaderno) y botón de enviar. */
export default function Redactor({ ocupado, bloqueado = false, conAtajos, placeholder, onEnviar, onFoto }: Props) {
  const [texto, setTexto] = useState("");
  // Datos personales que se encontraron al intentar enviar (para preguntar antes).
  const [datosEncontrados, setDatosEncontrados] = useState<TipoDato[] | null>(null);
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [presionado, setPresionado] = useState(false);
  const campo = useRef<HTMLTextAreaElement>(null);
  const caja = useRef<HTMLDivElement>(null);
  const entradaFoto = useRef<HTMLInputElement>(null);
  const idCampo = useId();
  const idMenu = useId();

  // Al abrir un chat, el cursor queda listo para escribir (solo con teclado físico).
  useEffect(() => {
    if (window.matchMedia("(pointer: fine)").matches) campo.current?.focus();
  }, [placeholder]);

  // El menú "+" se cierra al tocar fuera de la caja o con Escape.
  useEffect(() => {
    if (!menuAbierto) return;
    const alTocar = (e: PointerEvent) => {
      if (!caja.current?.contains(e.target as Node)) setMenuAbierto(false);
    };
    const alTeclear = (e: globalThis.KeyboardEvent) => {
      if (e.key === "Escape") setMenuAbierto(false);
    };
    document.addEventListener("pointerdown", alTocar);
    document.addEventListener("keydown", alTeclear);
    return () => {
      document.removeEventListener("pointerdown", alTocar);
      document.removeEventListener("keydown", alTeclear);
    };
  }, [menuAbierto]);

  function elegirFoto() {
    setMenuAbierto(false);
    entradaFoto.current?.click();
  }

  function ajustarAltura() {
    const el = campo.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }

  function mandar(contenido: string) {
    onEnviar(contenido);
    setTexto("");
    setDatosEncontrados(null);
    requestAnimationFrame(ajustarAltura);
  }

  function enviar(evento?: FormEvent) {
    evento?.preventDefault();
    const limpio = texto.trim();
    if (!limpio || ocupado) return;
    // Si el mensaje trae un dato personal, primero se pregunta.
    const datos = [...new Set(encontrarDatos(limpio).map((h) => h.tipo))];
    if (datos.length > 0) {
      setDatosEncontrados(datos);
      return;
    }
    mandar(limpio);
  }

  function editar() {
    setDatosEncontrados(null);
    campo.current?.focus();
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
      {datosEncontrados && (
        <div className="aviso-datos" role="alert">
          <p>
            Parece que tu mensaje tiene {listar(datosEncontrados.map((t) => NOMBRES_DE_DATOS[t]))}. Para practicar no
            hace falta compartir datos personales.
          </p>
          <div className="aviso-datos-acciones">
            <button type="button" className="boton boton-principal" onClick={() => mandar(ocultarDatos(texto.trim()))}>
              Quitarlo y enviar
            </button>
            <button type="button" className="boton-reintentar" onClick={editar}>
              Editar
            </button>
          </div>
        </div>
      )}
      <div
        ref={caja}
        className="redactor-caja"
        role="presentation"
        onClick={(e) => {
          if (e.target === e.currentTarget) campo.current?.focus();
        }}
      >
        {menuAbierto && (
          <div id={idMenu} className="redactor-menu" role="menu" aria-label="Agregar">
            <button type="button" role="menuitem" className="redactor-menu-fila" autoFocus onClick={elegirFoto}>
              <IconoCamara className="icono redactor-menu-icono" />
              <span className="redactor-menu-nombre">Foto del cuaderno</span>
              <span className="redactor-menu-desc">Desde este dispositivo</span>
            </button>
          </div>
        )}
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
            setDatosEncontrados(null);
            ajustarAltura();
          }}
          onFocus={() => setMenuAbierto(false)}
          onKeyDown={alPresionar}
        />
        <div className="redactor-fila">
          <input
            ref={entradaFoto}
            type="file"
            accept="image/*"
            className="solo-lectores"
            tabIndex={-1}
            aria-hidden="true"
            disabled={ocupado}
            onChange={(e) => {
              const archivo = e.target.files?.[0];
              if (archivo) onFoto(archivo);
              e.target.value = "";
            }}
          />
          <button
            type="button"
            className="redactor-herramienta"
            title="Agregar una foto del cuaderno"
            aria-label="Agregar una foto del cuaderno"
            aria-haspopup="menu"
            aria-expanded={menuAbierto}
            aria-controls={menuAbierto ? idMenu : undefined}
            data-activo={menuAbierto ? "" : undefined}
            disabled={ocupado}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => setMenuAbierto((v) => !v)}
          >
            <IconoMas />
          </button>
          <span className="redactor-nota">Enter para enviar · Shift+Enter para otra línea</span>
          <button
            type="submit"
            className="redactor-enviar"
            aria-label="Enviar"
            title="Enviar"
            disabled={ocupado || !texto.trim()}
            data-listo={texto.trim() || (ocupado && !bloqueado) ? "" : undefined}
            data-presionado={presionado ? "" : undefined}
            onMouseDown={(e) => e.preventDefault()}
            onPointerDown={(e) => e.button === 0 && setPresionado(true)}
            onPointerUp={() => setPresionado(false)}
            onPointerLeave={() => setPresionado(false)}
            onPointerCancel={() => setPresionado(false)}
          >
            {ocupado && !bloqueado ? <span className="spinner" aria-hidden="true" /> : <IconoFlechaArriba />}
          </button>
        </div>
      </div>
    </form>
  );
}

/** "a", "a y b", "a, b y c". */
function listar(cosas: string[]): string {
  return cosas.length <= 1 ? (cosas[0] ?? "") : `${cosas.slice(0, -1).join(", ")} y ${cosas[cosas.length - 1]}`;
}
