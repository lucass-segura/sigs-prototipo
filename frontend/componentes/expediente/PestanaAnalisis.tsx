"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { formatoDecimal, formatoFechaHora, formatoMesAnioCorto } from "@/lib/formato";
import { ETIQUETA_MOTIVO_EVALUACION, ETIQUETA_PRIORIDAD, ETIQUETA_RESULTADO } from "@/lib/etiquetas";
import type {
  Evaluacion,
  RespuestaCoincidencias,
  ResumenEvaluacion,
  Senal,
  Siniestro,
} from "@/lib/tipos";
import { AvisoAmbar, ErrorFormulario } from "../Avisos";
import { ErrorCarga } from "../Estados";
import { EsqueletoLineas } from "../Esqueletos";
import { useNotificar } from "../Notificaciones";
import { InsigniaEstado, InsigniaPrioridad } from "../Insignias";
import { FilaEnlace } from "../FilaActivable";

function ordenarSenales(senales: Senal[]): Senal[] {
  const peso = { activada: 0, no_evaluable: 1, no_activada: 2 } as const;
  return [...senales].sort((a, b) => peso[a.estado] - peso[b.estado] || a.codigo.localeCompare(b.codigo));
}

function FilaRegla({ senal, idSiniestro }: { senal: Senal; idSiniestro: number }) {
  const clase =
    senal.estado === "activada" ? "regla" : senal.estado === "no_evaluable" ? "regla regla-no-evaluable" : "regla regla-no-activada";
  return (
    <div className={clase}>
      <div className="regla-codigo">{senal.codigo}</div>
      <div>
        <div className="regla-nombre">
          {senal.nombre}
          {senal.estado === "no_evaluable" ? <span className="etiqueta-chica">No evaluable</span> : null}
        </div>
        <div className="regla-texto">{senal.texto || (senal.estado === "no_activada" ? "No se activó con los datos del caso." : "")}</div>
        {senal.estado === "activada" && senal.antecedentes.length > 0 ? (
          <div className="regla-antecedentes">
            Antecedentes:{" "}
            {senal.antecedentes.map((a, i) => (
              <span key={a.id}>
                {i > 0 ? ", " : ""}
                <Link href={`/expedientes/${idSiniestro}/antecedentes/${a.id}`}>{a.numero_expediente}</Link>
                {a.vinculo ? ` (${a.vinculo})` : ""}
              </span>
            ))}
          </div>
        ) : null}
      </div>
      <div className="regla-puntos" title={`Máximo ${senal.puntos_max}`}>
        {senal.puntos}
      </div>
    </div>
  );
}

function TarjetaIndicador({ evaluacion }: { evaluacion: Evaluacion }) {
  const grupos = Object.entries(evaluacion.grupos).filter(([, g]) => g.bruto > 0);
  return (
    <>
      <section className="tarjeta">
        <div className="tarjeta-cuerpo">
          <div className="subtitulo">Indicador de prioridad</div>
          <div className="indicador-numero">
            {evaluacion.puntaje} <small>/ 100</small>
          </div>
          <div>
            <InsigniaPrioridad prioridad={evaluacion.prioridad} texto={`Prioridad ${ETIQUETA_PRIORIDAD[evaluacion.prioridad].toLowerCase()}`} />
          </div>
          <div
            className={`barra-indicador ${evaluacion.prioridad}`}
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={evaluacion.puntaje}
            aria-label="Indicador de prioridad"
          >
            <div style={{ width: `${Math.min(100, Math.max(0, evaluacion.puntaje))}%` }} />
          </div>
          <div className="escala">Baja 0 a 24 · Media 25 a 49 · Alta 50 o más</div>
        </div>
      </section>

      <section className="tarjeta">
        <div className="tarjeta-cuerpo">
          <h3>Evaluación</h3>
          <ul className="lista-datos">
            <li>Reglas {evaluacion.version}</li>
            <li>Calculada el {formatoFechaHora(evaluacion.creada_en)}</li>
            <li>Motivo: {ETIQUETA_MOTIVO_EVALUACION[evaluacion.motivo] ?? evaluacion.motivo}</li>
            {grupos.map(([nombre, g]) => (
              <li key={nombre}>
                {nombre} {g.bruto > g.tope ? `${g.bruto} puntos, tope ${g.tope}` : `${g.puntos} puntos`}
              </li>
            ))}
          </ul>
        </div>
      </section>
    </>
  );
}

