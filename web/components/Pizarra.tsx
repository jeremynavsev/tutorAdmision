"use client";

import { Fragment, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { AnotacionNumerada } from "@/lib/chats";
import { circuloAMano, type Caja } from "@/lib/trazos";
import { IconoCerrar } from "./Iconos";

type Forma = { clave: string; d: string; animar: boolean; retraso: number };

type Props = {
  anotaciones: AnotacionNumerada[];
  /** Si el panel se ve. Lo nuevo solo se dibuja cuando se ve, para no perderse la animación. */
  visible: boolean;
  onCerrar: () => void;
};

const escapar = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/**
 * Pizarra del chat: el tutor copia ahí el problema, encierra los datos con
 * círculos de tiza y va escribiendo sus apuntes.
 */
export default function Pizarra({ anotaciones, visible, onCerrar }: Props) {
  const hoja = useRef<HTMLDivElement>(null);
  const maxN = anotaciones.reduce((m, a) => Math.max(m, a.n), 0);

  // Lo que ya estaba al abrir el chat se muestra quieto; lo que llega después se anima.
  const [hastaN, setHastaN] = useState(maxN);
  const [animarDesde, setAnimarDesde] = useState(maxN);
  useEffect(() => {
    if (visible && maxN > hastaN) {
      setAnimarDesde(hastaN);
      setHastaN(maxN);
    }
  }, [visible, maxN, hastaN]);

  const vistas = useMemo(() => anotaciones.filter((a) => a.n <= hastaN), [anotaciones, hastaN]);

  // El último enunciado copiado y los datos encerrados.
  // (Memorizados: si cambiaran en cada render, el cálculo de los trazos no pararía nunca.)
  const enunciado = useMemo(() => [...vistas].reverse().find((a) => a.tipo === "enunciado"), [vistas]);
  const circulos = useMemo(
    () => vistas.filter((a): a is Extract<AnotacionNumerada, { tipo: "circulo" }> => a.tipo === "circulo"),
    [vistas],
  );
  const apuntes = vistas.filter((a): a is Extract<AnotacionNumerada, { tipo: "apunte" }> => a.tipo === "apunte");

  // Parte el enunciado para envolver cada dato encerrado en un span con id.
  const trozos = useMemo(() => {
    if (!enunciado || enunciado.tipo !== "enunciado") return [];
    const datos = [...new Set(circulos.map((c) => c.dato))].sort((a, b) => b.length - a.length);
    if (datos.length === 0) return [{ texto: enunciado.texto }];
    const usados = new Set<string>();
    return enunciado.texto
      // Sin dígitos pegados: el dato "2" no debe encontrarse dentro de "12".
      .split(new RegExp(`(?<!\\d)(${datos.map(escapar).join("|")})(?!\\d)`))
      .filter(Boolean)
      .map((texto) => {
        if (datos.includes(texto) && !usados.has(texto)) {
          usados.add(texto);
          return { texto, id: `dato-${datos.indexOf(texto)}` };
        }
        return { texto };
      });
  }, [enunciado, circulos]);

  const [formas, setFormas] = useState<Forma[]>([]);

  const calcular = useCallback(
    (animar: boolean) => {
      const base = hoja.current?.getBoundingClientRect();
      if (!base) return;
      const datos = [...new Set(circulos.map((c) => c.dato))].sort((a, b) => b.length - a.length);
      let orden = 0;
      const resultado: Forma[] = [];
      const vistos = new Set<string>();
      for (const c of circulos) {
        if (vistos.has(c.dato)) continue;
        vistos.add(c.dato);
        const r = document.getElementById(`dato-${datos.indexOf(c.dato)}`)?.getBoundingClientRect();
        if (!r || r.width === 0) continue;
        const caja: Caja = { x: r.left - base.left, y: r.top - base.top, ancho: r.width, alto: r.height };
        const nueva = animar && c.n > animarDesde;
        resultado.push({ clave: c.dato, d: circuloAMano(caja, c.dato), animar: nueva, retraso: nueva ? 300 + orden++ * 300 : 0 });
      }
      setFormas(resultado);
    },
    [circulos, animarDesde],
  );

  useLayoutEffect(() => {
    calcular(true);
  }, [calcular]);

  // Cambio de ancho o fuentes recién cargadas: se redibuja sin animación.
  const ultimoCalcular = useRef(calcular);
  ultimoCalcular.current = calcular;
  useEffect(() => {
    const el = hoja.current;
    if (!el) return;
    let ancho = el.offsetWidth;
    const observador = new ResizeObserver(() => {
      if (el.offsetWidth === ancho) return;
      ancho = el.offsetWidth;
      ultimoCalcular.current(false);
    });
    observador.observe(el);
    document.fonts?.ready.then(() => ultimoCalcular.current(false));
    return () => observador.disconnect();
  }, []);

  const enunciadoNuevo = enunciado ? enunciado.n > animarDesde : false;

  return (
    <aside className="pizarra-panel" aria-labelledby="titulo-pizarra" aria-hidden={!visible} inert={!visible}>
      <div className="pizarra-barra">
        <h2 id="titulo-pizarra">Pizarra</h2>
        <button type="button" className="boton-icono" onClick={onCerrar} aria-label="Cerrar la pizarra" title="Cerrar pizarra">
          <IconoCerrar />
        </button>
      </div>

      <div className="pizarra-marco">
        <div className="pizarra">
          <div ref={hoja} className="pizarra-hoja">
            {!enunciado ? (
              <p className="pizarra-vacia">
                La pizarra está limpia. Cuando me mandés un problema, lo copio aquí y lo vamos trabajando.
              </p>
            ) : (
              <>
                <p className="pizarra-etiqueta">El problema</p>
                <p className={`pizarra-enunciado ${enunciadoNuevo ? "pizarra-enunciado-nuevo" : ""}`}>
                  {trozos.map((t, i) =>
                    "id" in t ? (
                      <span key={i} id={t.id} className="dato">
                        {t.texto}
                      </span>
                    ) : (
                      <Fragment key={i}>{t.texto}</Fragment>
                    ),
                  )}
                </p>
              </>
            )}

            {apuntes.length > 0 && (
              <div className="apuntes">
                <p className="pizarra-etiqueta">Apuntes</p>
                <ul className="apuntes-lista">
                  {apuntes.map((a) => (
                    <li key={a.n} className={`apunte ${a.n > animarDesde ? "apunte-nuevo" : ""}`}>
                      {a.texto}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <svg className="capa-anotaciones" aria-hidden="true">
              {formas.map((f) => (
                <path
                  key={f.clave + (f.animar ? "-a" : "")}
                  d={f.d}
                  pathLength={1}
                  strokeWidth={2.6}
                  className={`trazo trazo-guaria ${f.animar ? "trazo-animado" : ""}`}
                  style={f.animar ? { animationDelay: `${f.retraso}ms` } : undefined}
                />
              ))}
            </svg>
          </div>
        </div>
        <div className="repisa" aria-hidden="true">
          <span className="pedazo-tiza" />
        </div>
      </div>
    </aside>
  );
}
