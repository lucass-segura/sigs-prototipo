"use client";

import { useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { estaVencida, formatoFecha } from "@/lib/formato";
import { ETIQUETA_ESTADO_TAREA } from "@/lib/etiquetas";
import type { EstadoTarea, TareaConExpediente } from "@/lib/tipos";
import { EncabezadoPagina, Vista } from "@/componentes/Vista";
import { ProtegerRol } from "@/componentes/ProtegerRol";
import { Cargando, ErrorCarga, Vacio } from "@/componentes/Estados";
import { ErrorFormulario } from "@/componentes/Avisos";

function Tareas() {
  const { datos, error, cargando, recargar } = useApi<TareaConExpediente[]>("/tareas");
  const [errorCambio, setErrorCambio] = useState<unknown>(null);
  const [ocupada, setOcupada] = useState<number | null>(null);

  async function mover(id: number, estado: EstadoTarea) {
    setErrorCambio(null);
    setOcupada(id);
    try {
      await api(`/tareas/${id}`, { metodo: "PATCH", cuerpo: { estado } });
      recargar();
    } catch (e) {
      setErrorCambio(e);
    } finally {
      setOcupada(null);
    }
  }

  const ordenadas = [...(datos ?? [])].sort((a, b) => (a.vence_en ?? "9999").localeCompare(b.vence_en ?? "9999"));

  return (
    <Vista migas={[{ texto: "Tareas" }]}>
      <EncabezadoPagina titulo="Tareas" subtitulo="Tareas pendientes y en curso de tus expedientes, las que vencen primero arriba." />
      {cargando && !datos ? <Cargando /> : null}
      {error ? <ErrorCarga error={error} /> : null}
      <ErrorFormulario error={errorCambio} />
      {datos ? (
        <section className="tarjeta">
          {ordenadas.length === 0 ? (
            <Vacio>No tenés tareas pendientes.</Vacio>
          ) : (
            <div className="tabla-contenedor">
              <table className="tabla">
                <thead>
                  <tr>
                    <th>Tarea</th>
                    <th>Expediente</th>
                    <th>Estado</th>
                    <th>Vence</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {ordenadas.map((t) => (
                    <tr key={t.id}>
                      <td>{t.titulo}</td>
                      <td className="mono-celda">
                        <Link href={`/expedientes/${t.siniestro.id}?tab=seguimiento`}>{t.siniestro.numero_expediente}</Link>
                        <div className="nota-pequena" style={{ fontFamily: "inherit" }}>
                          {t.siniestro.tipo}
                        </div>
                      </td>
                      <td>{ETIQUETA_ESTADO_TAREA[t.estado]}</td>
                      <td style={estaVencida(t.vence_en) ? { color: "var(--rojo)", fontWeight: 600 } : undefined}>
                        {t.vence_en ? formatoFecha(t.vence_en) : "—"}
                      </td>
                      <td>
                        <div className="acciones">
                          {t.estado === "pendiente" ? (
                            <button type="button" className="boton boton-chico" disabled={ocupada === t.id} onClick={() => void mover(t.id, "en_curso")}>
                              Pasar a en curso
                            </button>
                          ) : null}
                          <button type="button" className="boton boton-chico" disabled={ocupada === t.id} onClick={() => void mover(t.id, "hecha")}>
                            Marcar como hecha
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      ) : null}
    </Vista>
  );
}

export default function PaginaTareas() {
  return (
    <ProtegerRol roles={["perito"]}>
      <Tareas />
    </ProtegerRol>
  );
}
