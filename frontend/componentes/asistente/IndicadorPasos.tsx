"use client";

import { useState } from "react";
import { PASOS, estadoDePaso, indiceDePaso, textoCompactoDePaso } from "@/lib/asistenteSiniestro";
import type { IdPaso } from "@/lib/asistenteSiniestro";

/**
 * Indicador de pasos: números y nombres, con el actual, los completos y los que tienen errores. Cada paso es un botón.
 * En el teléfono queda un resumen «Paso 2 de 5 · Hecho y denuncia» que despliega la lista.
 */
export function IndicadorPasos({
  actual,
  visitados,
  conError,
  alElegir,
}: {
  actual: IdPaso;
  visitados: readonly IdPaso[];
  conError: ReadonlySet<IdPaso>;
  alElegir: (id: IdPaso) => void;
}) {
  const [abierta, setAbierta] = useState(false);
  return (
    <nav className="pasos" aria-label="Pasos para registrar el siniestro">
      <button
        type="button"
        className="pasos-compacto"
        aria-expanded={abierta}
        aria-controls="lista-pasos"
        onClick={() => setAbierta((a) => !a)}
      >
        <span>{textoCompactoDePaso(actual)}</span>
        <span className="pasos-compacto-accion">
          {conError.size > 0 ? <span className="pasos-compacto-aviso">Con errores</span> : null}
          <span aria-hidden="true">{abierta ? "▴" : "▾"}</span>
        </span>
      </button>
      <ol id="lista-pasos" className={`pasos-lista${abierta ? " pasos-lista-abierta" : ""}`}>
        {PASOS.map((p) => {
          const e = estadoDePaso(p.id, actual, visitados, conError);
          const clases = ["paso-boton", e.actual ? "paso-actual" : "", e.completo ? "paso-completo" : "", e.error ? "paso-error" : ""]
            .filter(Boolean)
            .join(" ");
          return (
            <li key={p.id}>
              <button
                type="button"
                className={clases}
                aria-current={e.actual ? "step" : undefined}
                onClick={() => {
                  setAbierta(false);
                  alElegir(p.id);
                }}
              >
                <span className="paso-marca" aria-hidden="true">
                  {e.error ? "!" : e.completo ? "✓" : indiceDePaso(p.id) + 1}
                </span>
                <span className="paso-texto">
                  <span className="paso-nombre">
                    <span className="solo-lectores">Paso {indiceDePaso(p.id) + 1}: </span>
                    {p.nombre}
                  </span>
                  {e.error ? <span className="paso-estado">Con errores</span> : null}
                  {e.completo ? <span className="solo-lectores"> (completo)</span> : null}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
