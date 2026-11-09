"use client";

// Contenido del selector de fecha: atajos y calendario (días, meses y años).
import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import {
  ANIO_MAXIMO,
  ANIO_MINIMO,
  DIAS_CORTOS,
  DIAS_LARGOS,
  MESES,
  TEXTO_ATAJO,
  ajustarARango,
  armarISO,
  capitalizar,
  diasDelMes,
  finDeMesISO,
  finDeSemanaISO,
  formatearFecha,
  inicioDeMesISO,
  inicioDeSemanaISO,
  matrizDelMes,
  mensajeFueraDeRango,
  nombreLargoFecha,
  nombreMesAnio,
  partesISO,
  resolverAtajo,
  sumarDiasISO,
  sumarMesesISO,
} from "@/lib/fechas";
import type { AtajoFecha } from "@/lib/fechas";

type Vista = "dias" | "meses" | "anios";

export interface PropsCalendario {
  /** Fecha elegida (`AAAA-MM-DD`) o vacío. */
  valor: string;
  hoy: string;
  minimo?: string;
  maximo?: string;
  motivoMinimo?: string;
  motivoMaximo?: string;
  atajos: AtajoFecha[];
  limpiable: boolean;
  /** `""` = sin fecha. */
  onElegir: (iso: string) => void;
}

function Flecha({ lado }: { lado: "izquierda" | "derecha" }) {
  return (
    <svg viewBox="0 0 20 20" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={lado === "izquierda" ? "M12.5 4.5L7 10l5.5 5.5" : "M7.5 4.5L13 10l-5.5 5.5"} />
    </svg>
  );
}

