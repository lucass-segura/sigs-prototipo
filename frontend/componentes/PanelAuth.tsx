import type { ReactNode } from "react";

/** Pantalla dividida de las páginas públicas: marca a la izquierda, formulario a la derecha. */
export function PanelAuth({ titulo, subtitulo, children }: { titulo: string; subtitulo?: string; children: ReactNode }) {
  return (
    <div className="auth">
      <section className="auth-marca">
        <div>
          <h1>SIGS</h1>
          <p>
            Sistema Integral de Gestión de Siniestros y Prevención de Fraude. Expedientes, antecedentes y reglas
            explicables en un mismo lugar.
          </p>
        </div>
        <small>Prototipo académico. Datos ficticios.</small>
      </section>
      <section className="auth-formulario">
        <div className="auth-caja">
          <h2>{titulo}</h2>
          {subtitulo ? <p className="subtitulo">{subtitulo}</p> : null}
          {children}
        </div>
      </section>
    </div>
  );
}
