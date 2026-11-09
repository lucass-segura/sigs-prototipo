"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api, erroresDeCampo, mensajeDeError } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { formatoDiaMes, formatoFechaHora, hoyISO } from "@/lib/formato";
import { grupoDeVencimiento, insigniaDeVencimiento } from "@/lib/vencimientos";
import { ESTADOS_TAREA, ETIQUETA_ESTADO_TAREA } from "@/lib/etiquetas";
import type { EstadoTarea, Nota, Siniestro, Tarea } from "@/lib/tipos";
import { Campo } from "../Campo";
import { AvisoAmbar, ErrorFormulario } from "../Avisos";
import { ErrorCarga } from "../Estados";
import { SelectorFecha } from "../fechas/SelectorFecha";
import { useValidezFechas } from "../fechas/useValidezFechas";
import { EsqueletoLineas } from "../Esqueletos";
import { useNotificar } from "../Notificaciones";

function nombreUsuarioCambio(usuario: Tarea["cambios"][number]["usuario"]): string {
  if (!usuario) return "";
  return typeof usuario === "string" ? usuario : usuario.nombre;
}

function BotonesMover({
  tarea,
  ocupada,
  alMover,
}: {
  tarea: Tarea;
  ocupada: boolean;
  alMover: (tarea: Tarea, estado: EstadoTarea) => void;
}) {
  const opciones: { destino: EstadoTarea; texto: string; ayuda: string }[] =
    tarea.estado === "pendiente"
      ? [
          { destino: "en_curso", texto: "Pasar a en curso", ayuda: "Pasar a en curso" },
          { destino: "hecha", texto: "Marcar como hecha", ayuda: "Marcar como hecha" },
        ]
      : tarea.estado === "en_curso"
        ? [
            { destino: "pendiente", texto: "Volver a pendiente", ayuda: "Volver a pendiente" },
            { destino: "hecha", texto: "Marcar como hecha", ayuda: "Marcar como hecha" },
          ]
        : [{ destino: "pendiente", texto: "Reabrir", ayuda: "Reabrir como pendiente" }];
  return (
    <div className="tarea-acciones">
      {opciones.map((o) => (
        <button
          key={o.destino}
          type="button"
          className="boton boton-chico"
          aria-label={`${o.ayuda}: ${tarea.titulo}`}
          disabled={ocupada}
          onClick={() => alMover(tarea, o.destino)}
        >
          {o.texto}
        </button>
      ))}
    </div>
  );
}

