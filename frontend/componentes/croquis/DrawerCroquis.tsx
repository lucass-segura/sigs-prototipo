"use client";

// Cajón lateral con el editor de croquis. Guardar crea un documento nuevo de tipo «Croquis» (PNG + escena reeditable).
import { useCallback, useRef, useState } from "react";
import { api } from "@/lib/api";
import { escenaVacia, tieneContenido } from "@/lib/croquis";
import type { Escena } from "@/lib/croquis";
import { useAtrapaFoco } from "@/lib/useAtrapaFoco";
import { ErrorFormulario } from "../Avisos";
import { useConfirmar } from "../Confirmar";
import { useNotificar } from "../Notificaciones";
import { EditorCroquis } from "./EditorCroquis";

const ESCALA_PNG = 1.5;

/** Serializa el SVG del editor (sin las marcas de edición) y lo dibuja en un canvas para obtener el PNG. */
async function exportarPng(svg: SVGSVGElement, ancho: number, alto: number): Promise<Blob> {
  const copia = svg.cloneNode(true) as SVGSVGElement;
  copia.querySelectorAll("[data-solo-editor]").forEach((n) => n.remove());
  copia.removeAttribute("style");
  copia.removeAttribute("class");
  copia.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  copia.setAttribute("width", String(ancho));
  copia.setAttribute("height", String(alto));
  const xml = new XMLSerializer().serializeToString(copia);
  const url = URL.createObjectURL(new Blob([xml], { type: "image/svg+xml;charset=utf-8" }));
  try {
    const imagen = new Image();
    await new Promise<void>((ok, fallo) => {
      imagen.onload = () => ok();
      imagen.onerror = () => fallo(new Error("No se pudo generar la imagen del croquis."));
      imagen.src = url;
    });
    const lienzo = document.createElement("canvas");
    lienzo.width = Math.round(ancho * ESCALA_PNG);
    lienzo.height = Math.round(alto * ESCALA_PNG);
    const contexto = lienzo.getContext("2d");
    if (!contexto) throw new Error("No se pudo generar la imagen del croquis.");
    contexto.fillStyle = "#ffffff";
    contexto.fillRect(0, 0, lienzo.width, lienzo.height);
    contexto.drawImage(imagen, 0, 0, lienzo.width, lienzo.height);
    return await new Promise<Blob>((ok, fallo) =>
      lienzo.toBlob((b) => (b ? ok(b) : fallo(new Error("No se pudo generar la imagen del croquis."))), "image/png"),
    );
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function DrawerCroquis({
  idSiniestro,
  numeroExpediente,
  escenaInicial,
  basadoEn,
  alCerrar,
  alGuardar,
}: {
  idSiniestro: number;
  numeroExpediente: string;
  /** Escena de un croquis guardado; sin ella, el croquis empieza vacío. */
  escenaInicial: Escena | null;
  /** Id del documento del que se parte al editar: el original no se modifica. */
  basadoEn: number | null;
  alCerrar: () => void;
  alGuardar: () => void;
}) {
  const confirmar = useConfirmar();
  const notificar = useNotificar();
  const caja = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const escenaActual = useRef<Escena>(escenaInicial ?? escenaVacia());
  const [sinGuardar, setSinGuardar] = useState(false);
  const [vacio, setVacio] = useState(!tieneContenido(escenaActual.current));
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [inicial] = useState(() => escenaInicial ?? escenaVacia());

  const cerrar = useCallback(async () => {
    if (guardando) return;
    if (sinGuardar) {
      const si = await confirmar({
        titulo: "¿Cerrar sin guardar?",
        mensaje: "Hay cambios en el croquis que todavía no se guardaron. Si cerrás ahora, se pierden.",
        confirmar: "Cerrar sin guardar",
        cancelar: "Seguir editando",
        peligro: true,
      });
      if (!si) return;
    }
    alCerrar();
  }, [guardando, sinGuardar, confirmar, alCerrar]);

  useAtrapaFoco(caja, () => void cerrar());

  const alCambiar = useCallback((escena: Escena, cambios: boolean) => {
    escenaActual.current = escena;
    setSinGuardar(cambios);
    setVacio(!tieneContenido(escena));
  }, []);

  async function guardar() {
    const svg = svgRef.current;
    if (!svg) return;
    setError(null);
    setGuardando(true);
    try {
      const escena = escenaActual.current;
      const png = await exportarPng(svg, escena.ancho, escena.alto);
      const formulario = new FormData();
      formulario.append("imagen", png, "croquis.png");
      formulario.append("escena", JSON.stringify(escena));
      if (basadoEn !== null) formulario.append("basado_en", String(basadoEn));
      await api(`/siniestros/${idSiniestro}/croquis`, { formulario });
      notificar.exito(basadoEn !== null ? "Se guardó el croquis como documento nuevo. El original no se modificó." : "Se guardó el croquis en los documentos del expediente.");
      alGuardar();
    } catch (e) {
      setError(e);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="drawer-fondo" onMouseDown={(e) => e.target === e.currentTarget && void cerrar()}>
      <div ref={caja} className="drawer drawer-croquis" role="dialog" aria-modal="true" aria-labelledby="croquis-titulo">
        <header className="drawer-cabecera">
          <div>
            <h2 id="croquis-titulo">{basadoEn !== null ? "Editar croquis" : "Nuevo croquis"}</h2>
            <p className="nota-pequena">
              Expediente <span className="mono">{numeroExpediente}</span>
              {basadoEn !== null ? " · al guardar se crea un documento nuevo" : ""}
            </p>
          </div>
          <button type="button" className="boton" onClick={() => void cerrar()}>
            Cerrar
          </button>
        </header>
        <div className="drawer-cuerpo">
          <EditorCroquis escena={inicial} alCambiar={alCambiar} svgRef={svgRef} />
        </div>
        <footer className="drawer-pie">
          <div className="drawer-pie-mensaje">
            <ErrorFormulario error={error} />
            {!error ? (
              <p className="nota-pequena">
                {sinGuardar ? "Hay cambios sin guardar." : "Sin cambios."} El croquis es ilustrativo y no tiene escala.
              </p>
            ) : null}
          </div>
          <div className="acciones">
            <button type="button" className="boton" onClick={() => void cerrar()} disabled={guardando}>
              Cancelar
            </button>
            <button type="button" className="boton boton-principal" onClick={() => void guardar()} disabled={guardando || vacio} title={vacio ? "Agregá al menos un elemento" : undefined}>
              {guardando ? "Guardando…" : basadoEn !== null ? "Guardar como croquis nuevo" : "Guardar croquis"}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
