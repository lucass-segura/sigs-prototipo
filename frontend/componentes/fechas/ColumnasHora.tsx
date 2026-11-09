"use client";

// Contenido del selector de hora: la hora elegida en grande, «Ahora» y dos columnas (horas y minutos de 5 en 5).
import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import { HORAS, ahoraLocal, horaPermitida, minutoPermitido, minutosDeColumna } from "@/lib/fechas";

export interface PropsColumnasHora {
  /** `HH:MM` o vacío. */
  valor: string;
  minima?: string;
  maxima?: string;
  motivoMinima?: string;
  motivoMaxima?: string;
  limpiable: boolean;
  /** `cerrar`: con el minuto elegido, o «Ahora», ya no hay nada más que decidir. */
  onCambiar: (valor: string, cerrar: boolean) => void;
  onListo: () => void;
}

export function ColumnasHora({ valor, minima, maxima, motivoMinima, motivoMaxima, limpiable, onCambiar, onListo }: PropsColumnasHora) {
  const [pista, setPista] = useState("");
  const raiz = useRef<HTMLDivElement>(null);
  const idHoras = useId();
  const idMinutos = useId();

  const hora = valor.slice(0, 2);
  const minuto = valor.slice(3, 5);
  const horaInicial = hora || (horaPermitida(ahoraLocal().hora.slice(0, 2), minima, maxima) ? ahoraLocal().hora.slice(0, 2) : HORAS.find((h) => horaPermitida(h, minima, maxima)) ?? "00");
  const minutos = minutosDeColumna(minuto);
  const motivo = (v: string) =>
    minima && v < minima
      ? (motivoMinima ?? `No puede ser anterior a las ${minima}.`)
      : maxima && v > maxima
        ? (motivoMaxima ?? `No puede ser posterior a las ${maxima}.`)
        : null;

  // Las columnas se abren con lo elegido a la vista.
  useEffect(() => {
    raiz.current?.querySelectorAll<HTMLElement>(".reloj-lista").forEach((lista) => {
      const elegido = lista.querySelector<HTMLElement>("[aria-selected='true']") ?? lista.querySelector<HTMLElement>("[tabindex='0']");
      if (elegido) lista.scrollTop = elegido.offsetTop - lista.clientHeight / 2 + elegido.offsetHeight / 2;
    });
  }, []);

  function enfocarColumna(id: string, preferido?: string) {
    const lista = raiz.current?.querySelector<HTMLElement>(`[data-columna="${id}"]`);
    const destino =
      lista?.querySelector<HTMLElement>(`[data-v="${preferido}"]`) ??
      lista?.querySelector<HTMLElement>("[aria-selected='true']") ??
      lista?.querySelector<HTMLElement>("[tabindex='0']");
    destino?.focus();
  }

  function elegirHora(h: string) {
    if (!horaPermitida(h, minima, maxima)) {
      setPista(`${h} h: ${motivo(`${h}:00`) ?? motivo(`${h}:59`) ?? "no se puede elegir."}`);
      return;
    }
    setPista("");
    const permitido = minutos.find((m) => minutoPermitido(h, m, minima, maxima)) ?? "00";
    const m = minuto && minutoPermitido(h, minuto, minima, maxima) ? minuto : permitido;
    onCambiar(`${h}:${m}`, false);
    window.setTimeout(() => enfocarColumna("minutos", m), 0);
  }

  function elegirMinuto(m: string) {
    if (!hora) {
      setPista("Elegí primero la hora.");
      enfocarColumna("horas");
      return;
    }
    if (!minutoPermitido(hora, m, minima, maxima)) {
      setPista(`${hora}:${m}: ${motivo(`${hora}:${m}`) ?? "no se puede elegir."}`);
      return;
    }
    setPista("");
    onCambiar(`${hora}:${m}`, true);
  }

  function ahora() {
    let v = ahoraLocal().hora;
    if (maxima && v > maxima) v = maxima;
    if (minima && v < minima) v = minima;
    onCambiar(v, true);
  }

  function teclaLista(e: KeyboardEvent<HTMLDivElement>, columna: "horas" | "minutos") {
    const opciones = Array.from(e.currentTarget.querySelectorAll<HTMLElement>("[role='option']"));
    const indice = opciones.indexOf(document.activeElement as HTMLElement);
    if (indice === -1) return;
    let destino: HTMLElement | undefined;
    switch (e.key) {
      case "ArrowDown":
        destino = opciones[Math.min(opciones.length - 1, indice + 1)];
        break;
      case "ArrowUp":
        destino = opciones[Math.max(0, indice - 1)];
        break;
      case "Home":
        destino = opciones[0];
        break;
      case "End":
        destino = opciones[opciones.length - 1];
        break;
      case "ArrowRight":
      case "ArrowLeft":
        e.preventDefault();
        enfocarColumna(columna === "horas" ? "minutos" : "horas");
        return;
      case "Enter":
      case " ":
        e.preventDefault();
        (document.activeElement as HTMLElement).click();
        return;
      default:
        return;
    }
    e.preventDefault();
    destino?.focus();
  }

  return (
    <div className="reloj" ref={raiz}>
      <div className="reloj-cabecera">
        <div className="reloj-lectura" aria-live="polite" aria-atomic="true">
          <span className="solo-lectores">Hora elegida: </span>
          {valor || "--:--"}
        </div>
        <button type="button" className="boton selector-atajo" onClick={ahora}>
          Ahora
        </button>
      </div>

      <div className="reloj-columnas">
        <div className="reloj-columna">
          <span className="reloj-titulo" id={idHoras}>
            Hora
          </span>
          <div className="reloj-lista" role="listbox" aria-labelledby={idHoras} data-columna="horas" onKeyDown={(e) => teclaLista(e, "horas")}>
            {HORAS.map((h) => {
              const libre = horaPermitida(h, minima, maxima);
              const elegida = h === hora;
              return (
                <div
                  key={h}
                  role="option"
                  className={`reloj-opcion${elegida ? " reloj-opcion-elegida" : ""}${libre ? "" : " reloj-opcion-bloqueada"}`}
                  data-v={h}
                  data-foco-inicial={h === horaInicial ? "" : undefined}
                  tabIndex={h === horaInicial ? 0 : -1}
                  aria-selected={elegida}
                  aria-disabled={libre ? undefined : true}
                  title={libre ? undefined : (motivo(`${h}:00`) ?? motivo(`${h}:59`) ?? undefined)}
                  onClick={() => elegirHora(h)}
                >
                  {h}
                </div>
              );
            })}
          </div>
        </div>
        <div className="reloj-columna">
          <span className="reloj-titulo" id={idMinutos}>
            Minutos
          </span>
          <div className="reloj-lista" role="listbox" aria-labelledby={idMinutos} data-columna="minutos" onKeyDown={(e) => teclaLista(e, "minutos")}>
            {minutos.map((m) => {
              const libre = hora ? minutoPermitido(hora, m, minima, maxima) : true;
              const elegido = m === minuto;
              return (
                <div
                  key={m}
                  role="option"
                  className={`reloj-opcion${elegido ? " reloj-opcion-elegida" : ""}${libre && hora ? "" : " reloj-opcion-bloqueada"}`}
                  data-v={m}
                  tabIndex={elegido || (!minuto && m === "00") ? 0 : -1}
                  aria-selected={elegido}
                  aria-disabled={libre && hora ? undefined : true}
                  title={!hora ? "Elegí primero la hora" : libre ? undefined : (motivo(`${hora}:${m}`) ?? undefined)}
                  onClick={() => elegirMinuto(m)}
                >
                  {m}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <p className="calendario-pista" role="status">
        {pista}
      </p>

      <div className="selector-pie">
        {limpiable && valor ? (
          <button type="button" className="boton boton-chico" onClick={() => onCambiar("", true)}>
            Borrar hora
          </button>
        ) : (
          <span />
        )}
        <button type="button" className="boton boton-principal" onClick={onListo}>
          Listo
        </button>
      </div>
    </div>
  );
}
