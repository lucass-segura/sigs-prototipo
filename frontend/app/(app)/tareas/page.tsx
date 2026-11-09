"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { api, mensajeDeError } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { formatoFecha } from "@/lib/formato";
import { ETIQUETA_ESTADO_TAREA, FILTROS_ESTADO_TAREA } from "@/lib/etiquetas";
import type { FiltroEstadoTarea } from "@/lib/etiquetas";
import { grupoDeVencimiento, insigniaDeVencimiento, ORDEN_GRUPOS, TITULO_GRUPO } from "@/lib/vencimientos";
import type { GrupoVencimiento } from "@/lib/vencimientos";
import type { EstadoTarea, TareaConExpediente } from "@/lib/tipos";
import { EncabezadoPagina, Vista } from "@/componentes/Vista";
import { ProtegerRol } from "@/componentes/ProtegerRol";
import { ErrorCarga } from "@/componentes/Estados";
import { EsqueletoLineas } from "@/componentes/Esqueletos";
import { EnlaceExtendido } from "@/componentes/EnlaceExtendido";
import { useNotificar } from "@/componentes/Notificaciones";
import { Campo } from "@/componentes/Campo";

type FiltroVencimiento = "todas" | "vencidas" | "semana" | "sin_fecha";

const FILTROS_VENCIMIENTO: { valor: FiltroVencimiento; texto: string }[] = [
  { valor: "todas", texto: "Todas" },
  { valor: "vencidas", texto: "Vencidas" },
  { valor: "semana", texto: "Esta semana" },
  { valor: "sin_fecha", texto: "Sin fecha" },
];

function coincideVencimiento(filtro: FiltroVencimiento, grupo: GrupoVencimiento): boolean {
  if (filtro === "todas") return true;
  if (filtro === "vencidas") return grupo === "vencida";
  if (filtro === "semana") return grupo === "hoy" || grupo === "semana";
  return grupo === "sin_fecha";
}

function leerFiltro<T extends string>(valor: string | null, validos: readonly T[], porDefecto: T): T {
  return validos.includes(valor as T) ? (valor as T) : porDefecto;
}

