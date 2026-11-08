"use client";

import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { api, erroresDeCampo } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { formatoFechaHora, formatoTamanio } from "@/lib/formato";
import { TIPOS_DOCUMENTO_SUGERIDOS } from "@/lib/etiquetas";
import type { Documento, Siniestro } from "@/lib/tipos";
import { Campo } from "../Campo";
import { AvisoAmbar, ErrorFormulario, Exito } from "../Avisos";
import { Cargando, ErrorCarga } from "../Estados";

export function PestanaDocumentos({ siniestro }: { siniestro: Siniestro }) {
  const documentos = useApi<Documento[]>(siniestro.es_responsable ? `/siniestros/${siniestro.id}/documentos` : null);
  const [tipo, setTipo] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [exito, setExito] = useState<string | null>(null);
  const [subiendo, setSubiendo] = useState(false);
  const entradaArchivo = useRef<HTMLInputElement>(null);

  if (!siniestro.es_responsable) {
    return (
      <AvisoAmbar>
        Los documentos son privados del perito responsable ({siniestro.perito.nombre}). No se muestran ni se pueden descargar.
      </AvisoAmbar>
    );
  }

  async function subir(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setExito(null);
    if (!archivo) {
      setError(new Error("sin archivo"));
      return;
    }
    const formulario = new FormData();
    formulario.append("archivo", archivo);
    formulario.append("tipo", tipo.trim());
    setSubiendo(true);
    try {
      await api(`/siniestros/${siniestro.id}/documentos`, { formulario });
      setExito(`Se subió «${archivo.name}».`);
      setArchivo(null);
      setTipo("");
      if (entradaArchivo.current) entradaArchivo.current.value = "";
      documentos.recargar();
    } catch (e) {
      setError(e);
    } finally {
      setSubiendo(false);
    }
  }

  const sinArchivo = error instanceof Error && error.message === "sin archivo";

  return (
    <div className="columna">
      <section className="tarjeta">
        <div className="tarjeta-cabecera">
          <h2>Subir documento</h2>
        </div>
        <form className="tarjeta-cuerpo" onSubmit={subir}>
          <div className="rejilla-campos col-2">
            <Campo etiqueta="Tipo de documento" id="doc-tipo" errores={erroresDeCampo(error, "tipo")}>
              <input id="doc-tipo" list="tipos-documento" value={tipo} onChange={(e) => setTipo(e.target.value)} required />
              <datalist id="tipos-documento">
                {TIPOS_DOCUMENTO_SUGERIDOS.map((t) => (
                  <option key={t} value={t} />
                ))}
              </datalist>
            </Campo>
            <Campo
              etiqueta="Archivo"
              id="doc-archivo"
              ayuda="Se guarda en un volumen privado. Solo vos podés descargarlo."
              errores={[...erroresDeCampo(error, "archivo"), ...(sinArchivo ? ["Elegí un archivo para subir."] : [])]}
            >
              <input id="doc-archivo" type="file" ref={entradaArchivo} onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
            </Campo>
          </div>
          {!sinArchivo ? <ErrorFormulario error={error} /> : null}
          {exito ? <Exito>{exito}</Exito> : null}
          <div className="acciones">
            <button type="submit" className="boton boton-principal" disabled={subiendo}>
              {subiendo ? "Subiendo…" : "Subir documento"}
            </button>
          </div>
        </form>
      </section>

      <section className="tarjeta">
        <div className="tarjeta-cabecera">
          <h2>Documentos del expediente</h2>
        </div>
        {documentos.cargando && !documentos.datos ? (
          <div className="tarjeta-cuerpo">
            <Cargando />
          </div>
        ) : null}
        {documentos.error ? (
          <div className="tarjeta-cuerpo">
            <ErrorCarga error={documentos.error} />
          </div>
        ) : null}
        {documentos.datos && documentos.datos.length === 0 ? <p className="vacio">Todavía no hay documentos cargados.</p> : null}
        {documentos.datos && documentos.datos.length > 0 ? (
          <div className="tabla-contenedor">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Tipo</th>
                  <th>Archivo</th>
                  <th>Estado</th>
                  <th>Fecha de carga</th>
                  <th>Tamaño</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {documentos.datos.map((d) => (
                  <tr key={d.id}>
                    <td>{d.tipo}</td>
                    <td>{d.nombre_original}</td>
                    <td>{d.estado === "recibido" ? "Recibido" : d.estado}</td>
                    <td>{formatoFechaHora(d.recibido_en)}</td>
                    <td>{formatoTamanio(d.tamanio)}</td>
                    <td>
                      {/* La descarga pasa por la API, que verifica el permiso: nunca hay una URL pública. */}
                      <a className="boton boton-chico" href={`/api/documentos/${d.id}/descargar`}>
                        Descargar
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>
    </div>
  );
}
