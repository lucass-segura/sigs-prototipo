"use client";

import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { api, erroresDeCampo } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { formatoFechaHora } from "@/lib/formato";
import { ESCALA_VALORACION, ETIQUETA_RESULTADO, textoValoracion } from "@/lib/etiquetas";
import type { Cierre, Documento, ResultadoReclamo, RespuestaCierre, Siniestro } from "@/lib/tipos";
import { Campo } from "../Campo";
import { AvisoAmbar, ErrorFormulario } from "../Avisos";
import { Cargando, ErrorCarga } from "../Estados";

const RESULTADOS = Object.keys(ETIQUETA_RESULTADO) as ResultadoReclamo[];
const MAXIMO_JUSTIFICACION = 500;
const MAXIMO_OBSERVACION = 500;

interface DatosCierre {
  resultado: ResultadoReclamo;
  irregularidad: boolean;
  conclusion: string;
  valoracion: number | null;
  justificacion: string;
  motivo: string;
  /** Respaldo de la irregularidad: ids de documentos del expediente y/o una observación. */
  documentosRespaldo: number[];
  observacionRespaldo: string;
}

function datosIniciales(vigente: Cierre | null): DatosCierre {
  return {
    resultado: vigente?.resultado_reclamo ?? "aprobado",
    irregularidad: vigente?.irregularidad ?? false,
    conclusion: vigente?.conclusion ?? "",
    valoracion: vigente?.valoracion ?? null,
    justificacion: vigente?.justificacion ?? "",
    motivo: "",
    documentosRespaldo: vigente?.documentos_respaldo.map((d) => d.id) ?? [],
    observacionRespaldo: vigente?.observacion_respaldo ?? "",
  };
}

function SelectorValoracion({ valor, alElegir }: { valor: number | null; alElegir: (n: number) => void }) {
  return (
    <>
      <div className="valoracion" role="group" aria-label="Valoración de 1 a 10">
        {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
          <button key={n} type="button" aria-pressed={valor === n} onClick={() => alElegir(n)}>
            {n}
          </button>
        ))}
      </div>
      <div className="texto-escala" aria-live="polite">
        {valor ? `${valor}. ${textoValoracion(valor)}` : "Elegí un valor de 1 a 10."}
      </div>
    </>
  );
}

/** Respaldo de una irregularidad confirmada: documentos del expediente y/o una observación escrita. */
function BloqueRespaldo({
  idSiniestro,
  datos,
  cambiar,
  error,
}: {
  idSiniestro: number;
  datos: DatosCierre;
  cambiar: <K extends keyof DatosCierre>(clave: K, valor: DatosCierre[K]) => void;
  error: unknown;
}) {
  const documentos = useApi<Documento[]>(`/siniestros/${idSiniestro}/documentos`);
  const lista = documentos.datos ?? [];
  const errores = [
    ...erroresDeCampo(error, "respaldo"),
    ...erroresDeCampo(error, "documentos_respaldo"),
    ...erroresDeCampo(error, "observacion_respaldo"),
  ];

  function alternar(id: number) {
    cambiar(
      "documentosRespaldo",
      datos.documentosRespaldo.includes(id) ? datos.documentosRespaldo.filter((d) => d !== id) : [...datos.documentosRespaldo, id],
    );
  }

  return (
    <fieldset className="bloque-respaldo" aria-describedby="respaldo-ayuda">
      <legend>Respaldo de la irregularidad</legend>
      <p id="respaldo-ayuda" className="nota-pequena">
        Una irregularidad confirmada necesita respaldo: elegí al menos un documento del expediente (por ejemplo una fotografía)
        o escribí una observación. El respaldo queda en este expediente y no se comparte con otros peritos.
      </p>
      <div className="campo">
        <label>Documentos del expediente</label>
        {documentos.cargando && !documentos.datos ? <small className="ayuda">Cargando documentos…</small> : null}
        {documentos.error ? <small className="error-campo">No se pudieron cargar los documentos.</small> : null}
        {documentos.datos && lista.length === 0 ? (
          <small className="ayuda">Todavía no hay documentos. Subilos en la pestaña Documentos o escribí una observación.</small>
        ) : null}
        <div className="grupo-casillas">
          {lista.map((d) => (
            <label className="casilla" key={d.id}>
              <input type="checkbox" checked={datos.documentosRespaldo.includes(d.id)} onChange={() => alternar(d.id)} />
              {d.tipo} · {d.nombre_original || `Documento ${d.id}`}
            </label>
          ))}
        </div>
      </div>
      <div className="campo">
        <label htmlFor="cierre-observacion-respaldo">Observación de respaldo</label>
        <textarea
          id="cierre-observacion-respaldo"
          maxLength={MAXIMO_OBSERVACION}
          value={datos.observacionRespaldo}
          onChange={(e) => cambiar("observacionRespaldo", e.target.value)}
        />
        <div className="contador">
          {datos.observacionRespaldo.length} / {MAXIMO_OBSERVACION}
        </div>
      </div>
      {errores.length > 0 ? (
        <small className="error-campo" role="alert">
          {errores.join(" ")}
        </small>
      ) : null}
    </fieldset>
  );
}

