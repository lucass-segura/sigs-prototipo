"use client";

// Vista previa de documentos dentro de la app: imágenes con zoom, PDF y texto. Anterior y siguiente recorren la lista.
// La API solo entrega en línea tipos seguros (nunca HTML ni SVG); lo demás se descarga.
import { useEffect, useRef, useState } from "react";
import { formatoFechaHora, formatoTamanio } from "@/lib/formato";
import type { Documento } from "@/lib/tipos";
import { useAtrapaFoco } from "@/lib/useAtrapaFoco";
import { EsqueletoLineas } from "../Esqueletos";

const NIVELES_ZOOM = [0.5, 1, 1.5, 2, 3, 4];
const MAX_CARACTERES = 200_000;

function urlVer(d: Documento) {
  return `/api/documentos/${d.id}/ver`;
}

function esImagen(tipo: string | null) {
  return tipo !== null && tipo.startsWith("image/");
}

function Texto({ documento }: { documento: Documento }) {
  const [estado, setEstado] = useState<{ id: number; texto: string | null; fallo: boolean } | null>(null);

  useEffect(() => {
    let vigente = true;
    fetch(urlVer(documento), { credentials: "same-origin" })
      .then(async (r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.text();
      })
      .then((texto) => vigente && setEstado({ id: documento.id, texto, fallo: false }))
      .catch(() => vigente && setEstado({ id: documento.id, texto: null, fallo: true }));
    return () => {
      vigente = false;
    };
  }, [documento]);

  if (!estado || estado.id !== documento.id) return <EsqueletoLineas lineas={6} etiqueta="Cargando el texto…" />;
  if (estado.fallo || estado.texto === null) return <SinVistaPrevia documento={documento} />;
  const cortado = estado.texto.length > MAX_CARACTERES;
  return (
    <>
      <pre className="previa-texto" tabIndex={0} aria-label={`Contenido de ${documento.nombre_original}`}>
        {cortado ? estado.texto.slice(0, MAX_CARACTERES) : estado.texto}
      </pre>
      {cortado ? <p className="nota-pequena previa-aviso">Se muestra el comienzo del archivo. Descargalo para verlo completo.</p> : null}
    </>
  );
}

function SinVistaPrevia({ documento }: { documento: Documento }) {
  return (
    <div className="vacio-guia previa-sin">
      <strong>Este archivo no se puede previsualizar.</strong>
      <p>
        Por seguridad solo se muestran imágenes (PNG, JPG, GIF, WebP), PDF y texto plano. {documento.nombre_original} se puede descargar.
      </p>
      <a className="boton boton-principal" href={`/api/documentos/${documento.id}/descargar`}>
        Descargar
      </a>
    </div>
  );
}

function Imagen({ documento, zoom, alAlternar }: { documento: Documento; zoom: number; alAlternar: () => void }) {
  const [fallo, setFallo] = useState(false);
  const [cargada, setCargada] = useState(false);
  if (fallo) return <SinVistaPrevia documento={documento} />;
  return (
    <>
      {!cargada ? <EsqueletoLineas lineas={4} etiqueta="Cargando la imagen…" /> : null}
      {/* eslint-disable-next-line @next/next/no-img-element -- la imagen sale de la API con permiso, no de una URL pública */}
      <img
        src={urlVer(documento)}
        alt={`${documento.tipo}: ${documento.nombre_original}`}
        className={`previa-imagen${zoom === 1 ? " previa-imagen-ajustada" : ""}`}
        style={zoom === 1 ? undefined : { width: `${zoom * 100}%` }}
        hidden={!cargada}
        onLoad={() => setCargada(true)}
        onError={() => setFallo(true)}
        onDoubleClick={alAlternar}
        draggable={false}
      />
    </>
  );
}