const LEYENDA_PRIORIDAD = "La prioridad ordena qué revisar primero. No indica que haya fraude.";

export function PestanaAnalisis({ siniestro }: { siniestro: Siniestro }) {
  const confirmado = siniestro.estado === "en_analisis" || siniestro.estado === "cerrado" || siniestro.estado === "archivado";
  const base = `/siniestros/${siniestro.id}`;
  const [pagina, setPagina] = useState(1);
  const evaluacion = useApi<Evaluacion>(confirmado ? `${base}/evaluacion` : null);
  const historial = useApi<ResumenEvaluacion[]>(confirmado ? `${base}/evaluaciones` : null);
  const coincidencias = useApi<RespuestaCoincidencias>(confirmado ? `${base}/coincidencias?pagina=${pagina}` : null);
  const notificar = useNotificar();
  const [recalculando, setRecalculando] = useState(false);
  const [errorRecalculo, setErrorRecalculo] = useState<unknown>(null);

  async function recalcular() {
    setErrorRecalculo(null);
    setRecalculando(true);
    try {
      await api(`${base}/recalcular`, { metodo: "POST", cuerpo: {} });
      evaluacion.recargar();
      historial.recargar();
      notificar.exito("Se recalculó el indicador con las reglas vigentes.");
    } catch (e) {
      setErrorRecalculo(e);
    } finally {
      setRecalculando(false);
    }
  }

  if (!confirmado) {
    return (
      <div className="columna">
        <AvisoAmbar>
          {siniestro.estado === "borrador"
            ? "Solo un siniestro confirmado se analiza. Confirmá el borrador desde la pestaña Datos."
            : "Un expediente anulado no se analiza."}
        </AvisoAmbar>
        <AvisoAmbar>{LEYENDA_PRIORIDAD}</AvisoAmbar>
      </div>
    );
  }

  const ev = evaluacion.datos;
  const senales = ev ? ordenarSenales(ev.senales) : [];
  const activadas = senales.filter((s) => s.estado === "activada").length;
  const noActivadas = senales.filter((s) => s.estado === "no_activada").length;
  const noEvaluables = senales.filter((s) => s.estado === "no_evaluable").length;
  const co = coincidencias.datos;

  return (
    <div className="rejilla rejilla-analisis">
      <div className="columna">
        {evaluacion.cargando && !evaluacion.datos ? <EsqueletoLineas lineas={5} etiqueta="Cargando el análisis…" /> : null}
        {evaluacion.error && evaluacion.error.estado !== 404 ? <ErrorCarga error={evaluacion.error} /> : null}
        {evaluacion.error?.estado === 404 ? <AvisoAmbar>Todavía no hay una evaluación calculada para este expediente.</AvisoAmbar> : null}
        {ev ? <TarjetaIndicador evaluacion={ev} /> : null}
        {siniestro.es_responsable ? (
          <div className="columna">
            <button type="button" className="boton" disabled={recalculando} onClick={() => void recalcular()}>
              {recalculando ? "Recalculando…" : "Recalcular"}
            </button>
            <ErrorFormulario error={errorRecalculo} />
          </div>
        ) : null}
        <AvisoAmbar>{LEYENDA_PRIORIDAD}</AvisoAmbar>
        {historial.datos && historial.datos.length > 1 ? (
          <section className="tarjeta">
            <div className="tarjeta-cabecera">
              <h2>Historial de evaluaciones</h2>
            </div>
            <div className="tabla-contenedor">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Versión</th>
                    <th>Puntaje</th>
                  </tr>
                </thead>
                <tbody>
                  {historial.datos.map((h) => (
                    <tr key={h.id}>
                      <td>{formatoFechaHora(h.creada_en)}</td>
                      <td>{h.version}</td>
                      <td>
                        <InsigniaPrioridad prioridad={h.prioridad} puntaje={h.puntaje} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        ) : null}
      </div>

      <div className="columna">
        {ev ? (
          <section className="tarjeta">
            <div className="tarjeta-cabecera">
              <h2>Reglas evaluadas</h2>
              <span className="meta">
                {activadas} {activadas === 1 ? "activada" : "activadas"} · {noActivadas} sin activar
                {noEvaluables > 0 ? ` · ${noEvaluables} no ${noEvaluables === 1 ? "evaluable" : "evaluables"}` : ""}
              </span>
            </div>
            {senales.map((s) => (
              <FilaRegla key={s.codigo} senal={s} idSiniestro={siniestro.id} />
            ))}
          </section>
        ) : null}

        <section className="tarjeta">
          <div className="tarjeta-cabecera">
            <h2>Coincidencias en la red</h2>
          </div>
          {coincidencias.cargando && !co ? <p className="vacio">Buscando coincidencias…</p> : null}
          {coincidencias.error ? (
            <div className="tarjeta-cuerpo">
              <ErrorCarga error={coincidencias.error} />
            </div>
          ) : null}
          {co && co.resultados.length === 0 ? (
            <p className="vacio">{co.mensaje_vacio ?? "No hay antecedentes accesibles en la red"}</p>
          ) : null}
          {co && co.resultados.length > 0 ? (
            <>
              <div className="tabla-contenedor">
                <table className="tabla tabla-apilada">
                  <thead>
                    <tr>
                      <th>Antecedente</th>
                      <th>Vínculo</th>
                      <th>Fecha</th>
                      <th>Resultado</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {co.resultados.map((c) => (
                      <FilaEnlace
                        key={c.antecedente_id}
                        href={`/expedientes/${siniestro.id}/antecedentes/${c.antecedente_id}`}
                        etiqueta={`Ver el resumen del antecedente ${c.numero_expediente}`}
                      >
                        <td className="mono-celda" data-label="Antecedente">{c.numero_expediente}</td>
                        <td data-label="Vínculo">{c.descripcion_vinculo}</td>
                        <td data-label="Fecha">{formatoMesAnioCorto(c.fecha_hecho)}</td>
                        <td data-label="Resultado">
                          {c.resultado_reclamo ? ETIQUETA_RESULTADO[c.resultado_reclamo] : <InsigniaEstado estado={c.estado} />}
                        </td>
                        <td>
                          <Link
                            href={`/expedientes/${siniestro.id}/antecedentes/${c.antecedente_id}`}
                            className="boton boton-chico"
                          >
                            Ver resumen
                          </Link>
                        </td>
                      </FilaEnlace>
                    ))}
                  </tbody>
                </table>
              </div>
              {co.paginas > 1 ? (
                <div className="paginacion">
                  <button type="button" className="boton boton-chico" disabled={pagina <= 1} onClick={() => setPagina((p) => p - 1)}>
                    Anterior
                  </button>
                  <span>
                    Página {co.pagina} de {co.paginas} · {co.total} coincidencias
                  </span>
                  <button
                    type="button"
                    className="boton boton-chico"
                    disabled={pagina >= co.paginas}
                    onClick={() => setPagina((p) => p + 1)}
                  >
                    Siguiente
                  </button>
                </div>
              ) : null}
              <div className="pie-tarjeta">
                {co.promedio_valoracion.promedio !== null ? (
                  <>
                    Valoración promedio de los antecedentes vinculados{" "}
                    <strong>{formatoDecimal(co.promedio_valoracion.promedio)}</strong> en {co.promedio_valoracion.cantidad}{" "}
                    {co.promedio_valoracion.cantidad === 1 ? "caso" : "casos"}. Se calcula solo para este análisis.
                  </>
                ) : (
                  "Ningún antecedente vinculado tiene valoración pericial todavía."
                )}
              </div>
            </>
          ) : null}
        </section>
      </div>
    </div>
  );
}
