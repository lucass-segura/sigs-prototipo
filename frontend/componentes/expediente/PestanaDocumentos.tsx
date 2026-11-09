"use client";

import { useRef, useState } from "react";
import type { FormEvent } from "react";
import { api, erroresDeCampo, mensajeDeError } from "@/lib/api";
import { leerEscena } from "@/lib/croquis";
import type { Escena } from "@/lib/croquis";
import { useApi } from "@/lib/useApi";
import { formatoFechaHora, formatoTamanio } from "@/lib/formato";
import { TIPOS_DOCUMENTO_SUGERIDOS } from "@/lib/etiquetas";
import type { Documento, Siniestro } from "@/lib/tipos";
import { Campo } from "../Campo";
import { AvisoAmbar, ErrorFormulario } from "../Avisos";
import { ErrorCarga } from "../Estados";
import { EsqueletoTabla } from "../Esqueletos";
import { FilaActivable } from "../FilaActivable";
import { useNotificar } from "../Notificaciones";
import { DrawerCroquis } from "../croquis/DrawerCroquis";
import { Previsualizador } from "./Previsualizador";

export function PestanaDocumentos({ siniestro }: { siniestro: Siniestro }) {
  const documentos = useApi<Documento[]>(siniestro.es_responsable ? `/siniestros/${siniestro.id}/documentos` : null);
  const [tipo, setTipo] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [subiendo, setSubiendo] = useState(false);
  const notificar = useNotificar();
  const [verIndice, setVerIndice] = useState<number | null>(null);
  const [croquis, setCroquis] = useState<{ escena: Escena | null; basadoEn: number | null } | null>(null);
  const [abriendoCroquis, setAbriendoCroquis] = useState<number | null>(null);
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
      notificar.exito(`Se subió «${archivo.name}».`);
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
  const lista = documentos.datos ?? [];

  async function editarCroquis(d: Documento) {
    setAbriendoCroquis(d.id);
    try {
      const datos = await api<unknown>(`/documentos/${d.id}/escena`);
      const escena = leerEscena(datos);
      if (!escena) throw new Error("La escena guardada no tiene un formato compatible.");
      setVerIndice(null);
      setCroquis({ escena, basadoEn: d.id });
    } catch (e) {
      notificar.error(mensajeDeError(e));
    } finally {
      setAbriendoCroquis(null);
    }
  }

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
          <button type="button" className="boton boton-chico boton-principal" onClick={() => setCroquis({ escena: null, basadoEn: null })}>
            Nuevo croquis
          </button>
        </div>
        {documentos.cargando && !documentos.datos ? <EsqueletoTabla filas={3} columnas={5} etiqueta="Cargando documentos…" /> : null}
        {documentos.error ? (
          <div className="tarjeta-cuerpo">
            <ErrorCarga error={documentos.error} />
          </div>
        ) : null}
        {documentos.datos && documentos.datos.length === 0 ? (
          <div className="vacio-guia">
            <strong>Todavía no hay documentos cargados.</strong>
            <p>Subí fotos, actas o informes, o dibujá un croquis del siniestro. Solo vos podés verlos.</p>
            <button type="button" className="boton" onClick={() => setCroquis({ escena: null, basadoEn: null })}>
              Hacer un croquis
            </button>
          </div>
        ) : null}
        {documentos.datos && documentos.datos.length > 0 ? (
          <div className="tabla-contenedor">
            <table className="tabla tabla-apilada">
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
                {documentos.datos.map((d, i) => (
                  <FilaActivable key={d.id} etiqueta={`Ver ${d.nombre_original || d.tipo}`} alActivar={() => setVerIndice(i)}>
                    <td data-label="Tipo">
                      {d.tipo}
                      {d.tiene_escena ? <span className="etiqueta-chica">Editable</span> : null}
                    </td>
                    <td data-label="Archivo">{d.nombre_original}</td>
                    <td data-label="Estado">{d.estado === "recibido" ? "Recibido" : d.estado}</td>
                    <td data-label="Fecha de carga">{formatoFechaHora(d.recibido_en)}</td>
                    <td data-label="Tamaño">{formatoTamanio(d.tamanio)}</td>
                    <td>
                      <div className="acciones">
                        <button type="button" className="boton boton-chico" onClick={() => setVerIndice(i)}>
                          Ver
                        </button>
                        {d.tiene_escena ? (
                          <button type="button" className="boton boton-chico" disabled={abriendoCroquis === d.id} onClick={() => void editarCroquis(d)}>
                            {abriendoCroquis === d.id ? "Abriendo…" : "Editar"}
                          </button>
                        ) : null}
                        {/* La descarga pasa por la API, que verifica el permiso: nunca hay una URL pública. */}
                        <a className="boton boton-chico" href={`/api/documentos/${d.id}/descargar`}>
                          Descargar
                        </a>
                      </div>
                    </td>
                  </FilaActivable>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </section>

      {verIndice !== null ? (
        <Previsualizador
          documentos={lista}
          indice={Math.min(verIndice, lista.length - 1)}
          alCambiar={setVerIndice}
          alCerrar={() => setVerIndice(null)}
          alEditarCroquis={(d) => void editarCroquis(d)}
        />
      ) : null}
      {croquis ? (
        <DrawerCroquis
          idSiniestro={siniestro.id}
          numeroExpediente={siniestro.numero_expediente}
          escenaInicial={croquis.escena}
          basadoEn={croquis.basadoEn}
          alCerrar={() => setCroquis(null)}
          alGuardar={() => {
            setCroquis(null);
            documentos.recargar();
          }}
        />
      ) : null}
    </div>
  );
}
