"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { api, erroresDeCampo } from "@/lib/api";
import { useSesion } from "@/lib/sesion";
import { useApi } from "@/lib/useApi";
import { formatoFecha, formatoVersionCorta, hoyISO } from "@/lib/formato";
import type { ConjuntoReglas, CuerpoVersionReglas, RespuestaReglas, Topes } from "@/lib/tipos";
import { EncabezadoPagina, Vista } from "@/componentes/Vista";
import { Campo } from "@/componentes/Campo";
import { AvisoAmbar, AvisoVerde, ErrorFormulario, Exito } from "@/componentes/Avisos";
import { Cargando, ErrorCarga } from "@/componentes/Estados";

function siguienteVersion(version: string): string {
  const m = /^(.*?)(\d+)\.(\d+)$/.exec(version);
  return m ? `${m[1]}${m[2]}.${Number(m[3]) + 1}` : `${version}-nueva`;
}

function textoJson(valor: unknown): string {
  return JSON.stringify(valor, null, 2);
}

function FormularioNuevaVersion({
  vigente,
  alPublicar,
  alCancelar,
}: {
  vigente: ConjuntoReglas;
  alPublicar: (version: string) => void;
  alCancelar: () => void;
}) {
  const [version, setVersion] = useState(siguienteVersion(vigente.version));
  const [desde, setDesde] = useState(hoyISO());
  const [puntos, setPuntos] = useState<Record<string, string>>(() =>
    Object.fromEntries(vigente.reglas.map((r) => [r.codigo, String(r.puntos_max)])),
  );
  const [parametros, setParametros] = useState<Record<string, string>>(() =>
    Object.fromEntries(vigente.reglas.map((r) => [r.codigo, textoJson(r.parametros)])),
  );
  const [grupos, setGrupos] = useState<Record<string, string>>(() =>
    Object.fromEntries(Object.entries(vigente.topes.grupos).map(([g, n]) => [g, String(n)])),
  );
  const [total, setTotal] = useState(String(vigente.topes.total));
  const [media, setMedia] = useState(String(vigente.topes.prioridad.media));
  const [alta, setAlta] = useState(String(vigente.topes.prioridad.alta));
  const [error, setError] = useState<unknown>(null);
  const [errorLocal, setErrorLocal] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setErrorLocal(null);

    const reglas: CuerpoVersionReglas["reglas"] = {};
    for (const r of vigente.reglas) {
      const cambios: { parametros?: Record<string, unknown>; puntos_max?: number } = {};
      const nuevoPuntos = Number(puntos[r.codigo]);
      if (!Number.isFinite(nuevoPuntos) || puntos[r.codigo].trim() === "") {
        setErrorLocal(`Los puntos máximos de ${r.codigo} tienen que ser un número.`);
        return;
      }
      if (nuevoPuntos !== r.puntos_max) cambios.puntos_max = nuevoPuntos;
      let nuevosParametros: unknown;
      try {
        nuevosParametros = JSON.parse(parametros[r.codigo]);
      } catch {
        setErrorLocal(`El JSON de parámetros de ${r.codigo} no es válido.`);
        return;
      }
      if (typeof nuevosParametros !== "object" || nuevosParametros === null || Array.isArray(nuevosParametros)) {
        setErrorLocal(`Los parámetros de ${r.codigo} tienen que ser un objeto JSON.`);
        return;
      }
      if (textoJson(nuevosParametros) !== textoJson(r.parametros)) {
        cambios.parametros = nuevosParametros as Record<string, unknown>;
      }
      if (Object.keys(cambios).length > 0) reglas[r.codigo] = cambios;
    }

    const topesGrupos: Record<string, number> = {};
    for (const [nombre, valor] of Object.entries(grupos)) {
      const n = Number(valor);
      if (!Number.isFinite(n) || valor.trim() === "") {
        setErrorLocal(`El tope del grupo ${nombre} tiene que ser un número.`);
        return;
      }
      topesGrupos[nombre] = n;
    }
    const topes: Topes = {
      grupos: topesGrupos,
      total: Number(total),
      prioridad: { media: Number(media), alta: Number(alta) },
    };
    if (![topes.total, topes.prioridad.media, topes.prioridad.alta].every(Number.isFinite)) {
      setErrorLocal("El tope total y los límites de prioridad tienen que ser números.");
      return;
    }

    setEnviando(true);
    try {
      const cuerpo: CuerpoVersionReglas = { version: version.trim(), vigente_desde: desde, reglas, topes };
      await api("/reglas/versiones", { cuerpo });
      alPublicar(cuerpo.version);
    } catch (e) {
      setError(e);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form className="tarjeta" onSubmit={enviar}>
      <div className="tarjeta-cabecera">
        <h2>Nueva versión</h2>
        <span className="meta">Copia {vigente.version}</span>
      </div>
      <div className="tarjeta-cuerpo">
        <p className="nota-pequena">
          Se copia la versión vigente y se aplican los cambios. La versión anterior queda sin edición y las evaluaciones
          viejas conservan la suya.
        </p>
        <div className="rejilla-campos col-2">
          <Campo etiqueta="Versión" id="nv-version" errores={erroresDeCampo(error, "version")}>
            <input id="nv-version" value={version} onChange={(e) => setVersion(e.target.value)} required />
          </Campo>
          <Campo etiqueta="Vigente desde" id="nv-desde" errores={erroresDeCampo(error, "vigente_desde")}>
            <input id="nv-desde" type="date" value={desde} onChange={(e) => setDesde(e.target.value)} required />
          </Campo>
        </div>

        <h3>Reglas</h3>
        {vigente.reglas.map((r) => (
          <div className="fila-persona" key={r.codigo} style={{ padding: "12px 0" }}>
            <div className="titulo-seccion">
              <span className="mono">{r.codigo}</span> · {r.nombre} <span className="nota-pequena">({r.grupo})</span>
            </div>
            <div className="rejilla-campos" style={{ gridTemplateColumns: "140px minmax(0, 1fr)" }}>
              <Campo etiqueta="Puntos máximos" id={`nv-puntos-${r.codigo}`} errores={erroresDeCampo(error, `reglas.${r.codigo}.puntos_max`)}>
                <input
                  id={`nv-puntos-${r.codigo}`}
                  type="number"
                  min={0}
                  value={puntos[r.codigo]}
                  onChange={(e) => setPuntos((p) => ({ ...p, [r.codigo]: e.target.value }))}
                />
              </Campo>
              <Campo etiqueta="Parámetros (JSON)" id={`nv-param-${r.codigo}`} errores={erroresDeCampo(error, `reglas.${r.codigo}.parametros`)}>
                <textarea
                  id={`nv-param-${r.codigo}`}
                  className="json-area"
                  rows={Math.min(10, textoJson(r.parametros).split("\n").length + 1)}
                  value={parametros[r.codigo]}
                  onChange={(e) => setParametros((p) => ({ ...p, [r.codigo]: e.target.value }))}
                  spellCheck={false}
                />
              </Campo>
            </div>
          </div>
        ))}

        <h3>Topes por grupo</h3>
        <div className="rejilla-campos col-4">
          {Object.keys(grupos).map((nombre) => (
            <Campo etiqueta={nombre} id={`nv-tope-${nombre}`} key={nombre}>
              <input
                id={`nv-tope-${nombre}`}
                type="number"
                min={0}
                value={grupos[nombre]}
                onChange={(e) => setGrupos((g) => ({ ...g, [nombre]: e.target.value }))}
              />
            </Campo>
          ))}
        </div>
        <div className="rejilla-campos col-3">
          <Campo etiqueta="Tope total" id="nv-total">
            <input id="nv-total" type="number" min={0} value={total} onChange={(e) => setTotal(e.target.value)} />
          </Campo>
          <Campo etiqueta="Prioridad media desde" id="nv-media">
            <input id="nv-media" type="number" min={0} value={media} onChange={(e) => setMedia(e.target.value)} />
          </Campo>
          <Campo etiqueta="Prioridad alta desde" id="nv-alta">
            <input id="nv-alta" type="number" min={0} value={alta} onChange={(e) => setAlta(e.target.value)} />
          </Campo>
        </div>

        {errorLocal ? (
          <div className="aviso aviso-error" role="alert">
            <p>{errorLocal}</p>
          </div>
        ) : null}
        <ErrorFormulario error={error} />
        <div className="acciones">
          <button type="submit" className="boton boton-principal" disabled={enviando}>
            {enviando ? "Publicando…" : "Publicar versión"}
          </button>
          <button type="button" className="boton" onClick={alCancelar}>
            Cancelar
          </button>
        </div>
      </div>
    </form>
  );
}

