import type { ReactNode } from "react";
import { PASOS, indiceDePaso } from "@/lib/asistenteSiniestro";
import type { IdPaso } from "@/lib/asistenteSiniestro";

/**
 * Un paso del asistente. Los cinco quedan montados y solo se oculta el que no es el actual: así lo que se escribió
 * (incluido el texto a medio escribir de una fecha) no se pierde al ir y venir.
 */
export function Paso({
  id,
  activo,
  accion,
  children,
}: {
  id: IdPaso;
  activo: boolean;
  /** Botón de la cabecera (por ejemplo, «Agregar»). */
  accion?: ReactNode;
  children: ReactNode;
}) {
  const indice = indiceDePaso(id);
  return (
    <section className="tarjeta paso" hidden={!activo} aria-labelledby={`titulo-paso-${id}`}>
      <div className="tarjeta-cabecera">
        <div className="paso-titulo">
          <h2 id={`titulo-paso-${id}`} tabIndex={-1}>
            {PASOS[indice].nombre}
          </h2>
          <span className="meta">
            Paso {indice + 1} de {PASOS.length}
          </span>
        </div>
        {accion}
      </div>
      {children}
    </section>
  );
}
