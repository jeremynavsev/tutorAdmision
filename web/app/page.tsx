"use client";

import { useCallback, useEffect, useState } from "react";
import AvisoEntrada from "@/components/AvisoEntrada";
import BarraLateral from "@/components/BarraLateral";
import Bienvenida from "@/components/Bienvenida";
import Conversacion from "@/components/Conversacion";
import { IconoMenu, IconoNuevo, IconoPizarra } from "@/components/Iconos";
import Pizarra from "@/components/Pizarra";
import Redactor from "@/components/Redactor";
import Toasts, { type Toast } from "@/components/Toasts";
import { cargarChats, guardarChats, nuevoId, tituloDesde, type Chat, type Mensaje } from "@/lib/chats";
import { ErrorDeFoto, prepararFoto } from "@/lib/fotos";
import { guardarBandera, leerBandera } from "@/lib/tema";
import { MAX_HISTORIAL, type Contexto, type EntradaTutor, type RespuestaTutor, type Tutor } from "@/lib/contrato";
import { tutorRemoto } from "@/lib/tutorRemoto";
import { tutorSimulado } from "@/lib/tutorSimulado";

// El tutor real habla con el backend. Con NEXT_PUBLIC_TUTOR=simulado se usa el de
// mentiras, que sirve para mostrar la interfaz sin backend ni cuota de IA.
const tutor: Tutor = process.env.NEXT_PUBLIC_TUTOR === "simulado" ? tutorSimulado : tutorRemoto;
const MENSAJE_DE_ERROR = "Algo salió mal. Probá de nuevo en un ratito.";

const CLAVE_AVISO = "maestro-aviso-aceptado";
const SIN_ANOTACIONES: Chat["anotaciones"] = [];
const ANCHO_LATERAL_FIJA = "(min-width: 920px)";
const ANCHO_PIZARRA_FIJA = "(min-width: 1180px)";

const coincide = (consulta: string) => typeof window !== "undefined" && window.matchMedia(consulta).matches;

function contextoDe(chat: Chat | undefined): Contexto {
  const enunciado = chat ? [...chat.anotaciones].reverse().find((a) => a.tipo === "enunciado") : undefined;
  return {
    enunciado: enunciado?.tipo === "enunciado" ? enunciado.texto : null,
    pistasDadas: chat ? chat.mensajes.filter((m) => m.pista).length : 0,
    // Los últimos mensajes; las fotos viajan solo una vez, aquí quedan como una nota.
    historial: (chat?.mensajes ?? []).slice(-MAX_HISTORIAL).map((m) => ({
      autor: m.autor,
      texto: m.texto || (m.foto ? "[El estudiante mandó una foto del cuaderno]" : ""),
      pista: m.pista,
    })),
  };
}

/** Para comparar apuntes: "-5 + 20 = 15" y "-5+20 = 15" son el mismo. */
const sinEspacios = (texto: string) => texto.replace(/\s+/g, "").toLowerCase();

