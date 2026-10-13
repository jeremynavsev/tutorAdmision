"use client";

import { useEffect, useState } from "react";
import { aplicarTema, temaActual, type Tema } from "@/lib/tema";
import { IconoLuna, IconoSol } from "./Iconos";

/** Alterna entre modo claro y oscuro y lo recuerda en este navegador. */
export default function BotonTema({ className = "boton-icono" }: { className?: string }) {
  const [tema, setTema] = useState<Tema | null>(null);

  useEffect(() => {
    setTema(temaActual());
  }, []);

  function alternar() {
    const nuevo: Tema = temaActual() === "dark" ? "light" : "dark";
    aplicarTema(nuevo);
    setTema(nuevo);
  }

  const oscuro = tema === "dark";
  const texto = oscuro ? "Modo claro" : "Modo oscuro";
  return (
    <button type="button" className={className} onClick={alternar} aria-label={`Cambiar a ${texto.toLowerCase()}`} title={texto}>
      {oscuro ? <IconoSol className="icono tema-icono" /> : <IconoLuna className="icono tema-icono" />}
      <span className="lateral-texto" aria-hidden="true">
        {texto}
      </span>
    </button>
  );
}