export function Previsualizador({
  documentos,
  indice,
  alCambiar,
  alCerrar,
  alEditarCroquis,
}: {
  documentos: Documento[];
  indice: number;
  alCambiar: (indice: number) => void;
  alCerrar: () => void;
  alEditarCroquis?: (documento: Documento) => void;
}) {
  const caja = useRef<HTMLDivElement>(null);
  const cerrar = useRef<HTMLButtonElement>(null);
  const [zoom, setZoom] = useState(1);
  const documento = documentos[indice];
  const hayAnterior = indice > 0;
  const haySiguiente = indice < documentos.length - 1;

  useAtrapaFoco(caja, alCerrar, cerrar);

  // Cada documento empieza ajustado a la ventana.
  useEffect(() => setZoom(1), [indice]);

  useEffect(() => {
    function alPulsar(e: KeyboardEvent) {
      if (e.defaultPrevented || (e.target as HTMLElement).closest("input, textarea, select")) return;
      if (e.key === "ArrowLeft" && hayAnterior) {
        e.preventDefault();
        alCambiar(indice - 1);
      } else if (e.key === "ArrowRight" && haySiguiente) {
        e.preventDefault();
        alCambiar(indice + 1);
      } else if ((e.key === "+" || e.key === "=") && esImagen(documento?.previsualizable ?? null)) {
        setZoom((z) => NIVELES_ZOOM[Math.min(NIVELES_ZOOM.length - 1, NIVELES_ZOOM.indexOf(z) + 1)] ?? z);
      } else if (e.key === "-" && esImagen(documento?.previsualizable ?? null)) {
        setZoom((z) => NIVELES_ZOOM[Math.max(0, NIVELES_ZOOM.indexOf(z) - 1)] ?? z);
      }
    }
    window.addEventListener("keydown", alPulsar);
    return () => window.removeEventListener("keydown", alPulsar);
  }, [indice, hayAnterior, haySiguiente, alCambiar, documento]);

  if (!documento) return null;
  const tipo = documento.previsualizable;
  const nivel = NIVELES_ZOOM.indexOf(zoom);

  return (
    <div className="modal-fondo" onMouseDown={(e) => e.target === e.currentTarget && alCerrar()}>
      <div ref={caja} className="previa" role="dialog" aria-modal="true" aria-labelledby="previa-titulo">
        <header className="previa-cabecera">
          <div className="previa-titulo">
            <h2 id="previa-titulo">{documento.nombre_original || `Documento ${documento.id}`}</h2>
            <p className="nota-pequena">
              {documento.tipo} · {formatoFechaHora(documento.recibido_en)} · {formatoTamanio(documento.tamanio)} · {indice + 1} de {documentos.length}
            </p>
          </div>
          <div className="acciones previa-acciones">
            {esImagen(tipo) ? (
              <div className="editor-grupo" role="group" aria-label="Zoom">
                <button type="button" className="boton boton-chico" aria-label="Alejar" disabled={nivel <= 0} onClick={() => setZoom(NIVELES_ZOOM[nivel - 1])}>
                  −
                </button>
                <button type="button" className="boton boton-chico" aria-label="Ajustar a la ventana" onClick={() => setZoom(1)}>
                  {Math.round(zoom * 100)} %
                </button>
                <button type="button" className="boton boton-chico" aria-label="Acercar" disabled={nivel >= NIVELES_ZOOM.length - 1} onClick={() => setZoom(NIVELES_ZOOM[nivel + 1])}>
                  +
                </button>
              </div>
            ) : null}
            {documento.tiene_escena && alEditarCroquis ? (
              <button type="button" className="boton boton-chico" onClick={() => alEditarCroquis(documento)}>
                Editar croquis
              </button>
            ) : null}
            <a className="boton boton-chico" href={`/api/documentos/${documento.id}/descargar`}>
              Descargar
            </a>
            <button ref={cerrar} type="button" className="boton boton-chico" onClick={alCerrar} aria-label="Cerrar la vista previa (Esc)">
              Cerrar
            </button>
          </div>
        </header>
        <div className={`previa-cuerpo${esImagen(tipo) ? " previa-cuerpo-imagen" : ""}`}>
          {tipo === null ? <SinVistaPrevia documento={documento} /> : null}
          {esImagen(tipo) ? <Imagen key={documento.id} documento={documento} zoom={zoom} alAlternar={() => setZoom((z) => (z === 1 ? 2 : 1))} /> : null}
          {tipo === "application/pdf" ? <iframe key={documento.id} className="previa-pdf" src={urlVer(documento)} title={`PDF: ${documento.nombre_original}`} /> : null}
          {tipo === "text/plain" ? <Texto key={documento.id} documento={documento} /> : null}
        </div>
        <footer className="previa-pie">
          <button type="button" className="boton" disabled={!hayAnterior} onClick={() => alCambiar(indice - 1)}>
            Anterior
          </button>
          <span className="nota-pequena previa-ayuda">Teclas izquierda y derecha para cambiar de documento · Esc para cerrar</span>
          <button type="button" className="boton" disabled={!haySiguiente} onClick={() => alCambiar(indice + 1)}>
            Siguiente
          </button>
        </footer>
      </div>
    </div>
  );
}