export default function Inicio() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [cargado, setCargado] = useState(false);
  const [activoId, setActivoId] = useState<string | null>(null);
  const [lateralAbierta, setLateralAbierta] = useState(false);
  const [pizarraAbierta, setPizarraAbierta] = useState(false);
  const [pizarraNueva, setPizarraNueva] = useState(false);
  const [pensandoEn, setPensandoEn] = useState<string | null>(null);
  const [animar, setAnimar] = useState<Set<string>>(new Set());
  const [fotos, setFotos] = useState<Record<string, string>>({});
  const [aviso, setAviso] = useState({ abierto: false, obligatorio: false });
  const [toasts, setToasts] = useState<Toast[]>([]);

  // Al cargar: historial, menú abierto en pantalla ancha y aviso en la primera visita.
  useEffect(() => {
    setChats(cargarChats());
    setCargado(true);
    setLateralAbierta(coincide(ANCHO_LATERAL_FIJA));
    if (!leerBandera(CLAVE_AVISO)) setAviso({ abierto: true, obligatorio: true });
  }, []);

  useEffect(() => {
    if (cargado) guardarChats(chats);
  }, [chats, cargado]);

  // Escape cierra lo que esté encima de la conversación en pantallas angostas.
  useEffect(() => {
    function alPresionar(e: KeyboardEvent) {
      if (e.key !== "Escape" || aviso.abierto) return;
      if (!coincide(ANCHO_PIZARRA_FIJA)) setPizarraAbierta(false);
      if (!coincide(ANCHO_LATERAL_FIJA)) setLateralAbierta(false);
    }
    document.addEventListener("keydown", alPresionar);
    return () => document.removeEventListener("keydown", alPresionar);
  }, [aviso.abierto]);

  const avisar = useCallback((texto: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, texto }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);

  const activo = chats.find((c) => c.id === activoId);
  const contexto = contextoDe(activo);
  const pensando = pensandoEn !== null && pensandoEn === activoId;

  function actualizarChat(id: string, cambio: (chat: Chat) => Chat) {
    setChats((todos) => todos.map((c) => (c.id === id ? cambio(c) : c)));
  }

  async function conversar(mensaje: Mensaje, entrada: EntradaTutor) {
    // Un chat nuevo se crea con el primer mensaje.
    let id = activoId;
    let chat = activo;
    if (!chat || !id) {
      id = nuevoId();
      chat = {
        id,
        titulo: tituloDesde(mensaje.texto || "Foto del cuaderno"),
        actualizado: Date.now(),
        mensajes: [],
        anotaciones: [],
      };
      const creado = chat;
      setChats((todos) => [creado, ...todos]);
      setActivoId(id);
    }
    const chatId = id;
    const ctx = contextoDe(chat);
    actualizarChat(chatId, (c) => ({ ...c, actualizado: Date.now(), mensajes: [...c.mensajes, mensaje] }));

    setPensandoEn(chatId);
    let respuesta: RespuestaTutor;
    try {
      respuesta = await tutor(entrada, ctx);
    } catch (error) {
      // El mensaje del estudiante se queda en el chat; solo se avisa que no hubo respuesta.
      avisar(error instanceof Error && error.message ? error.message : MENSAJE_DE_ERROR);
      return;
    } finally {
      setPensandoEn(null);
    }

    const idRespuesta = nuevoId();
    setAnimar((a) => new Set(a).add(idRespuesta));
    actualizarChat(chatId, (c) => {
      const base = c.anotaciones.reduce((m, a) => Math.max(m, a.n), 0);
      // El modelo a veces repite un apunte que ya escribió: no se vuelve a poner en la pizarra.
      const escritos = new Set(c.anotaciones.flatMap((a) => (a.tipo === "apunte" ? [sinEspacios(a.texto)] : [])));
      const nuevas = respuesta.anotaciones.filter((a) => {
        if (a.tipo !== "apunte") return true;
        const clave = sinEspacios(a.texto);
        if (escritos.has(clave)) return false;
        escritos.add(clave);
        return true;
      });
      return {
        ...c,
        actualizado: Date.now(),
        mensajes: [...c.mensajes, { id: idRespuesta, autor: "tutor", texto: respuesta.texto, pista: respuesta.pista }],
        anotaciones: [...c.anotaciones, ...nuevas.map((a, i) => ({ ...a, n: base + i + 1 }))],
      };
    });

    // Si el tutor escribió en la pizarra: se abre sola en pantalla ancha; en celular se avisa con un punto.
    if (respuesta.anotaciones.length > 0) {
      if (coincide(ANCHO_PIZARRA_FIJA)) setPizarraAbierta(true);
      else setPizarraNueva(true);
    }
  }

  function enviarTexto(texto: string) {
    conversar({ id: nuevoId(), autor: "estudiante", texto }, { texto });
  }

  async function enviarFoto(archivo: File) {
    let foto;
    try {
      // Se reduce y se endereza en el navegador: gasta menos datos y no salen los metadatos.
      foto = await prepararFoto(archivo);
    } catch (error) {
      avisar(error instanceof ErrorDeFoto ? error.message : "No se pudo preparar la foto. Probá con otra.");
      return;
    }
    const id = nuevoId();
    setFotos((f) => ({ ...f, [id]: foto.url }));
    conversar({ id, autor: "estudiante", texto: "", foto: true }, { texto: "", fotoBase64: foto.base64 });
  }

  function cerrarLateralEnCelular() {
    if (!coincide(ANCHO_LATERAL_FIJA)) setLateralAbierta(false);
  }

  function chatNuevo() {
    setActivoId(null);
    setPizarraNueva(false);
    if (!coincide(ANCHO_PIZARRA_FIJA)) setPizarraAbierta(false);
    cerrarLateralEnCelular();
  }

  function elegirChat(id: string) {
    setActivoId(id);
    setPizarraNueva(false);
    if (!coincide(ANCHO_PIZARRA_FIJA)) setPizarraAbierta(false);
    else setPizarraAbierta(chats.find((c) => c.id === id)?.anotaciones.length !== 0);
    cerrarLateralEnCelular();
  }

  function eliminarChat(id: string) {
    setChats((todos) => todos.filter((c) => c.id !== id));
    if (id === activoId) setActivoId(null);
    avisar("Chat eliminado.");
  }

  function alternarPizarra() {
    setPizarraAbierta((a) => !a);
    setPizarraNueva(false);
  }

  function aceptarAviso() {
    const primeraVez = aviso.obligatorio;
    setAviso({ abierto: false, obligatorio: false });
    if (primeraVez) {
      guardarBandera(CLAVE_AVISO);
      avisar("¡Listo! Mandame el problema cuando querás.");
    }
  }

  const vacio = !activo || activo.mensajes.length === 0;

  return (
    <div className={`app ${lateralAbierta ? "con-lateral" : "sin-lateral"} ${pizarraAbierta ? "con-pizarra" : ""}`}>
      <BarraLateral
        chats={chats}
        activoId={activoId}
        abierta={lateralAbierta}
        onAlternar={() => setLateralAbierta((a) => !a)}
        onNuevo={chatNuevo}
        onElegir={elegirChat}
        onEliminar={eliminarChat}
        onVerAviso={() => setAviso({ abierto: true, obligatorio: false })}
      />

      <main className="chat">
        <header className="chat-barra">
          <button
            type="button"
            className="boton-icono chat-menu"
            onClick={() => setLateralAbierta(true)}
            aria-label="Abrir el menú de chats"
            title="Abrir menú"
          >
            <IconoMenu />
          </button>
          <h1 className="chat-titulo">{activo?.titulo ?? "Chat nuevo"}</h1>
          <button type="button" className="boton-icono chat-nuevo" onClick={chatNuevo} aria-label="Chat nuevo" title="Chat nuevo">
            <IconoNuevo />
          </button>
          <button
            type="button"
            className={`boton-pizarra ${pizarraAbierta ? "boton-pizarra-activo" : ""}`}
            onClick={alternarPizarra}
            aria-pressed={pizarraAbierta}
            title={pizarraAbierta ? "Cerrar la pizarra" : "Abrir la pizarra"}
          >
            <IconoPizarra />
            <span>Pizarra</span>
            {pizarraNueva && <span className="punto-nuevo" aria-label="(tiene algo nuevo)" />}
          </button>
        </header>

        <div className={`chat-cuerpo ${vacio ? "chat-vacio" : ""}`}>
          {vacio ? (
            <Bienvenida />
          ) : (
            <Conversacion
              mensajes={activo.mensajes}
              pensando={pensando}
              animar={animar}
              fotos={fotos}
            />
          )}
          <Redactor
            ocupado={pensando}
            conAtajos={contexto.enunciado !== null}
            placeholder={vacio ? "Escribí o pegá el problema que querés resolver…" : "Escribí cómo lo estás pensando…"}
            onEnviar={enviarTexto}
            onFoto={enviarFoto}
          />
        </div>
      </main>

      <div className="velo-pizarra" onClick={() => setPizarraAbierta(false)} aria-hidden="true" />
      <Pizarra
        key={activoId ?? "nuevo"}
        anotaciones={activo?.anotaciones ?? SIN_ANOTACIONES}
        visible={pizarraAbierta}
        onCerrar={() => setPizarraAbierta(false)}
      />

      <AvisoEntrada abierto={aviso.abierto} obligatorio={aviso.obligatorio} onAceptar={aceptarAviso} />
      <Toasts toasts={toasts} onCerrar={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />
    </div>
  );
}
