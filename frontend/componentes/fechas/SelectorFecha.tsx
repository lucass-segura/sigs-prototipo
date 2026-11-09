"use client";

// Selector de fecha (dd/mm/aaaa): se escribe directo ("120826" → 12/08/2026) o se elige en el calendario.
// El valor que maneja el formulario es `AAAA-MM-DD`, o vacío si no hay una fecha válida.
import { useId, useRef, useState } from "react";
import {
  ahoraLocal,
  evaluarFecha,
  formatearFecha,
  mascaraFecha,
  nombreLargoFecha,
  capitalizar,
} from "@/lib/fechas";
import type { AtajoFecha, LimitesFecha } from "@/lib/fechas";
import { Calendario } from "./Calendario";
import { Disparador } from "./Disparador";
import { Emergente } from "./Emergente";
import { useAhora } from "./useAhora";
import { useCampoEscrito } from "./useCampoEscrito";

export interface PropsSelectorFecha {
  id: string;
  /** Nombre del campo, para los lectores de pantalla y los títulos («Fecha del hecho»). */
  etiqueta: string;
  /** `AAAA-MM-DD` o vacío. */
  valor: string;
  onCambio: (valor: string) => void;
  /** Primer día elegible (`AAAA-MM-DD`). */
  minimo?: string;
  /** Último día elegible (`AAAA-MM-DD`). */
  maximo?: string;
  /** No admite días posteriores a hoy (se actualiza solo al cambiar el día). */
  noFuturo?: boolean;
  /** Explicación de por qué un día anterior al mínimo no se puede elegir. */
  motivoMinimo?: string;
  motivoMaximo?: string;
  /** Atajos del calendario, en orden. Por defecto «Hoy». */
  atajos?: AtajoFecha[];
  /** Obligatorio: no se puede borrar y vacío cuenta como no válido. */
  requerido?: boolean;
  mensajeRequerido?: string;
  /** Nota que no impide enviar (por ejemplo, «esa fecha ya pasó»). */
  aviso?: (valor: string) => string | null;
  onInvalido?: (mensaje: string | null) => void;
  revision?: number;
  deshabilitado?: boolean;
}

export function SelectorFecha({
  id,
  etiqueta,
  valor,
  onCambio,
  minimo,
  maximo,
  noFuturo = false,
  motivoMinimo,
  motivoMaximo,
  atajos = ["hoy"],
  requerido = false,
  mensajeRequerido = "Elegí una fecha.",
  aviso,
  onInvalido,
  revision = 0,
  deshabilitado,
}: PropsSelectorFecha) {
  const ahora = useAhora(noFuturo);
  const hoy = noFuturo ? ahora.fecha : ahoraLocal().fecha;
  const tope = noFuturo && (!maximo || hoy < maximo) ? hoy : maximo;
  const limites: LimitesFecha = {
    minimo,
    maximo: tope,
    motivoMinimo,
    motivoMaximo: motivoMaximo ?? (noFuturo && tope === hoy ? "Todavía no pasó: la fecha no puede ser posterior a hoy." : undefined),
  };

  const [abierto, setAbierto] = useState(false);
  const abiertoRef = useRef(false);
  abiertoRef.current = abierto;
  const caja = useRef<HTMLDivElement>(null);
  const boton = useRef<HTMLButtonElement>(null);
  const idLeyenda = useId();
  const idMensaje = useId();
  const idAviso = useId();

  const campo = useCampoEscrito({
    valor,
    onCambio,
    evaluar: (t) => evaluarFecha(t, hoy, limites),
    contexto: `${minimo ?? ""}|${tope ?? ""}`,
    formatear: formatearFecha,
    mascara: mascaraFecha,
    largoCompleto: 10,
    requerido,
    mensajeRequerido,
    revision,
    onInvalido,
    anunciar: (v) => `${etiqueta}: ${nombreLargoFecha(v)}.`,
  });

  const valida = campo.evaluacion.estado === "ok";
  const nota = valida && aviso ? aviso(campo.evaluacion.valor) : null;
  const descritoPor = [campo.mensaje ? idMensaje : "", valida ? idLeyenda : "", nota ? idAviso : ""].filter(Boolean).join(" ") || undefined;

  function cerrar(devolverFoco: boolean) {
    setAbierto(false);
    if (devolverFoco) boton.current?.focus();
    else campo.salir();
  }

  return (
    <div className="selector" onFocus={campo.alEntrar} onBlur={(e) => !abiertoRef.current && campo.alSalir(e, e.currentTarget)}>
      <Disparador
        id={id}
        icono="calendario"
        texto={campo.texto}
        placeholder="dd/mm/aaaa"
        maxLength={10}
        etiquetaBoton={`Abrir calendario: ${etiqueta}`}
        etiquetaBorrar={requerido ? undefined : `Borrar ${etiqueta.toLowerCase()}`}
        abierto={abierto}
        invalido={campo.mensaje !== ""}
        descritoPor={descritoPor}
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
      {valida ? (
        <small className="selector-leyenda" id={idLeyenda}>
          {capitalizar(nombreLargoFecha(campo.evaluacion.valor))}
        </small>
      ) : null}
      {nota ? (
        <small className="ayuda" id={idAviso}>
          {nota}
        </small>
      ) : null}
      <span className="solo-lectores" role="status" aria-live="polite">
        {campo.anuncio}
      </span>
      {abierto ? (
        <Emergente anclaje={caja} etiqueta={`Calendario: ${etiqueta}`} ancho={348} alCerrar={cerrar}>
          <Calendario
            valor={campo.evaluacion.valor}
            hoy={hoy}
            minimo={limites.minimo}
            maximo={limites.maximo}
            motivoMinimo={limites.motivoMinimo}
            motivoMaximo={limites.motivoMaximo}
            atajos={atajos}
            limpiable={!requerido}
            onElegir={(iso) => {
              campo.elegir(iso);
              cerrar(true);
            }}
          />
        </Emergente>
      ) : null}
    </div>
  );
}