function Tareas() {
  const consulta = useSearchParams();
  const router = useRouter();
  const ruta = usePathname();
  const notificar = useNotificar();

  // Los filtros viven en la URL: se pueden compartir, recargar y volver con «atrás».
  const estado = leerFiltro<FiltroEstadoTarea>(consulta.get("estado"), FILTROS_ESTADO_TAREA.map((f) => f.valor), "abiertas");
  const vencimiento = leerFiltro<FiltroVencimiento>(consulta.get("vence"), FILTROS_VENCIMIENTO.map((f) => f.valor), "todas");
  const expediente = consulta.get("exp") ?? "";
  const textoUrl = consulta.get("q") ?? "";

  const [texto, setTexto] = useState(textoUrl);
  const [ocupada, setOcupada] = useState<number | null>(null);

  const { datos, error, cargando, recargar } = useApi<TareaConExpediente[]>(estado === "abiertas" ? "/tareas" : `/tareas?estado=${estado}`);

  function cambiarUrl(cambios: Record<string, string>) {
    const parametros = new URLSearchParams(consulta.toString());
    for (const [clave, valor] of Object.entries(cambios)) {
      if (valor) parametros.set(clave, valor);
      else parametros.delete(clave);
    }
    const cadena = parametros.toString();
    router.replace(cadena ? `${ruta}?${cadena}` : ruta, { scroll: false });
  }

  // El texto se pasa a la URL con una pequeña espera para no reescribirla en cada tecla.
  const consultaRef = useRef(consulta);
  consultaRef.current = consulta;
  const escrito = useRef(textoUrl);
  useEffect(() => {
    if (texto.trim() === (consultaRef.current.get("q") ?? "")) return;
    const espera = window.setTimeout(() => {
      const parametros = new URLSearchParams(consultaRef.current.toString());
      escrito.current = texto.trim();
      if (texto.trim()) parametros.set("q", texto.trim());
      else parametros.delete("q");
      const cadena = parametros.toString();
      router.replace(cadena ? `${ruta}?${cadena}` : ruta, { scroll: false });
    }, 250);
    return () => window.clearTimeout(espera);
  }, [texto, router, ruta]);

  // «Atrás» o un enlace con otro texto actualizan el campo.
  useEffect(() => {
    if (textoUrl !== escrito.current) {
      escrito.current = textoUrl;
      setTexto(textoUrl);
    }
  }, [textoUrl]);

  const expedientes = useMemo(() => {
    const mapa = new Map<number, string>();
    for (const t of datos ?? []) mapa.set(t.siniestro.id, t.siniestro.numero_expediente);
    return [...mapa.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [datos]);

  // Lo que cumple texto, expediente y estado; el vencimiento se cuenta aparte para mostrar los totales.
  const base = useMemo(() => {
    const buscado = textoUrl.trim().toLowerCase();
    return (datos ?? []).filter((t) => {
      if (expediente && String(t.siniestro.id) !== expediente) return false;
      if (!buscado) return true;
      return [t.titulo, t.siniestro.numero_expediente, t.siniestro.tipo].some((v) => v.toLowerCase().includes(buscado));
    });
  }, [datos, textoUrl, expediente]);

  const conGrupo = useMemo(() => base.map((t) => ({ tarea: t, grupo: grupoDeVencimiento(t.estado, t.vence_en) })), [base]);
  const totales = useMemo(() => {
    const cuenta = { todas: conGrupo.length, vencidas: 0, semana: 0, sin_fecha: 0 };
    for (const { grupo } of conGrupo) {
      if (grupo === "vencida") cuenta.vencidas++;
      else if (grupo === "hoy" || grupo === "semana") cuenta.semana++;
      else if (grupo === "sin_fecha") cuenta.sin_fecha++;
    }
    return cuenta;
  }, [conGrupo]);

  const visibles = conGrupo.filter(({ grupo }) => coincideVencimiento(vencimiento, grupo));
  const grupos = ORDEN_GRUPOS.map((g) => ({ grupo: g, tareas: visibles.filter((v) => v.grupo === g).map((v) => v.tarea) })).filter((g) => g.tareas.length > 0);
  const hayFiltros = estado !== "abiertas" || vencimiento !== "todas" || expediente !== "" || textoUrl !== "";

  function limpiar() {
    escrito.current = "";
    setTexto("");
    router.replace(ruta, { scroll: false });
  }

  async function mover(t: TareaConExpediente, nuevo: EstadoTarea) {
    setOcupada(t.id);
    try {
      await api(`/tareas/${t.id}`, { metodo: "PATCH", cuerpo: { estado: nuevo } });
      notificar.exito(`«${t.titulo}» pasó a ${ETIQUETA_ESTADO_TAREA[nuevo].toLowerCase()}.`);
      recargar();
    } catch (e) {
      notificar.error(mensajeDeError(e));
    } finally {
      setOcupada(null);
    }
  }

  return (
    <Vista migas={[{ texto: "Tareas" }]}>
      <EncabezadoPagina
        titulo="Tareas"
        subtitulo="Tareas de tus expedientes, agrupadas por vencimiento: lo que vence primero queda arriba."
      />

      <section className="tarjeta" aria-label="Filtros de tareas">
        <div className="filtros-tareas">
          <Campo etiqueta="Buscar" id="tareas-texto">
            <input
              id="tareas-texto"
              type="search"
              value={texto}
              placeholder="Título, expediente o tipo"
              onChange={(e) => setTexto(e.target.value)}
            />
          </Campo>
          <Campo etiqueta="Expediente" id="tareas-expediente">
            <select id="tareas-expediente" value={expediente} onChange={(e) => cambiarUrl({ exp: e.target.value })}>
              <option value="">Todos</option>
              {expedientes.map(([id, numero]) => (
                <option key={id} value={id}>
                  {numero}
                </option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Estado" id="tareas-estado">
            <select
              id="tareas-estado"
              value={estado}
              onChange={(e) => cambiarUrl({ estado: e.target.value === "abiertas" ? "" : e.target.value, exp: "" })}
            >
              {FILTROS_ESTADO_TAREA.map((f) => (
                <option key={f.valor} value={f.valor}>
                  {f.texto}
                </option>
              ))}
            </select>
          </Campo>
        </div>
        <div className="filtro-vencimiento" role="group" aria-label="Vencimiento">
          <span className="filtro-vencimiento-titulo">Vencimiento</span>
          {FILTROS_VENCIMIENTO.map((f) => (
            <button
              key={f.valor}
              type="button"
              className={`segmento${vencimiento === f.valor ? " segmento-activo" : ""}`}
              aria-pressed={vencimiento === f.valor}
              onClick={() => cambiarUrl({ vence: f.valor === "todas" ? "" : f.valor })}
            >
              {f.texto} <span className="segmento-cuenta">{totales[f.valor]}</span>
            </button>
          ))}
          {hayFiltros ? (
            <button type="button" className="boton-enlace filtro-limpiar" onClick={limpiar}>
              Limpiar filtros
            </button>
          ) : null}
        </div>
      </section>

      {cargando && !datos ? <EsqueletoLineas lineas={5} etiqueta="Cargando tareas…" /> : null}
      {error ? <ErrorCarga error={error} /> : null}

      {datos ? (
        <>
          <p className="nota-pequena" role="status" aria-live="polite">
            {visibles.length === 1 ? "1 tarea" : `${visibles.length} tareas`}
            {hayFiltros ? " con los filtros aplicados" : ""}
          </p>
          {visibles.length === 0 ? (
            <section className="tarjeta">
              <div className="vacio-guia">
                {datos.length === 0 && !hayFiltros ? (
                  <>
                    <strong>No tenés tareas pendientes.</strong>
                    <p>Las tareas se crean desde la pestaña Seguimiento de cada expediente.</p>
                    <Link href="/expedientes" className="boton">
                      Ir a mis expedientes
                    </Link>
                  </>
                ) : (
                  <>
                    <strong>Ninguna tarea coincide con los filtros.</strong>
                    <p>Probá con otro texto o ampliá el vencimiento.</p>
                    <button type="button" className="boton" onClick={limpiar}>
                      Limpiar filtros
                    </button>
                  </>
                )}
              </div>
            </section>
          ) : null}
          {grupos.map(({ grupo, tareas }) => (
            <section key={grupo} className="grupo-tareas" aria-labelledby={`grupo-${grupo}`}>
              <h2 id={`grupo-${grupo}`} className={`grupo-tareas-titulo grupo-${grupo}`}>
                {TITULO_GRUPO[grupo]} <span>{tareas.length}</span>
              </h2>
              <ul className="lista-tarjetas">
                {tareas.map((t) => {
                  const venc = insigniaDeVencimiento(t.estado, t.vence_en);
                  return (
                    <li key={t.id} className={`tarjeta tarjeta-tarea tarjeta-enlace${grupo === "vencida" ? " tarjeta-vencida" : ""}`}>
                      <div className="tarjeta-tarea-principal">
                        <div className="tarjeta-tarea-titulo">{t.titulo}</div>
                        <div className="tarjeta-tarea-meta">
                          <EnlaceExtendido
                            href={`/expedientes/${t.siniestro.id}?tab=seguimiento`}
                            aria-label={`Abrir el expediente ${t.siniestro.numero_expediente}: ${t.titulo}`}
                          >
                            <span className="mono">{t.siniestro.numero_expediente}</span>
                          </EnlaceExtendido>
                          <span> · {t.siniestro.tipo}</span>
                        </div>
                      </div>
                      <div className="tarjeta-tarea-estado">
                        <span className={`insignia insignia-tarea-${t.estado}`}>{ETIQUETA_ESTADO_TAREA[t.estado]}</span>
                        <span className={`insignia insignia-venc-${venc.clase}`} title={t.vence_en ? `Vence el ${formatoFecha(t.vence_en)}` : undefined}>
                          {venc.texto}
                        </span>
                      </div>
                      <div className="acciones tarjeta-tarea-acciones">
                        {t.estado === "pendiente" ? (
                          <button type="button" className="boton boton-chico" disabled={ocupada === t.id} onClick={() => void mover(t, "en_curso")}>
                            Pasar a en curso
                          </button>
                        ) : null}
                        {t.estado === "hecha" ? (
                          <button type="button" className="boton boton-chico" disabled={ocupada === t.id} onClick={() => void mover(t, "pendiente")}>
                            Reabrir
                          </button>
                        ) : (
                          <button type="button" className="boton boton-chico" disabled={ocupada === t.id} onClick={() => void mover(t, "hecha")}>
                            Marcar como hecha
                          </button>
                        )}
                      </div>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
        </>
      ) : null}
    </Vista>
  );
}

export default function PaginaTareas() {
  return (
    <ProtegerRol roles={["perito"]}>
      <Suspense fallback={null}>
        <Tareas />
      </Suspense>
    </ProtegerRol>
  );
}