export default function PaginaReglas() {
  const { usuario } = useSesion();
  const reglas = useApi<RespuestaReglas>("/reglas");
  const [seleccionada, setSeleccionada] = useState<number | null>(null);
  const otra = useApi<ConjuntoReglas>(seleccionada !== null ? `/reglas/versiones/${seleccionada}` : null);
  const [creando, setCreando] = useState(false);
  const [publicada, setPublicada] = useState<string | null>(null);

  const esSuperadmin = usuario?.rol === "superadministrador";
  const vigente = reglas.datos?.vigente;
  const mostrado: ConjuntoReglas | undefined = seleccionada !== null && otra.datos ? otra.datos : vigente;

  return (
    <Vista
      migas={[{ texto: "Reglas del indicador" }]}
      accion={
        esSuperadmin && vigente && !creando ? (
          <button type="button" className="boton boton-principal" onClick={() => setCreando(true)}>
            Nueva versión
          </button>
        ) : undefined
      }
    >
      {reglas.cargando && !reglas.datos ? <Cargando /> : null}
      {reglas.error ? <ErrorCarga error={reglas.error} /> : null}
      {mostrado ? (
        <>
          <EncabezadoPagina
            titulo={`Reglas del indicador · ${mostrado.version}`}
            subtitulo={`Son las mismas para todos los peritos de la red. Vigentes desde el ${formatoFecha(mostrado.vigente_desde)}.`}
            lateral={
              <span className={`insignia ${mostrado.activo ? "insignia-vigente" : ""}`}>
                {mostrado.activo ? "Vigente" : "Versión anterior"}
              </span>
            }
          />
          {publicada ? <Exito>Se publicó la versión {publicada}. Es la vigente desde ahora; las evaluaciones anteriores conservan la suya.</Exito> : null}
          {creando && vigente ? (
            <FormularioNuevaVersion
              vigente={vigente}
              alCancelar={() => setCreando(false)}
              alPublicar={(version) => {
                setCreando(false);
                setSeleccionada(null);
                setPublicada(version);
                reglas.recargar();
              }}
            />
          ) : null}
          <div className="rejilla rejilla-principal">
            <div className="columna">
              <section className="tarjeta">
                <div className="tarjeta-cabecera">
                  <h2>Reglas</h2>
                </div>
                <div className="tabla-contenedor">
                  <table className="tabla">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Regla</th>
                        <th>Grupo</th>
                        <th>Umbral y puntos</th>
                        <th>Versión</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mostrado.reglas.map((r) => (
                        <tr key={r.codigo}>
                          <td className="mono-celda">{r.codigo}</td>
                          <td>{r.nombre}</td>
                          <td>{r.grupo}</td>
                          <td>{r.umbral_texto}</td>
                          <td className="nota-pequena">{formatoVersionCorta(mostrado.version)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {reglas.datos && reglas.datos.versiones.length > 1 ? (
                <section className="tarjeta">
                  <div className="tarjeta-cabecera">
                    <h2>Versiones publicadas</h2>
                  </div>
                  <div className="tabla-contenedor">
                    <table className="tabla">
                      <thead>
                        <tr>
                          <th>Versión</th>
                          <th>Vigente desde</th>
                          <th>Estado</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {reglas.datos.versiones.map((v) => (
                          <tr key={v.id}>
                            <td>{v.version}</td>
                            <td>{formatoFecha(v.vigente_desde)}</td>
                            <td>{v.activo ? "Vigente" : "Anterior"}</td>
                            <td>
                              <button
                                type="button"
                                className="boton boton-chico"
                                onClick={() => setSeleccionada(v.activo ? null : v.id)}
                                disabled={(v.activo && seleccionada === null) || seleccionada === v.id}
                              >
                                Ver
                              </button>
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
              <section className="tarjeta">
                <div className="tarjeta-cabecera">
                  <h2>Topes por grupo</h2>
                </div>
                <div className="tabla-contenedor">
                  <table className="tabla tabla-clave">
                    <tbody>
                      {Object.entries(mostrado.topes.grupos).map(([grupo, tope]) => (
                        <tr key={grupo}>
                          <th scope="row">{grupo}</th>
                          <td>{tope}</td>
                        </tr>
                      ))}
                      <tr>
                        <th scope="row">Total</th>
                        <td>{mostrado.topes.total}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </section>
              <section className="tarjeta">
                <div className="tarjeta-cuerpo">
                  <h3>Prioridad</h3>
                  <ul className="lista-datos">
                    <li>Baja 0 a {mostrado.topes.prioridad.media - 1}</li>
                    <li>
                      Media {mostrado.topes.prioridad.media} a {mostrado.topes.prioridad.alta - 1}
                    </li>
                    <li>Alta {mostrado.topes.prioridad.alta} o más</li>
                  </ul>
                </div>
              </section>
              <AvisoVerde>
                Las reglas solo cambian después de validarlas con profesionales. Cada cambio crea una versión nueva y las
                evaluaciones anteriores conservan la suya.
              </AvisoVerde>
              <AvisoAmbar>El indicador ordena qué revisar primero. No es una probabilidad de fraude.</AvisoAmbar>
            </div>
          </div>
        </>
      ) : null}
    </Vista>
  );
}
