import type { ReactNode } from "react";

/** Etiqueta + control + errores de campo (los muestra la pantalla que llama). */
export function Campo({
  etiqueta,
  id,
  ayuda,
  errores,
  children,
  className,
}: {
  etiqueta: string;
  id?: string;
  ayuda?: string;
  errores?: string[];
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`campo${className ? ` ${className}` : ""}`}>
      <label htmlFor={id}>{etiqueta}</label>
      {children}
      {ayuda ? <small className="ayuda">{ayuda}</small> : null}
      {errores && errores.length > 0 ? (
        <small className="error-campo" role="alert">
          {errores.join(" ")}
        </small>
      ) : null}
    </div>
  );
}
