"use client";

import { useMemo, useState } from "react";
import type { FormEvent } from "react";
import { api, erroresDeCampo } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { estaVencida, formatoDiaMes, formatoFechaHora } from "@/lib/formato";
import { ESTADOS_TAREA, ETIQUETA_ESTADO_TAREA } from "@/lib/etiquetas";
import type { EstadoTarea, Nota, Siniestro, Tarea } from "@/lib/tipos";
import { Campo } from "../Campo";
import { AvisoAmbar, ErrorFormulario } from "../Avisos";
import { Cargando, ErrorCarga } from "../Estados";

function nombreUsuarioCambio(usuario: Tarea["cambios"][number]["usuario"]): string {
  if (!usuario) return "";
  return typeof usuario === "string" ? usuario : usuario.nombre;
}

function Tablero({ idSiniestro }: { idSiniestro: number }) {
  const tareas = useApi<Tarea[]>(`/siniestros/${idSiniestro}/tareas`);
  const [creando, setCreando] = useState(false);
  const [titulo, setTitulo] = useState("");
  const [vence, setVence] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [errorCambio, setErrorCambio] = useState<unknown>(null);
  const [columnaSobre, setColumnaSobre] = useState<EstadoTarea | null>(null);
  const [ocupada, setOcupada] = useState<number | null>(null);

  const columnas = useMemo(() => {
    const porEstado: Record<EstadoTarea, Tarea[]> = { pendiente: [], en_curso: [], hecha: [] };
    for (const t of tareas.datos ?? []) porEstado[t.estado]?.push(t);
    return porEstado;
  }, [tareas.datos]);

  async function crear(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    try {
      await api(`/siniestros/${idSiniestro}/tareas`, {
        cuerpo: { titulo: titulo.trim(), ...(vence ? { vence_en: vence } : {}) },
      });
      setTitulo("");
      setVence("");
      setCreando(false);
      tareas.recargar();
    } catch (e) {
      setError(e);
    }
  }

  async function mover(tarea: Tarea, estado: EstadoTarea) {
    if (tarea.estado === estado) return;
    setErrorCambio(null);
    setOcupada(tarea.id);
    try {
      await api(`/tareas/${tarea.id}`, { metodo: "PATCH", cuerpo: { estado } });
      tareas.recargar();
    } catch (e) {
      setErrorCambio(e);
    } finally {
      setOcupada(null);
    }
  }

  return (
    <div className="columna">
      <div className="tarjeta-cabecera" style={{ border: 0, padding: 0 }}>
        <h2>Tareas</h2>
        <button type="button" className="boton boton-chico" onClick={() => setCreando((c) => !c)} aria-expanded={creando}>
          Nueva tarea
        </button>
      </div>

      {creando ? (
        <form className="tarjeta tarjeta-cuerpo" onSubmit={crear}>
          <div className="rejilla-campos col-2">
            <Campo etiqueta="Título" id="tarea-titulo" errores={erroresDeCampo(error, "titulo")}>
              <input id="tarea-titulo" value={titulo} onChange={(e) => setTitulo(e.target.value)} required />
            </Campo>
            <Campo etiqueta="Vencimiento (opcional)" id="tarea-vence" errores={erroresDeCampo(error, "vence_en")}>
              <input id="tarea-vence" type="date" value={vence} onChange={(e) => setVence(e.target.value)} />
            </Campo>
          </div>
          <ErrorFormulario error={error} />
          <div className="acciones">
            <button type="submit" className="boton boton-principal">
              Crear tarea
            </button>
            <button type="button" className="boton" onClick={() => setCreando(false)}>
              Cancelar
            </button>
          </div>
        </form>
      ) : null}

      {tareas.cargando && !tareas.datos ? <Cargando /> : null}
      {tareas.error ? <ErrorCarga error={tareas.error} /> : null}
      <ErrorFormulario error={errorCambio} />

      {tareas.datos ? (
        <div className="tablero">
          {ESTADOS_TAREA.map((estado) => (
            <div
              key={estado}
              className={`columna-tablero${columnaSobre === estado ? " sobre" : ""}`}
              onDragOver={(e) => {
                e.preventDefault();
                setColumnaSobre(estado);
              }}
              onDragLeave={() => setColumnaSobre((actual) => (actual === estado ? null : actual))}
              onDrop={(e) => {
                e.preventDefault();
                setColumnaSobre(null);
                const id = Number(e.dataTransfer.getData("text/plain"));
                const tarea = (tareas.datos ?? []).find((t) => t.id === id);
                if (tarea) void mover(tarea, estado);
              }}
            >
              <h3>
                {ETIQUETA_ESTADO_TAREA[estado]} <span>{columnas[estado].length}</span>
              </h3>
              {columnas[estado].map((t) => (
                <article
                  key={t.id}
                  className="tarea"
                  draggable
                  onDragStart={(e) => e.dataTransfer.setData("text/plain", String(t.id))}
                >
                  <div className="tarea-titulo">{t.titulo}</div>
                  {t.vence_en ? (
                    <div className={`tarea-meta${t.estado !== "hecha" && estaVencida(t.vence_en) ? " vencida" : ""}`}>
                      Vence {formatoDiaMes(t.vence_en)}
                    </div>
                  ) : (
                    <div className="tarea-meta">Sin vencimiento</div>
                  )}
                  <div className="tarea-acciones">
                    {ESTADOS_TAREA.filter((e) => e !== t.estado).map((e) => (
                      <button
                        key={e}
                        type="button"
                        className="boton boton-chico"
                        disabled={ocupada === t.id}
                        onClick={() => void mover(t, e)}
                      >
                        Pasar a {ETIQUETA_ESTADO_TAREA[e].toLowerCase()}
                      </button>
                    ))}
                  </div>
                  {t.cambios && t.cambios.length > 0 ? (
                    <details>
                      <summary>Historial ({t.cambios.length})</summary>
                      <ul className="lista-datos">
                        {t.cambios.map((c, i) => (
                          <li key={i}>
                            {formatoFechaHora(c.fecha)} · {c.estado_anterior ? `${ETIQUETA_ESTADO_TAREA[c.estado_anterior]} → ` : ""}
                            {ETIQUETA_ESTADO_TAREA[c.estado_nuevo]}
                            {nombreUsuarioCambio(c.usuario) ? ` · ${nombreUsuarioCambio(c.usuario)}` : ""}
                          </li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                </article>
              ))}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Notas({ idSiniestro }: { idSiniestro: number }) {
  const notas = useApi<Nota[]>(`/siniestros/${idSiniestro}/notas`);
  const [agregando, setAgregando] = useState(false);
  const [texto, setTexto] = useState("");
  const [error, setError] = useState<unknown>(null);

  async function agregar(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    try {
      await api(`/siniestros/${idSiniestro}/notas`, { cuerpo: { texto: texto.trim() } });
      setTexto("");
      setAgregando(false);
      notas.recargar();
    } catch (e) {
      setError(e);
    }
  }

  const ordenadas = useMemo(
    () => [...(notas.datos ?? [])].sort((a, b) => b.creada_en.localeCompare(a.creada_en)),
    [notas.datos],
  );

  return (
    <section className="tarjeta">
      <div className="tarjeta-cabecera">
        <h2>Notas privadas</h2>
        <button type="button" className="boton boton-chico" onClick={() => setAgregando((a) => !a)} aria-expanded={agregando}>
          Agregar
        </button>
      </div>
      {agregando ? (
        <form className="tarjeta-cuerpo" onSubmit={agregar}>
          <Campo etiqueta="Nota" id="nota-texto" errores={erroresDeCampo(error, "texto")}>
            <textarea id="nota-texto" value={texto} onChange={(e) => setTexto(e.target.value)} required />
          </Campo>
          <ErrorFormulario error={error} />
          <div className="acciones">
            <button type="submit" className="boton boton-principal">
              Guardar nota
            </button>
            <button type="button" className="boton" onClick={() => setAgregando(false)}>
              Cancelar
            </button>
          </div>
        </form>
      ) : null}
      {notas.cargando && !notas.datos ? <p className="vacio">Cargando…</p> : null}
      {notas.error ? (
        <div className="tarjeta-cuerpo">
          <ErrorCarga error={notas.error} />
        </div>
      ) : null}
      {notas.datos && ordenadas.length === 0 ? <p className="vacio">Todavía no hay notas.</p> : null}
      <ul className="notas-lista">
        {ordenadas.map((n) => (
          <li key={n.id}>
            <div className="nota-meta">
              {formatoFechaHora(n.creada_en)} · {n.autor.nombre}
            </div>
            <div className="nota-texto">{n.texto}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function PestanaSeguimiento({ siniestro }: { siniestro: Siniestro }) {
  if (!siniestro.es_responsable) {
    return (
      <AvisoAmbar>
        Las tareas y las notas son privadas del perito responsable ({siniestro.perito.nombre}).
      </AvisoAmbar>
    );
  }
  return (
    <div className="rejilla rejilla-seguimiento">
      <Tablero idSiniestro={siniestro.id} />
      <Notas idSiniestro={siniestro.id} />
    </div>
  );
}