export function Calendario({ valor, hoy, minimo, maximo, motivoMinimo, motivoMaximo, atajos, limpiable, onElegir }: PropsCalendario) {
  const [foco, setFoco] = useState(() => ajustarARango(partesISO(valor) ? valor : hoy, minimo, maximo));
  const [vista, setVista] = useState<Vista>("dias");
  const [pista, setPista] = useState("");
  const raiz = useRef<HTMLDivElement>(null);
  const enfocar = useRef(false);
  const idTitulo = useId();

  const limites = { minimo, maximo, motivoMinimo, motivoMaximo };
  const motivoDe = (iso: string) => mensajeFueraDeRango(iso, limites);
  const p = partesISO(foco) ?? { a: 2000, m: 1, d: 1 };

  // Después de mover el foco con el teclado o de cambiar de vista, el foco real sigue a la selección.
  useEffect(() => {
    if (!enfocar.current) return;
    enfocar.current = false;
    const destino = vista === "dias" ? `[data-dia="${foco}"]` : "[data-foco-vista]";
    raiz.current?.querySelector<HTMLElement>(destino)?.focus();
  }, [foco, vista]);

  function mover(iso: string) {
    enfocar.current = true;
    setFoco(iso);
  }

  function elegir(iso: string) {
    const motivo = motivoDe(iso);
    if (motivo) {
      setPista(`${formatearFecha(iso)}: ${motivo}`);
      return;
    }
    onElegir(iso);
  }

  // ------------------------------------------------------------ Teclado en la grilla de días

  function teclaDia(e: KeyboardEvent<HTMLDivElement>) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    let nuevo: string | null = null;
    switch (e.key) {
      case "ArrowLeft":
        nuevo = sumarDiasISO(foco, -1);
        break;
      case "ArrowRight":
        nuevo = sumarDiasISO(foco, 1);
        break;
      case "ArrowUp":
        nuevo = sumarDiasISO(foco, -7);
        break;
      case "ArrowDown":
        nuevo = sumarDiasISO(foco, 7);
        break;
      case "Home":
        nuevo = inicioDeSemanaISO(foco);
        break;
      case "End":
        nuevo = finDeSemanaISO(foco);
        break;
      case "PageUp":
        nuevo = sumarMesesISO(foco, e.shiftKey ? -12 : -1);
        break;
      case "PageDown":
        nuevo = sumarMesesISO(foco, e.shiftKey ? 12 : 1);
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        elegir(foco);
        return;
      default:
        return;
    }
    e.preventDefault();
    if (nuevo.slice(0, 4) < String(ANIO_MINIMO) || nuevo.slice(0, 4) > String(ANIO_MAXIMO)) return;
    mover(nuevo);
  }

  // ------------------------------------------------------------ Meses y años

  const anioBase = Math.floor(p.a / 12) * 12;
  const anioMin = minimo ? Number(minimo.slice(0, 4)) : null;
  const anioMax = maximo ? Number(maximo.slice(0, 4)) : null;

  function mesFuera(a: number, m: number): boolean {
    const inicio = armarISO(a, m, 1);
    const fin = armarISO(a, m, diasDelMes(a, m));
    return (minimo !== undefined && fin < minimo) || (maximo !== undefined && inicio > maximo);
  }

  function anioFuera(a: number): boolean {
    return (anioMin !== null && a < anioMin) || (anioMax !== null && a > anioMax) || a < ANIO_MINIMO || a > ANIO_MAXIMO;
  }

  function elegirMes(m: number) {
    const dia = Math.min(p.d, diasDelMes(p.a, m));
    enfocar.current = true;
    setFoco(ajustarARango(armarISO(p.a, m, dia), minimo, maximo));
    setVista("dias");
  }

  function elegirAnio(a: number) {
    const dia = Math.min(p.d, diasDelMes(a, p.m));
    enfocar.current = true;
    setFoco(ajustarARango(armarISO(a, p.m, dia), minimo, maximo));
    setVista("meses");
  }

  function teclaCeldas(e: KeyboardEvent<HTMLDivElement>) {
    const paso = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -3, ArrowDown: 3 }[e.key];
    if (paso === undefined) return;
    const botones = Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>("button:not([aria-disabled='true'])"));
    const indice = botones.indexOf(document.activeElement as HTMLButtonElement);
    if (indice === -1) return;
    e.preventDefault();
    botones[Math.max(0, Math.min(botones.length - 1, indice + paso))]?.focus();
  }

  // ------------------------------------------------------------ Encabezado

  const titulo = vista === "dias" ? capitalizar(nombreMesAnio(foco)) : vista === "meses" ? String(p.a) : `${anioBase} – ${anioBase + 11}`;
  const etiquetaTitulo =
    vista === "dias" ? "Elegir mes y año" : vista === "meses" ? "Elegir año" : "Volver a los meses";

  function desplazar(sentido: -1 | 1) {
    const meses = vista === "dias" ? 1 : vista === "meses" ? 12 : 144;
    if (vista === "dias") {
      setFoco(ajustarARango(sumarMesesISO(foco, sentido * meses), minimo, maximo));
    } else {
      setFoco(sumarMesesISO(foco, sentido * meses));
    }
  }

  const sinAnterior =
    vista === "dias"
      ? minimo !== undefined && inicioDeMesISO(foco) <= minimo
      : vista === "meses"
        ? p.a - 1 < ANIO_MINIMO || (anioMin !== null && p.a <= anioMin)
        : anioBase <= ANIO_MINIMO || (anioMin !== null && anioBase <= anioMin);
  const sinSiguiente =
    vista === "dias"
      ? maximo !== undefined && finDeMesISO(foco) >= maximo
      : vista === "meses"
        ? p.a + 1 > ANIO_MAXIMO || (anioMax !== null && p.a >= anioMax)
        : anioBase + 11 >= ANIO_MAXIMO || (anioMax !== null && anioBase + 11 >= anioMax);

  function alternarVista() {
    enfocar.current = true;
    setVista(vista === "dias" ? "meses" : vista === "meses" ? "anios" : "meses");
  }

  const motivoFoco = vista === "dias" ? motivoDe(foco) : null;
  const textoPista = pista || (motivoFoco ? `${formatearFecha(foco)}: ${motivoFoco}` : "");
  const semanas = matrizDelMes(foco);

  return (
    <div className="calendario" ref={raiz}>
      {atajos.length > 0 ? (
        <div className="selector-atajos" role="group" aria-label="Atajos">
          {atajos.map((atajo) => {
            const destino = resolverAtajo(atajo, hoy);
            const motivo = destino ? motivoDe(destino) : null;
            return (
              <button
                key={atajo}
                type="button"
                className="boton selector-atajo"
                disabled={motivo !== null}
                title={motivo ?? (destino ? nombreLargoFecha(destino) : "Sin fecha")}
                onClick={() => onElegir(destino)}
              >
                {TEXTO_ATAJO[atajo]}
              </button>
            );
          })}
        </div>
      ) : null}

      <div className="calendario-nav">
        <button type="button" className="calendario-flecha" aria-label={vista === "dias" ? "Mes anterior" : vista === "meses" ? "Año anterior" : "Años anteriores"} disabled={sinAnterior} onClick={() => desplazar(-1)}>
          <Flecha lado="izquierda" />
        </button>
        <button type="button" className="calendario-titulo" aria-label={`${titulo}. ${etiquetaTitulo}`} onClick={alternarVista}>
          <span id={idTitulo} aria-live="polite">
            {titulo}
          </span>
          <svg viewBox="0 0 20 20" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d={vista === "dias" ? "M5 7.5l5 5 5-5" : "M5 12.5l5-5 5 5"} />
          </svg>
        </button>
        <button type="button" className="calendario-flecha" aria-label={vista === "dias" ? "Mes siguiente" : vista === "meses" ? "Año siguiente" : "Años siguientes"} disabled={sinSiguiente} onClick={() => desplazar(1)}>
          <Flecha lado="derecha" />
        </button>
      </div>

      {vista === "dias" ? (
        <div className="calendario-grilla" role="grid" aria-labelledby={idTitulo} onKeyDown={teclaDia} onMouseLeave={() => setPista("")}>
          <div role="row" className="calendario-semana calendario-dias-semana">
            {DIAS_CORTOS.map((d, i) => (
              <span key={d} role="columnheader" aria-label={DIAS_LARGOS[i]} title={DIAS_LARGOS[i]}>
                {d}
              </span>
            ))}
          </div>
          {semanas.map((semana) => (
            <div role="row" className="calendario-semana" key={semana[0]}>
              {semana.map((iso) => {
                const pd = partesISO(iso) as { a: number; m: number; d: number };
                const motivo = motivoDe(iso);
                const elegido = iso === valor;
                const esHoy = iso === hoy;
                const clases = ["dia"];
                if (pd.m !== p.m) clases.push("dia-fuera");
                if (esHoy) clases.push("dia-hoy");
                if (elegido) clases.push("dia-elegido");
                if (motivo) clases.push("dia-bloqueado");
                return (
                  <div
                    key={iso}
                    role="gridcell"
                    className={clases.join(" ")}
                    data-dia={iso}
                    data-foco-inicial={iso === foco ? "" : undefined}
                    tabIndex={iso === foco ? 0 : -1}
                    aria-selected={elegido}
                    aria-disabled={motivo ? true : undefined}
                    aria-current={esHoy ? "date" : undefined}
                    aria-label={`${esHoy ? "Hoy, " : ""}${nombreLargoFecha(iso)}${motivo ? `. No disponible: ${motivo}` : ""}`}
                    title={motivo ?? (esHoy ? "Hoy" : undefined)}
                    onClick={() => elegir(iso)}
                    onMouseEnter={() => setPista(motivo ? `${formatearFecha(iso)}: ${motivo}` : "")}
                  >
                    {pd.d}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      ) : null}

      {vista === "meses" ? (
        <div className="calendario-celdas" role="group" aria-label="Meses" onKeyDown={teclaCeldas}>
          {MESES.map((nombre, i) => {
            const fuera = mesFuera(p.a, i + 1);
            const actual = i + 1 === p.m;
            return (
              <button
                key={nombre}
                type="button"
                className={`calendario-celda${actual ? " calendario-celda-actual" : ""}`}
                data-foco-vista={actual ? "" : undefined}
                data-foco-inicial={actual ? "" : undefined}
                aria-disabled={fuera || undefined}
                aria-pressed={actual}
                title={fuera ? "Ningún día de este mes se puede elegir" : undefined}
                onClick={() => !fuera && elegirMes(i + 1)}
              >
                {capitalizar(nombre)}
              </button>
            );
          })}
        </div>
      ) : null}

      {vista === "anios" ? (
        <div className="calendario-celdas" role="group" aria-label="Años" onKeyDown={teclaCeldas}>
          {Array.from({ length: 12 }, (_, i) => anioBase + i).map((a) => {
            const fuera = anioFuera(a);
            const actual = a === p.a;
            return (
              <button
                key={a}
                type="button"
                className={`calendario-celda${actual ? " calendario-celda-actual" : ""}`}
                data-foco-vista={actual ? "" : undefined}
                data-foco-inicial={actual ? "" : undefined}
                aria-disabled={fuera || undefined}
                aria-pressed={actual}
                title={fuera ? "Ningún día de este año se puede elegir" : undefined}
                onClick={() => !fuera && elegirAnio(a)}
              >
                {a}
              </button>
            );
          })}
        </div>
      ) : null}

      <p className="calendario-pista" role="status">
        {textoPista}
      </p>

      {limpiable && valor ? (
        <div className="selector-pie">
          <button type="button" className="boton boton-chico" onClick={() => onElegir("")}>
            Borrar fecha
          </button>
        </div>
      ) : null}
    </div>
  );
}
