"use client";

import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { api, erroresDeCampo } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { formatoFechaHora } from "@/lib/formato";
import { ESCALA_VALORACION, ETIQUETA_RESULTADO, textoValoracion } from "@/lib/etiquetas";
import type { Cierre, ResultadoReclamo, RespuestaCierre, Siniestro } from "@/lib/tipos";
import { Campo } from "../Campo";
import { AvisoAmbar, ErrorFormulario } from "../Avisos";
import { Cargando, ErrorCarga } from "../Estados";

const RESULTADOS = Object.keys(ETIQUETA_RESULTADO) as ResultadoReclamo[];
const MAXIMO_JUSTIFICACION = 500;

interface DatosCierre {
  resultado: ResultadoReclamo;
  irregularidad: boolean;
  conclusion: string;
  valoracion: number | null;
  justificacion: string;
  motivo: string;
}

function datosIniciales(vigente: Cierre | null): DatosCierre {
  return {
    resultado: vigente?.resultado_reclamo ?? "aprobado",
    irregularidad: vigente?.irregularidad ?? false,
    conclusion: vigente?.conclusion ?? "",
    valoracion: vigente?.valoracion ?? null,
    justificacion: vigente?.justificacion ?? "",
    motivo: "",
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
        {valor ? `${valor}. ${textoValoracion(valor)}.` : "Elegí un valor de 1 a 10."}
      </div>
    </>
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
              <Campo etiqueta="Irregularidad confirmada" id="cierre-irregularidad" errores={erroresDeCampo(error, "irregularidad")}>
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
            <Campo etiqueta="Conclusión pericial" id="cierre-conclusion" errores={erroresDeCampo(error, "conclusion")}>
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
            <p>Documentos, fotos, notas y datos personales.</p>
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
            <p>Documentos, fotos, notas y datos personales.</p>
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