function Tablero({ idSiniestro }: { idSiniestro: number }) {
  const tareas = useApi<Tarea[]>(`/siniestros/${idSiniestro}/tareas`);
  const notificar = useNotificar();
  const [creando, setCreando] = useState(false);
  const [titulo, setTitulo] = useState("");
  const [vence, setVence] = useState("");
  const validez = useValidezFechas();
  const [error, setError] = useState<unknown>(null);
  const [guardando, setGuardando] = useState(false);
  const [columnaSobre, setColumnaSobre] = useState<EstadoTarea | null>(null);
  const [ocupada, setOcupada] = useState<number | null>(null);
  const campoTitulo = useRef<HTMLInputElement>(null);

  const columnas = useMemo(() => {
    const porEstado: Record<EstadoTarea, Tarea[]> = { pendiente: [], en_curso: [], hecha: [] };
    for (const t of tareas.datos ?? []) porEstado[t.estado]?.push(t);
    // Dentro de cada columna, las que vencen primero arriba y las que no tienen fecha al final.
    for (const lista of Object.values(porEstado)) {
      lista.sort((a, b) => (a.vence_en ?? "9999").localeCompare(b.vence_en ?? "9999") || a.id - b.id);
    }
    return porEstado;
  }, [tareas.datos]);

  const vencidas = columnas.pendiente.concat(columnas.en_curso).filter((t) => grupoDeVencimiento(t.estado, t.vence_en) === "vencida").length;
  const abiertas = columnas.pendiente.length + columnas.en_curso.length;

  useEffect(() => {
    if (creando) campoTitulo.current?.focus();
  }, [creando]);

  async function crear(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    if (validez.revisar()) return;
    setGuardando(true);
    try {
      await api(`/siniestros/${idSiniestro}/tareas`, {
        cuerpo: { titulo: titulo.trim(), ...(vence ? { vence_en: vence } : {}) },
      });
      notificar.exito(`Se agregó la tarea «${titulo.trim()}».`);
      setTitulo("");
      setVence("");
      tareas.recargar();
      campoTitulo.current?.focus();
    } catch (e) {
      setError(e);
    } finally {
      setGuardando(false);
    }
  }

  async function mover(tarea: Tarea, estado: EstadoTarea) {
    if (tarea.estado === estado) return;
    setOcupada(tarea.id);
    try {
      await api(`/tareas/${tarea.id}`, { metodo: "PATCH", cuerpo: { estado } });
      notificar.exito(`«${tarea.titulo}» pasó a ${ETIQUETA_ESTADO_TAREA[estado].toLowerCase()}.`);
      tareas.recargar();
    } catch (e) {
      notificar.error(mensajeDeError(e));
    } finally {
      setOcupada(null);
    }
  }

  return (
    <div className="columna">
      <div className="tarjeta-cabecera" style={{ border: 0, padding: 0 }}>
        <div>
          <h2>Tareas</h2>
          {tareas.datos ? (
            <p className="nota-pequena">
              {abiertas} {abiertas === 1 ? "abierta" : "abiertas"}
              {vencidas > 0 ? (
                <>
                  {" · "}
                  <span className="texto-vencida">
                    {vencidas} {vencidas === 1 ? "vencida" : "vencidas"}
                  </span>
                </>
              ) : null}
            </p>
          ) : null}
        </div>
        <button
          type="button"
          className="boton boton-chico"
          onClick={() => setCreando((c) => !c)}
          aria-expanded={creando}
          aria-controls="alta-rapida-tarea"
        >
          Nueva tarea
        </button>
      </div>

      {tareas.cargando && !tareas.datos ? <EsqueletoLineas lineas={4} etiqueta="Cargando tareas…" /> : null}
      {tareas.error ? <ErrorCarga error={tareas.error} /> : null}

      {tareas.datos ? (
        <>
          <p className="nota-pequena">Arrastrá las tarjetas entre columnas o usá los botones de cada una.</p>
          <div className="tablero">
            {ESTADOS_TAREA.map((estado) => (
              <div
                key={estado}
                className={`columna-tablero columna-${estado}${columnaSobre === estado ? " sobre" : ""}`}
                role="group"
                aria-label={`${ETIQUETA_ESTADO_TAREA[estado]}: ${columnas[estado].length}`}
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

                {estado === "pendiente" && creando ? (
                  <form id="alta-rapida-tarea" className="tarea tarea-alta" onSubmit={crear}>
                    <Campo etiqueta="Tarea nueva" id="tarea-titulo" errores={erroresDeCampo(error, "titulo")}>
                      <input
                        id="tarea-titulo"
                        ref={campoTitulo}
                        value={titulo}
                        onChange={(e) => setTitulo(e.target.value)}
                        placeholder="Qué hay que hacer"
                        required
                      />
                    </Campo>
                    <Campo etiqueta="Vence (opcional)" id="tarea-vence" errores={erroresDeCampo(error, "vence_en")}>
                      <SelectorFecha
                        id="tarea-vence"
                        etiqueta="Vencimiento de la tarea"
                        valor={vence}
                        onCambio={setVence}
                        atajos={["hoy", "manana", "en7dias", "finDeMes", "sinFecha"]}
                        aviso={(v) => (v < hoyISO() ? "Esa fecha ya pasó: la tarea va a figurar como vencida." : null)}
                        {...validez.props("tarea-vence")}
                      />
                    </Campo>
                    <ErrorFormulario error={error} />
                    <div className="acciones">
                      <button type="submit" className="boton boton-principal boton-chico" disabled={guardando}>
                        {guardando ? "Agregando…" : "Agregar"}
                      </button>
                      <button type="button" className="boton boton-chico" onClick={() => setCreando(false)}>
                        Cerrar
                      </button>
                    </div>
                  </form>
                ) : null}

                {columnas[estado].length === 0 && !(estado === "pendiente" && creando) ? (
                  <p className="columna-vacia">{estado === "hecha" ? "Todavía no cerraste tareas." : "Sin tareas."}</p>
                ) : null}

                {columnas[estado].map((t) => {
                  const venc = insigniaDeVencimiento(t.estado, t.vence_en);
                  const vencida = grupoDeVencimiento(t.estado, t.vence_en) === "vencida";
                  return (
                    <article
                      key={t.id}
                      className={`tarea${vencida ? " tarea-vencida" : ""}`}
                      draggable
                      onDragStart={(e) => e.dataTransfer.setData("text/plain", String(t.id))}
                    >
                      <div className="tarea-titulo">{t.titulo}</div>
                      <div className="tarea-meta">
                        {t.estado === "hecha" ? (
                          t.vence_en ? `Vencía el ${formatoDiaMes(t.vence_en)}` : "Sin vencimiento"
                        ) : (
                          <span className={`insignia insignia-venc-${venc.clase}`}>{venc.texto}</span>
                        )}
                      </div>
                      <BotonesMover tarea={t} ocupada={ocupada === t.id} alMover={(tarea, e) => void mover(tarea, e)} />
                      {t.cambios && t.cambios.length > 0 ? (
                        <details>
                          <summary>Historial ({t.cambios.length})</summary>
                          <ol className="historial-tarea">
                            {t.cambios.map((c, i) => (
                              <li key={i}>
                                <span className="historial-fecha">{formatoFechaHora(c.fecha)}</span>
                                <span>
                                  {c.estado_anterior ? `De ${ETIQUETA_ESTADO_TAREA[c.estado_anterior]} a ` : "Creada en "}
                                  <strong>{ETIQUETA_ESTADO_TAREA[c.estado_nuevo]}</strong>
                                  {nombreUsuarioCambio(c.usuario) ? ` · ${nombreUsuarioCambio(c.usuario)}` : ""}
                                </span>
                              </li>
                            ))}
                          </ol>
                        </details>
                      ) : null}
                    </article>
                  );
                })}

                {estado === "pendiente" && !creando ? (
                  <button type="button" className="boton-agregar" onClick={() => setCreando(true)}>
                    + Agregar tarea
                  </button>
                ) : null}
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}

function Notas({ idSiniestro }: { idSiniestro: number }) {
  const notas = useApi<Nota[]>(`/siniestros/${idSiniestro}/notas`);
  const notificar = useNotificar();
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
      notificar.exito("Se guardó la nota.");
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
      {notas.cargando && !notas.datos ? (
        <div className="tarjeta-cuerpo">
          <EsqueletoLineas lineas={3} etiqueta="Cargando notas…" />
        </div>
      ) : null}
      {notas.error ? (
        <div className="tarjeta-cuerpo">
          <ErrorCarga error={notas.error} />
        </div>
      ) : null}
      {notas.datos && ordenadas.length === 0 ? <p className="vacio">Todavía no hay notas. Usá «Agregar» para dejar la primera: son privadas y solo las ves vos.</p> : null}
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
