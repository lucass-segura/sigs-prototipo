import Link from "next/link";
import type { ReactNode } from "react";

export interface Miga {
  texto: string;
  href?: string;
}

/** Barra superior con migas de pan + contenido de la pantalla. */
export function Vista({
  migas,
  accion,
  children,
}: {
  migas: Miga[];
  accion?: ReactNode;
  children: ReactNode;
}) {
  return (
    <>
      <header className="barra-superior">
        <nav className="migas" aria-label="Ruta de navegación">
          {migas.map((miga, i) => {
            const ultima = i === migas.length - 1;
            return (
              <span key={`${miga.texto}-${i}`}>
                {miga.href && !ultima ? <Link href={miga.href}>{miga.texto}</Link> : ultima ? <strong>{miga.texto}</strong> : miga.texto}
                {!ultima ? <span className="miga-separador"> / </span> : null}
              </span>
            );
          })}
        </nav>
        {accion ? <div className="barra-accion">{accion}</div> : null}
      </header>
      <main id="contenido-principal" className="pagina" tabIndex={-1}>{children}</main>
    </>
  );
}

export function EncabezadoPagina({
  titulo,
  subtitulo,
  lateral,
}: {
  titulo: ReactNode;
  subtitulo?: ReactNode;
  lateral?: ReactNode;
}) {
  return (
    <div className="encabezado-pagina">
      <div>
        <h1>{titulo}</h1>
        {subtitulo ? <p className="subtitulo">{subtitulo}</p> : null}
      </div>
      {lateral ? <div className="encabezado-lateral">{lateral}</div> : null}
    </div>
  );
}
