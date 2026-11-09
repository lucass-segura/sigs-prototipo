"use client";

// El campo del selector: un cuadro de texto con máscara (se puede escribir directo) y, a la derecha,
// un botón grande que abre el calendario o el reloj. Escribir o hacer clic en el texto no abre nada.
import type { KeyboardEvent, Ref } from "react";

export function IconoCalendario() {
  return (
    <svg className="selector-icono" viewBox="0 0 20 20" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <rect x="3" y="4.5" width="14" height="12.5" rx="1.5" />
      <path d="M3 8.5h14M7 2.75v3.5M13 2.75v3.5" strokeLinecap="round" />
    </svg>
  );
}

export function IconoReloj() {
  return (
    <svg className="selector-icono" viewBox="0 0 20 20" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden="true">
      <circle cx="10" cy="10" r="7" />
      <path d="M10 5.75V10l2.75 1.75" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Disparador({
  id,
  icono,
  texto,
  placeholder,
  maxLength,
  etiquetaBoton,
  etiquetaBorrar,
  abierto,
  invalido,
  descritoPor,
  deshabilitado,
  refCaja,
  refBoton,
  alEscribir,
  alSalirTexto,
  alAbrir,
  alBorrar,
}: {
  id: string;
  icono: "calendario" | "reloj";
  texto: string;
  placeholder: string;
  maxLength: number;
  /** Nombre accesible del botón («Abrir calendario…»). */
  etiquetaBoton: string;
  /** Texto del botón para borrar; sin él no hay botón. */
  etiquetaBorrar?: string;
  abierto: boolean;
  invalido: boolean;
  descritoPor?: string;
  deshabilitado?: boolean;
  refCaja: Ref<HTMLDivElement>;
  refBoton: Ref<HTMLButtonElement>;
  alEscribir: (crudo: string) => void;
  alSalirTexto: () => void;
  alAbrir: (origen: "campo" | "boton") => void;
  alBorrar: () => void;
}) {
  function alPulsar(e: KeyboardEvent<HTMLInputElement>) {
    // Alt + flecha abajo abre el selector sin sacar las manos del teclado.
    if (e.key === "ArrowDown" && e.altKey) {
      e.preventDefault();
      alAbrir("campo");
    }
  }
  return (
    <div ref={refCaja} className={`selector-caja${invalido ? " selector-invalido" : ""}${abierto ? " selector-abierto" : ""}`}>
      <input
        id={id}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        spellCheck={false}
        value={texto}
        placeholder={placeholder}
        maxLength={maxLength}
        aria-invalid={invalido || undefined}
        aria-describedby={descritoPor}
        disabled={deshabilitado}
        onChange={(e) => alEscribir(e.target.value)}
        onBlur={alSalirTexto}
        onKeyDown={alPulsar}
      />
      {texto && etiquetaBorrar ? (
        <button type="button" className="selector-borrar" aria-label={etiquetaBorrar} title={etiquetaBorrar} disabled={deshabilitado} onClick={alBorrar}>
          <svg viewBox="0 0 20 20" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
            <path d="M5 5l10 10M15 5L5 15" />
          </svg>
        </button>
      ) : null}
      <button
        ref={refBoton}
        type="button"
        className="selector-boton"
        aria-haspopup="dialog"
        aria-expanded={abierto}
        aria-label={etiquetaBoton}
        title={etiquetaBoton}
        disabled={deshabilitado}
        onClick={() => alAbrir("boton")}
      >
        {icono === "calendario" ? <IconoCalendario /> : <IconoReloj />}
      </button>
    </div>
  );
}