function FormularioCierre({
  idSiniestro,
  vigente,
  alGuardar,
  alCancelar,
}: {
  idSiniestro: number;
  vigente: Cierre | null;
  alGuardar: () => void;
  alCancelar?: () => void;
}) {
  const esCambio = vigente !== null;
  const [datos, setDatos] = useState<DatosCierre>(() => datosIniciales(vigente));
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState(false);
  const [sinValoracion, setSinValoracion] = useState(false);

  function cambiar<K extends keyof DatosCierre>(clave: K, valor: DatosCierre[K]) {
    setDatos((d) => ({ ...d, [clave]: valor }));
  }

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setSinValoracion(false);
    if (datos.valoracion === null) {
      setSinValoracion(true);
      return;
    }
    setEnviando(true);
    try {
      await api(`/siniestros/${idSiniestro}/cierre`, {
        cuerpo: {
          resultado_reclamo: datos.resultado,
          irregularidad: datos.irregularidad,
          conclusion: datos.conclusion.trim(),
          valoracion: datos.valoracion,
          justificacion: datos.justificacion.trim(),
          ...(datos.irregularidad
            ? { documentos_respaldo: datos.documentosRespaldo, observacion_respaldo: datos.observacionRespaldo.trim() }
            : {}),
          ...(esCambio ? { motivo_cambio: datos.motivo.trim() } : {}),
        },
      });
      alGuardar();
    } catch (e) {
      setError(e);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} className="rejilla rejilla-principal">
      <div className="columna">
        <section className="tarjeta">
          <div className="tarjeta-cabecera">
            <h2>{esCambio ? "Cambiar valoración" : "Resultado"}</h2>
          </div>
          <div className="tarjeta-cuerpo">
            <div className="rejilla-campos col-2">
              <Campo etiqueta="Resultado del reclamo informado por la compañía" id="cierre-resultado" errores={erroresDeCampo(error, "resultado_reclamo")}>
                <select
                  id="cierre-resultado"
                  value={datos.resultado}
                  onChange={(e) => cambiar("resultado", e.target.value as ResultadoReclamo)}
                >
                  {RESULTADOS.map((r) => (
                    <option key={r} value={r}>
                      {ETIQUETA_RESULTADO[r]}
                    </option>
                  ))}
                </select>
              </Campo>
              <Campo
                etiqueta="Irregularidad confirmada"
                id="cierre-irregularidad"
                ayuda="Si es «Sí», hace falta un respaldo: un documento del expediente o una observación."
                errores={erroresDeCampo(error, "irregularidad")}
              >
                <select
                  id="cierre-irregularidad"
                  value={datos.irregularidad ? "si" : "no"}
                  onChange={(e) => cambiar("irregularidad", e.target.value === "si")}
                >
                  <option value="no">No</option>
                  <option value="si">Sí</option>
                </select>
              </Campo>
            </div>
            {datos.irregularidad ? (
              <BloqueRespaldo idSiniestro={idSiniestro} datos={datos} cambiar={cambiar} error={error} />
            ) : null}
            <Campo etiqueta="Conclusión pericial (obligatoria)" id="cierre-conclusion" errores={erroresDeCampo(error, "conclusion")}>
              <textarea id="cierre-conclusion" value={datos.conclusion} onChange={(e) => cambiar("conclusion", e.target.value)} />
            </Campo>
          </div>
        </section>

        <section className="tarjeta">
          <div className="tarjeta-cabecera">
            <h2>Valoración pericial</h2>
          </div>
          <div className="tarjeta-cuerpo">
            <div className="campo">
              <label>Confianza en la veracidad del hecho</label>
              <SelectorValoracion valor={datos.valoracion} alElegir={(n) => cambiar("valoracion", n)} />
              {sinValoracion ? <small className="error-campo">Elegí una valoración de 1 a 10.</small> : null}
              {erroresDeCampo(error, "valoracion").length > 0 ? (
                <small className="error-campo">{erroresDeCampo(error, "valoracion").join(" ")}</small>
              ) : null}
            </div>
            <ul className="leyenda-escala">
              {ESCALA_VALORACION.map((e) => (
                <li key={e.desde}>
                  {e.desde}–{e.hasta}: {e.texto}
                </li>
              ))}
            </ul>
            <Campo etiqueta="Justificación (obligatoria)" id="cierre-justificacion" errores={erroresDeCampo(error, "justificacion")}>
              <textarea
                id="cierre-justificacion"
                maxLength={MAXIMO_JUSTIFICACION}
                value={datos.justificacion}
                onChange={(e) => cambiar("justificacion", e.target.value)}
              />
              <div className="contador">
                {datos.justificacion.length} / {MAXIMO_JUSTIFICACION}
              </div>
            </Campo>
            {esCambio ? (
              <Campo etiqueta="Motivo del cambio (obligatorio)" id="cierre-motivo" errores={erroresDeCampo(error, "motivo_cambio")}>
                <textarea id="cierre-motivo" value={datos.motivo} onChange={(e) => cambiar("motivo", e.target.value)} />
              </Campo>
            ) : null}
          </div>
        </section>
      </div>

      <div className="columna">
        <section className="tarjeta">
          <div className="tarjeta-cuerpo">
            <h3>Se va a compartir</h3>
            <p>Tipo, fecha, resultado, irregularidad, valoración, justificación y perito responsable.</p>
            <h3>No se comparte</h3>
            <p>Documentos, fotos, notas, respaldo de la irregularidad y datos personales.</p>
          </div>
        </section>
        <AvisoAmbar>Un valor bajo no equivale a fraude confirmado.</AvisoAmbar>
        <ErrorFormulario error={error} />
        <button type="submit" className="boton boton-principal boton-ancho" disabled={enviando}>
          {enviando ? "Guardando…" : esCambio ? "Guardar nueva valoración" : "Cerrar expediente"}
        </button>
        {alCancelar ? (
          <button type="button" className="boton boton-ancho" onClick={alCancelar}>
            Cancelar
          </button>
        ) : null}
      </div>
    </form>
  );
}

