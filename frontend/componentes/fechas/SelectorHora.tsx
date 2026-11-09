"use client";

// Selector de hora (hh:mm, 24 h): se escribe directo ("2340" → 23:40) o se elige en el reloj.
// El valor que maneja el formulario es `HH:MM`, o vacío si no hay una hora válida.
import { useId, useRef, useState } from "react";
import { evaluarHora, formatearHora, mascaraHora } from "@/lib/fechas";
import { ColumnasHora } from "./ColumnasHora";
import { Disparador } from "./Disparador";
import { Emergente } from "./Emergente";
import { useCampoEscrito } from "./useCampoEscrito";

export interface PropsSelectorHora {
  id: string;
  etiqueta: string;
  /** `HH:MM` o vacío. */
  valor: string;
  onCambio: (valor: string) => void;
  /** Hora más temprana y más tardía que se admiten (`HH:MM`). */
  minima?: string;
  maxima?: string;
  motivoMinima?: string;
  motivoMaxima?: string;
  requerido?: boolean;
  mensajeRequerido?: string;
  onInvalido?: (mensaje: string | null) => void;
  revision?: number;
  deshabilitado?: boolean;
}

export function SelectorHora({
  id,
  etiqueta,
  valor,
  onCambio,
  minima,
  maxima,
  motivoMinima,
  motivoMaxima,
  requerido = false,
  mensajeRequerido = "Elegí una hora.",
  onInvalido,
  revision = 0,
  deshabilitado,
}: PropsSelectorHora) {
  const [abierto, setAbierto] = useState(false);
  const abiertoRef = useRef(false);
  abiertoRef.current = abierto;
  const caja = useRef<HTMLDivElement>(null);
  const boton = useRef<HTMLButtonElement>(null);
  const idMensaje = useId();

  const campo = useCampoEscrito({
    valor,
    onCambio,
    evaluar: (t) => evaluarHora(t, { minima, maxima, motivoMinima, motivoMaxima }),
    contexto: `${minima ?? ""}|${maxima ?? ""}`,
    formatear: formatearHora,
    mascara: mascaraHora,
    largoCompleto: 5,
    requerido,
    mensajeRequerido,
    revision,
    onInvalido,
    anunciar: (v) => `${etiqueta}: ${v} horas.`,
  });

  function cerrar(devolverFoco: boolean) {
    setAbierto(false);
    if (devolverFoco) boton.current?.focus();
    else campo.salir();
  }

  return (
    <div className="selector" onFocus={campo.alEntrar} onBlur={(e) => !abiertoRef.current && campo.alSalir(e, e.currentTarget)}>
      <Disparador
        id={id}
        icono="reloj"
        texto={campo.texto}
        placeholder="hh:mm"
        maxLength={5}
        etiquetaBoton={`Abrir selector de hora: ${etiqueta}`}
        etiquetaBorrar={requerido ? undefined : `Borrar ${etiqueta.toLowerCase()}`}
        abierto={abierto}
        invalido={campo.mensaje !== ""}
        descritoPor={campo.mensaje ? idMensaje : undefined}
        deshabilitado={deshabilitado}
        refCaja={caja}
        refBoton={boton}
        alEscribir={campo.alEscribir}
        alSalirTexto={campo.normalizar}
        alAbrir={() => setAbierto(true)}
        alBorrar={() => campo.elegir("")}
      />
      {campo.mensaje ? (
        <small className="error-campo" id={idMensaje} role="alert">
          {campo.mensaje}
        </small>
      ) : null}
      <span className="solo-lectores" role="status" aria-live="polite">
        {campo.anuncio}
      </span>
      {abierto ? (
        <Emergente anclaje={caja} etiqueta={`Hora: ${etiqueta}`} ancho={300} alCerrar={cerrar}>
          <ColumnasHora
            valor={campo.evaluacion.valor}
            minima={minima}
            maxima={maxima}
            motivoMinima={motivoMinima}
            motivoMaxima={motivoMaxima}
            limpiable={!requerido}
            onCambiar={(v, cierra) => {
              campo.elegir(v);
              if (cierra) cerrar(true);
            }}
            onListo={() => cerrar(true)}
          />
        </Emergente>
      ) : null}
    </div>
  );
}
