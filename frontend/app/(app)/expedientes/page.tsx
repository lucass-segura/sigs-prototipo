"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useApi } from "@/lib/useApi";
import { useSesion } from "@/lib/sesion";
import { formatoFecha } from "@/lib/formato";
import { ETIQUETA_ESTADO } from "@/lib/etiquetas";
import type { EstadoSiniestro, RespuestaPanel } from "@/lib/tipos";
import { EncabezadoPagina, Vista } from "@/componentes/Vista";
import { ProtegerRol } from "@/componentes/ProtegerRol";
import { ErrorCarga } from "@/componentes/Estados";
import { EsqueletoTabla, EsqueletoTarjetas } from "@/componentes/Esqueletos";
import { FilaEnlace } from "@/componentes/FilaActivable";
import { InsigniaEstado, InsigniaPrioridad } from "@/componentes/Insignias";
import { Campo } from "@/componentes/Campo";

function PanelExpedientes() {
  const { usuario } = useSesion();
  const { datos, error, cargando } = useApi<RespuestaPanel>("/siniestros");
  const [filtrando, setFiltrando] = useState(false);
  const [estado, setEstado] = useState<"" | EstadoSiniestro>("");
  const [texto, setTexto] = useState("");

  const filas = useMemo(() => {
    if (!datos) return [];
    const buscado = texto.trim().toLowerCase();
    return datos.resultados.filter((s) => {
      if (estado && s.estado !== estado) return false;
      if (!buscado) return true;
      return [s.numero_expediente, s.tipo, s.bien_principal ?? ""].some((v) => v.toLowerCase().includes(buscado));
    });
  }, [datos, estado, texto]);

  return (
    <Vista
      migas={[{ texto: "Expedientes" }]}
      accion={
        <Link href="/expedientes/nuevo" className="boton boton-principal">
          Nuevo siniestro
        </Link>
      }
    >
      <EncabezadoPagina
        titulo="Mis expedientes"
        subtitulo={`Casos asignados en el espacio ${usuario?.espacio?.nombre ?? ""}, ordenados por prioridad.`}
      />
      {cargando && !datos ? (
        <>
          <EsqueletoTarjetas etiqueta="Cargando el resumen…" />
          <section className="tarjeta">
            <EsqueletoTabla filas={6} columnas={7} etiqueta="Cargando expedientes…" />
          </section>
        </>
      ) : null}
      {error ? <ErrorCarga error={error} /> : null}
      {datos ? (
        <>
          <div className="resumen-tarjetas">
            <div className="tarjeta tarjeta-numero">
              <div className="etiqueta">En análisis</div>
              <div className="numero">{datos.resumen.en_analisis}</div>
            </div>
            <div className="tarjeta tarjeta-numero">
              <div className="etiqueta">Prioridad alta</div>
              <div className="numero rojo">{datos.resumen.prioridad_alta}</div>
            </div>
            <div className="tarjeta tarjeta-numero">
              <div className="etiqueta">Tareas vencen esta semana</div>
              <div className="numero">{datos.resumen.tareas_vencen_semana}</div>
            </div>
            <div className="tarjeta tarjeta-numero">
              <div className="etiqueta">Cerrados en el mes</div>
              <div className="numero">{datos.resumen.cerrados_mes}</div>
            </div>
          </div>

          <section className="tarjeta">
            <div className="tarjeta-cabecera">
              <h2>Expedientes</h2>
              <button type="button" className="boton" aria-expanded={filtrando} onClick={() => setFiltrando((f) => !f)}>
                Filtrar
              </button>
            </div>
            {filtrando ? (
              <div className="herramientas">
                <Campo etiqueta="Estado" id="filtro-estado">
                  <select id="filtro-estado" value={estado} onChange={(e) => setEstado(e.target.value as "" | EstadoSiniestro)}>
                    <option value="">Todos</option>
                    {(Object.keys(ETIQUETA_ESTADO) as EstadoSiniestro[]).map((clave) => (
                      <option key={clave} value={clave}>
                        {ETIQUETA_ESTADO[clave]}
                      </option>
                    ))}
                  </select>
                </Campo>
                <Campo etiqueta="Buscar por expediente, tipo o bien" id="filtro-texto">
                  <input id="filtro-texto" value={texto} onChange={(e) => setTexto(e.target.value)} />
                </Campo>
              </div>
            ) : null}
            {filas.length === 0 ? (
              <div className="vacio-guia">
                {datos.resultados.length === 0 ? (
                  <>
                    <strong>Todavía no tenés expedientes asignados.</strong>
                    <p>Registrá el primer siniestro: queda en borrador hasta que lo confirmes.</p>
                    <Link href="/expedientes/nuevo" className="boton boton-principal">
                      Nuevo siniestro
                    </Link>
                  </>
                ) : (
                  <>
                    <strong>Ningún expediente coincide con el filtro.</strong>
                    <button
                      type="button"
                      className="boton"
                      onClick={() => {
                        setEstado("");
                        setTexto("");
                      }}
                    >
                      Limpiar filtro
                    </button>
                  </>
                )}
              </div>
            ) : (
              <div className="tabla-contenedor">
                <table className="tabla tabla-apilada">
                  <thead>
                    <tr>
                      <th>Expediente</th>
                      <th>Fecha del hecho</th>
                      <th>Tipo</th>
                      <th>Bien</th>
                      <th>Estado</th>
                      <th>Prioridad</th>
                      <th>Tareas</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filas.map((s) => (
                      <FilaEnlace key={s.id} href={`/expedientes/${s.id}`} etiqueta={`Abrir el expediente ${s.numero_expediente}, ${s.tipo}`}>
                        <td className="mono-celda" data-label="Expediente">
                          <Link href={`/expedientes/${s.id}`} tabIndex={-1}>
                            {s.numero_expediente}
                          </Link>
                        </td>
                        <td data-label="Fecha del hecho">{formatoFecha(s.fecha_hecho)}</td>
                        <td data-label="Tipo">{s.tipo}</td>
                        <td data-label="Bien">{s.bien_principal ?? "—"}</td>
                        <td data-label="Estado">
                          <InsigniaEstado estado={s.estado} />
                        </td>
                        <td className={s.prioridad ? undefined : "sin-evaluar"} data-label="Prioridad">
                          {s.prioridad ? <InsigniaPrioridad prioridad={s.prioridad} puntaje={s.puntaje} /> : "Sin evaluar"}
                        </td>
                        <td data-label="Tareas">{s.tareas_pendientes}</td>
                      </FilaEnlace>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : null}
    </Vista>
  );
}

export default function PaginaExpedientes() {
  return (
    <ProtegerRol roles={["perito"]}>
      <PanelExpedientes />
    </ProtegerRol>
  );
}