/** Documentos y observación que respaldan una irregularidad (solo el perito responsable los ve). */
function Respaldo({ cierre }: { cierre: Cierre }) {
  if (cierre.documentos_respaldo.length === 0 && !cierre.observacion_respaldo) return <>—</>;
  return (
    <>
      {cierre.documentos_respaldo.length > 0 ? (
        <ul className="lista-simple">
          {cierre.documentos_respaldo.map((d) => (
            <li key={d.id}>
              {d.tipo} · {d.nombre_original || `Documento ${d.id}`}
            </li>
          ))}
        </ul>
      ) : null}
      {cierre.observacion_respaldo ? <p>{cierre.observacion_respaldo}</p> : null}
    </>
  );
}

function FilaDato({ clave, children }: { clave: string; children: ReactNode }) {
  return (
    <tr>
      <th scope="row">{clave}</th>
      <td>{children}</td>
    </tr>
  );
}

export function PestanaCierre({ siniestro, alCambiar }: { siniestro: Siniestro; alCambiar: () => void }) {
  const cierre = useApi<RespuestaCierre>(
    siniestro.estado === "borrador" || siniestro.estado === "anulado" ? null : `/siniestros/${siniestro.id}/cierre`,
  );
  const [cambiando, setCambiando] = useState(false);
  const [errorArchivo, setErrorArchivo] = useState<unknown>(null);
  const [archivando, setArchivando] = useState(false);

  if (siniestro.estado === "borrador") {
    return <AvisoAmbar>El cierre está disponible cuando el siniestro está confirmado y en análisis.</AvisoAmbar>;
  }
  if (siniestro.estado === "anulado") {
    return <AvisoAmbar>Un expediente anulado no se cierra.</AvisoAmbar>;
  }
  if (cierre.cargando && !cierre.datos) return <Cargando />;
  if (cierre.error) return <ErrorCarga error={cierre.error} />;

  const vigente = cierre.datos?.vigente ?? null;
  const historial = cierre.datos?.historial ?? [];

  async function guardado() {
    setCambiando(false);
    cierre.recargar();
    alCambiar();
  }

  async function archivar() {
    if (!window.confirm("¿Archivar el expediente? Se conserva todo y sigue contando como antecedente.")) return;
    setErrorArchivo(null);
    setArchivando(true);
    try {
      await api(`/siniestros/${siniestro.id}/archivar`, { metodo: "POST", cuerpo: {} });
      cierre.recargar();
      alCambiar();
    } catch (e) {
      setErrorArchivo(e);
    } finally {
      setArchivando(false);
    }
  }

  if (!vigente) {
    if (!siniestro.es_responsable) {
      return <AvisoAmbar>El expediente todavía no tiene cierre. Solo el perito responsable puede cerrarlo.</AvisoAmbar>;
    }
    return <FormularioCierre idSiniestro={siniestro.id} vigente={null} alGuardar={() => void guardado()} />;
  }

  if (cambiando && siniestro.es_responsable) {
    return (
      <FormularioCierre
        idSiniestro={siniestro.id}
        vigente={vigente}
        alGuardar={() => void guardado()}
        alCancelar={() => setCambiando(false)}
      />
    );
  }

  return (
    <div className="rejilla rejilla-principal">
      <div className="columna">
        <section className="tarjeta">
          <div className="tarjeta-cabecera">
            <h2>Cierre vigente</h2>
            <span className="meta">{formatoFechaHora(vigente.creado_en)}</span>
          </div>
          <div className="tabla-contenedor">
            <table className="tabla tabla-clave">
              <tbody>
                <FilaDato clave="Resultado del reclamo">{ETIQUETA_RESULTADO[vigente.resultado_reclamo]}</FilaDato>
                <FilaDato clave="Irregularidad confirmada">{vigente.irregularidad ? "Sí" : "No"}</FilaDato>
                {vigente.irregularidad ? (
                  <FilaDato clave="Respaldo de la irregularidad">
                    <Respaldo cierre={vigente} />
                  </FilaDato>
                ) : null}
                <FilaDato clave="Conclusión pericial">{vigente.conclusion || "—"}</FilaDato>
                <FilaDato clave="Valoración pericial">
                  <strong>{vigente.valoracion} / 10</strong>{" "}
                  <span className="nota-pequena">{vigente.valoracion_texto || textoValoracion(vigente.valoracion)}</span>
                </FilaDato>
                <FilaDato clave="Justificación">{vigente.justificacion}</FilaDato>
                <FilaDato clave="Perito responsable">{vigente.perito.nombre}</FilaDato>
              </tbody>
            </table>
          </div>
        </section>

        <section className="tarjeta">
          <div className="tarjeta-cabecera">
            <h2>Historial de valoraciones</h2>
            <span className="meta">
              {historial.length} {historial.length === 1 ? "registro" : "registros"}
            </span>
          </div>
          <div className="tabla-contenedor">
            <table className="tabla">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Valoración</th>
                  <th>Justificación</th>
                  <th>Irregularidad y respaldo</th>
                  <th>Motivo del cambio</th>
                  <th>Perito</th>
                </tr>
              </thead>
              <tbody>
                {[...historial]
                  .sort((a, b) => b.id - a.id)
                  .map((c) => (
                    <tr key={c.id} className={c.id === vigente.id ? undefined : "fila-tenue"}>
                      <td>{formatoFechaHora(c.creado_en)}</td>
                      <td>
                        <strong>{c.valoracion}</strong> / 10
                        {c.id === vigente.id ? <span className="etiqueta-chica">Vigente</span> : null}
                      </td>
                      <td>{c.justificacion}</td>
                      <td>{c.irregularidad ? <Respaldo cierre={c} /> : "No"}</td>
                      <td>{c.motivo_cambio || "—"}</td>
                      <td>{c.perito.nombre}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <div className="columna">
        <section className="tarjeta">
          <div className="tarjeta-cuerpo">
            <h3>Se va a compartir</h3>
            <p>Tipo, fecha, resultado, irregularidad, valoración, justificación y perito responsable.</p>
            <h3>No se comparte</h3>
            <p>Documentos, fotos, notas, respaldo de la irregularidad y datos personales.</p>
          </div>
        </section>
        <AvisoAmbar>Un valor bajo no equivale a fraude confirmado.</AvisoAmbar>
        {siniestro.es_responsable ? (
          <div className="columna">
            <button type="button" className="boton boton-principal boton-ancho" onClick={() => setCambiando(true)}>
              Cambiar valoración
            </button>
            {siniestro.estado === "cerrado" ? (
              <button type="button" className="boton boton-ancho" disabled={archivando} onClick={() => void archivar()}>
                {archivando ? "Archivando…" : "Archivar"}
              </button>
            ) : null}
            <ErrorFormulario error={errorArchivo} />
          </div>
        ) : null}
        {siniestro.estado === "archivado" ? (
          <p className="nota-pequena">Expediente archivado: se conserva todo y sigue contando como antecedente.</p>
        ) : null}
      </div>
    </div>
  );
}
