"use client";

import { useEffect, useRef, useState } from "react";
import type { Mensaje } from "@/lib/chats";
import { prefiereMenosMovimiento } from "@/lib/tema";
import { CIRCULITO_PISTA } from "@/lib/trazos";

type Props = {
  mensajes: Mensaje[];
  pensando: boolean;
  /** Ids de mensajes del tutor que deben aparecer palabra por palabra. */
  animar: Set<string>;
  /** Fotos de esta sesión (no se guardan en el historial). */
  fotos: Record<string, string>;
};

/** Conversación: el tutor sin burbuja con la etiqueta "MAEstro"; el estudiante en burbuja a la derecha. */
export default function Conversacion({ mensajes, pensando, animar, fotos }: Props) {
  const final = useRef<HTMLLIElement>(null);

  function bajar(suave: boolean) {
    final.current?.scrollIntoView({ behavior: suave && !prefiereMenosMovimiento() ? "smooth" : "auto", block: "end" });
  }

  useEffect(() => {
    bajar(true);
  }, [mensajes.length, pensando]);

  return (
    <ol className="conversacion" aria-live="polite" aria-label="Conversación con MAEstro">
      {mensajes.map((m) =>
        m.autor === "tutor" ? (
          <li key={m.id} className="mensaje mensaje-tutor">
            <p className="autor">
              MAEstro
              {m.pista && <SelloPista numero={m.pista} animar={animar.has(m.id)} />}
            </p>
            <TextoTutor texto={m.texto} animar={animar.has(m.id)} onAvance={() => bajar(false)} />
          </li>
        ) : (
          <li key={m.id} className="mensaje mensaje-estudiante">
            <span className="solo-lectores">Vos: </span>
            {m.foto &&
              (fotos[m.id] ? (
                <FotoEnviada src={fotos[m.id]} alCargar={() => bajar(false)} />
              ) : (
                <p className="foto-ausente">Foto enviada (las fotos no se guardan en el historial)</p>
              ))}
            {m.texto && <p>{m.texto}</p>}
          </li>
        ),
      )}
      {pensando && (
        <li className="mensaje mensaje-tutor">
          <p className="autor">MAEstro</p>
          <span className="pensando" role="status" aria-label="MAEstro está pensando">
            <span />
            <span />
            <span />
          </span>
        </li>
      )}
      <li ref={final} className="conversacion-final" aria-hidden="true" />
    </ol>
  );
}

/** La foto que mandó el estudiante; mientras el navegador la carga se ve un bloque con brillo. */
function FotoEnviada({ src, alCargar }: { src: string; alCargar: () => void }) {
  const [cargada, setCargada] = useState(false);
  return (
    <>
      {!cargada && <div className="cargando-foto" role="status" aria-label="Cargando la foto" />}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt="Foto que enviaste"
        hidden={!cargada}
        onLoad={() => {
          setCargada(true);
          alCargar();
        }}
      />
    </>
  );
}

/** Número de pista en Caveat dentro de un circulito a mano, más la palabra "pista". */
function SelloPista({ numero, animar }: { numero: number; animar: boolean }) {
  return (
    <span className="sello-pista">
      <span className="numero-pista">
        <svg viewBox="0 0 32 32" aria-hidden="true">
          <path d={CIRCULITO_PISTA} pathLength={1} className={animar ? "trazo-animado" : undefined} />
        </svg>
        {numero}
      </span>
      pista
    </span>
  );
}

/** El texto del tutor aparece palabra por palabra; los lectores de pantalla lo reciben completo. */
function TextoTutor({ texto, animar, onAvance }: { texto: string; animar: boolean; onAvance: () => void }) {
  const palabras = texto.split(" ");
  const [visibles, setVisibles] = useState(animar ? 0 : palabras.length);
  const avance = useRef(onAvance);
  avance.current = onAvance;

  useEffect(() => {
    if (!animar || prefiereMenosMovimiento()) {
      setVisibles(palabras.length);
      return;
    }
    const reloj = setInterval(() => {
      setVisibles((v) => {
        if (v + 1 >= palabras.length) clearInterval(reloj);
        return v + 1;
      });
      avance.current();
    }, 45);
    return () => clearInterval(reloj);
  }, [animar, palabras.length]);

  return (
    <p>
      <span className="solo-lectores">{texto}</span>
      <span aria-hidden="true">
        {palabras.slice(0, visibles).map((p, i) => (
          <span key={i} className={animar ? "palabra" : undefined}>
            {p}{" "}
          </span>
        ))}
      </span>
    </p>
  );
}
