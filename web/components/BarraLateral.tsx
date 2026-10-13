"use client";

import { agruparPorFecha, type Chat } from "@/lib/chats";
import BotonTema from "./BotonTema";
import { IconoAviso, IconoBasura, IconoNuevo, IconoPanel } from "./Iconos";
import Logo from "./Logo";

type Props = {
  chats: Chat[];
  activoId: string | null;
  abierta: boolean;
  onAlternar: () => void;
  onNuevo: () => void;
  onElegir: (id: string) => void;
  onEliminar: (id: string) => void;
  onVerAviso: () => void;
};

/**
 * Menú desplegable de los chats, como en los agentes: botón de chat nuevo,
 * historial agrupado por fecha y, abajo, el tema y el aviso de entrada.
 * En pantalla ancha se encoge a una franja de íconos; en celular se desliza
 * por encima de la conversación.
 */
export default function BarraLateral({ chats, activoId, abierta, onAlternar, onNuevo, onElegir, onEliminar, onVerAviso }: Props) {
  const grupos = agruparPorFecha(chats);

  return (
    <>
      <div className="velo-lateral" onClick={onAlternar} aria-hidden="true" />
      <nav className="lateral" aria-label="Chats">
        <div className="lateral-cabeza">
          <span className="lateral-logo">
            <Logo ancho={116} />
          </span>
          <button
            type="button"
            className="boton-icono"
            onClick={onAlternar}
            aria-label={abierta ? "Cerrar el menú de chats" : "Abrir el menú de chats"}
            aria-expanded={abierta}
            title={abierta ? "Cerrar menú" : "Abrir menú"}
          >
            <IconoPanel />
          </button>
        </div>

        <button type="button" className="lateral-accion lateral-nuevo" onClick={onNuevo} title="Chat nuevo">
          <IconoNuevo />
          <span className="lateral-texto">Chat nuevo</span>
        </button>

        <div className="lateral-lista">
          {grupos.length === 0 ? (
            <p className="lateral-vacio lateral-texto">Tus chats van a aparecer aquí.</p>
          ) : (
            grupos.map((grupo) => (
              <section key={grupo.nombre} className="lateral-grupo" aria-label={grupo.nombre}>
                <h2 className="lateral-grupo-titulo">{grupo.nombre}</h2>
                <ul>
                  {grupo.chats.map((chat) => (
                    <li key={chat.id} className={`lateral-chat ${chat.id === activoId ? "lateral-chat-activo" : ""}`}>
                      <button
                        type="button"
                        className="lateral-chat-abrir"
                        onClick={() => onElegir(chat.id)}
                        aria-current={chat.id === activoId ? "page" : undefined}
                      >
                        {chat.titulo}
                      </button>
                      <button
                        type="button"
                        className="lateral-chat-eliminar"
                        onClick={() => onEliminar(chat.id)}
                        aria-label={`Eliminar el chat «${chat.titulo}»`}
                        title="Eliminar chat"
                      >
                        <IconoBasura />
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ))
          )}
        </div>

        <div className="lateral-pie">
          <button type="button" className="lateral-accion" onClick={onVerAviso} title="Aviso de entrada">
            <IconoAviso />
            <span className="lateral-texto">Aviso de entrada</span>
          </button>
          <BotonTema className="lateral-accion" />
        </div>
      </nav>
    </>
  );
}
