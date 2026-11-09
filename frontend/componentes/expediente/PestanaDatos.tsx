"use client";

import { useState } from "react";
import Link from "next/link";
import { api, ErrorApi, erroresDeCampo } from "@/lib/api";
import { formatoFecha, formatoFechaHora, formatoHora } from "@/lib/formato";
import { ETIQUETA_ROL_PERSONA, ETIQUETA_TIPO_BIEN } from "@/lib/etiquetas";
import type { Siniestro } from "@/lib/tipos";
import { Campo } from "../Campo";
import { ErrorFormulario } from "../Avisos";
import { useConfirmar } from "../Confirmar";
import { useNotificar } from "../Notificaciones";

interface Props {
  siniestro: Siniestro;
  alCambiar: () => void;
  /** Después de confirmar se pasa a la pestaña de análisis. */
  alConfirmar: () => void;
}

export function PestanaDatos({ siniestro, alCambiar, alConfirmar }: Props) {
  const confirmarAccion = useConfirmar();
  const notificar = useNotificar();
  const [error, setError] = useState<unknown>(null);
  const [trabajando, setTrabajando] = useState(false);
  const [anulando, setAnulando] = useState(false);
  const [motivo, setMotivo] = useState("");

  const poliza = siniestro.poliza;
  const esBorrador = siniestro.estado === "borrador";
  const puedeAnular = siniestro.es_responsable && siniestro.estado !== "anulado";

  async function confirmar() {
    setError(null);
    setTrabajando(true);
    try {
      await api(`/siniestros/${siniestro.id}/confirmar`, { metodo: "POST", cuerpo: {} });
      notificar.exito("Siniestro confirmado. Ya se buscaron coincidencias y se calculó el indicador.");
      alConfirmar();
    } catch (e) {
      setError(e);
    } finally {
      setTrabajando(false);
    }
  }

  async function anular() {
    setError(null);
    if (!motivo.trim()) {
      setError(new ErrorApi(400, null, [{ ruta: "motivo", mensaje: "El motivo de la anulación es obligatorio." }]));
      return;
    }
    const si = await confirmarAccion({
      titulo: `¿Anular ${siniestro.numero_expediente}?`,
      mensaje: (
        <>
          <p>La anulación es por carga errónea. El registro y la auditoría se conservan, pero el caso deja de contar como antecedente y no se puede deshacer.</p>
          <p>
            <strong>Motivo:</strong> {motivo.trim()}
          </p>
        </>
      ),
      confirmar: "Anular expediente",
      peligro: true,
    });
    if (!si) return;
    setTrabajando(true);
    try {
      await api(`/siniestros/${siniestro.id}/anular`, { metodo: "POST", cuerpo: { motivo: motivo.trim() } });
      setAnulando(false);
      setMotivo("");
      notificar.exito(`Se anuló ${siniestro.numero_expediente}.`);
      alCambiar();
    } catch (e) {
      setError(e);
    } finally {
      setTrabajando(false);
    }
  }

  return (
    <div className="columna">
      {siniestro.estado === "anulado" ? (
        <div className="aviso aviso-error" role="status">
          <p>
            <strong>Expediente anulado por carga errónea.</strong> Ya no cuenta como antecedente.
          </p>
          {siniestro.motivo_anulacion ? <p>Motivo: {siniestro.motivo_anulacion}</p> : null}
        </div>
      ) : null}
      {esBorrador ? (
        <div className="aviso aviso-ambar">
          <p>Este expediente es un borrador: todavía no se analiza ni cuenta como antecedente.</p>
        </div>
      ) : null}

      <div className="rejilla rejilla-principal">
        <div className="columna">
          <section className="tarjeta">
            <div className="tarjeta-cabecera">
              <h2>Póliza</h2>
            </div>
            <div className="tarjeta-cuerpo">
              {poliza ? (
                <>
                  <div className="dato-par"><span className="dato-clave">Compañía</span><span className="dato-valor">{poliza.compania || "—"}</span></div>
                  <div className="dato-par"><span className="dato-clave">Número de póliza</span><span className="dato-valor mono">{poliza.numero || "—"}</span></div>
                  <div className="dato-par"><span className="dato-clave">Cobertura</span><span className="dato-valor">{poliza.cobertura || "—"}</span></div>
                  <div className="dato-par"><span className="dato-clave">Inicio de vigencia</span><span className="dato-valor">{formatoFecha(poliza.inicio_vigencia)}</span></div>
                  <div className="dato-par"><span className="dato-clave">Primer pago</span><span className="dato-valor">{formatoFecha(poliza.primer_pago)}</span></div>
                </>
              ) : (
                <p className="nota-pequena">Sin póliza cargada.</p>
              )}
            </div>
          </section>

          <section className="tarjeta">
            <div className="tarjeta-cabecera">
              <h2>Hecho</h2>
            </div>
            <div className="tarjeta-cuerpo">
              <div className="dato-par"><span className="dato-clave">Tipo de siniestro</span><span className="dato-valor">{siniestro.tipo}</span></div>
              <div className="dato-par"><span className="dato-clave">Fecha y hora del hecho</span><span className="dato-valor">{formatoFechaHora(siniestro.fecha_hecho)}</span></div>
              <div className="dato-par"><span className="dato-clave">Fecha de denuncia</span><span className="dato-valor">{formatoFecha(siniestro.fecha_denuncia)}</span></div>
              <div className="dato-par"><span className="dato-clave">Número de denuncia</span><span className="dato-valor mono">{siniestro.numero_denuncia || "—"}</span></div>
              <div className="dato-par"><span className="dato-clave">Hora de la denuncia</span><span className="dato-valor">{formatoHora(siniestro.hora_denuncia)}</span></div>
              <div className="dato-par"><span className="dato-clave">Asesor que carga</span><span className="dato-valor">{siniestro.asesor || "—"}</span></div>
              <div className="dato-par"><span className="dato-clave">Lugar</span><span className="dato-valor">{siniestro.lugar || "—"}</span></div>
              <div className="dato-par"><span className="dato-clave">Relato</span><span className="dato-valor">{siniestro.relato || "—"}</span></div>
              <div className="dato-par"><span className="dato-clave">Intervenciones</span><span className="dato-valor">{siniestro.intervenciones || "—"}</span></div>
              <div className="dato-par"><span className="dato-clave">Documentación adjunta</span><span className="dato-valor">{siniestro.documentacion_adjunta || "—"}</span></div>
            </div>
          </section>

          <section className="tarjeta">
            <div className="tarjeta-cabecera">
              <h2>Personas</h2>
            </div>
            {siniestro.personas.length === 0 ? (
              <p className="vacio">Sin personas cargadas.</p>
            ) : (
              <div className="tabla-contenedor">
                <table className="tabla">
                  <thead>
                    <tr>
                      <th>Identificador</th>
                      <th>Nombre</th>
                      <th>Rol</th>
                    </tr>
                  </thead>
                  <tbody>
                    {siniestro.personas.map((p, i) => (
                      <tr key={p.id ?? i}>
                        <td className="mono-celda">
                          {p.tipo_identificador} {p.identificador}
                        </td>
                        <td>{p.nombre}</td>
                        <td>{p.roles.map((r) => ETIQUETA_ROL_PERSONA[r] ?? r).join(" y ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="tarjeta">
            <div className="tarjeta-cabecera">
              <h2>Bienes</h2>
            </div>
            {siniestro.bienes.length === 0 ? (
              <p className="vacio">Sin bienes cargados.</p>
            ) : (
              <div className="tabla-contenedor">
                <table className="tabla">
                  <thead>
                    <tr>
                      <th>Tipo</th>
                      <th>Identificador</th>
                      <th>Descripción</th>
                      <th>Detalle del daño</th>
                    </tr>
                  </thead>
                  <tbody>
                    {siniestro.bienes.map((b, i) => (
                      <tr key={b.id ?? i}>
                        <td>{ETIQUETA_TIPO_BIEN[b.tipo] ?? b.tipo}</td>
                        <td className="mono-celda">
                          {b.identificador_norm ?? b.identificador}
                          {b.atributos?.motor || b.atributos?.chasis ? (
                            <div className="nota-pequena">
                              Motor / chasis: {String(b.atributos?.motor ?? "—")} / {String(b.atributos?.chasis ?? "—")}
                            </div>
                          ) : null}
                        </td>
                        <td>{b.descripcion || "—"}</td>
                        <td>{b.detalle_dano || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>

        <div className="columna">
          <section className="tarjeta">
            <div className="tarjeta-cuerpo">
              <h3>Responsable</h3>
              <p>{siniestro.perito.nombre}</p>
              <p className="nota-pequena">Espacio {siniestro.espacio.nombre}</p>
              {siniestro.confirmado_en ? (
                <p className="nota-pequena">Confirmado el {formatoFechaHora(siniestro.confirmado_en)}</p>
              ) : null}
              {!siniestro.es_responsable ? (
                <p className="nota-pequena">
                  Solo el perito responsable puede modificar este expediente. Vos lo ves porque es de tu espacio.
                </p>
              ) : null}
            </div>
          </section>

          {siniestro.es_responsable && (esBorrador || puedeAnular) ? (
            <section className="tarjeta">
              <div className="tarjeta-cuerpo">
                <h3>Acciones</h3>
                {esBorrador ? (
                  <>
                    <p className="nota-pequena">
                      Al confirmar, el sistema busca coincidencias y calcula el indicador con las reglas vigentes.
                    </p>
                    <button type="button" className="boton boton-principal boton-ancho" disabled={trabajando} onClick={() => void confirmar()}>
                      {trabajando ? "Confirmando…" : "Confirmar siniestro"}
                    </button>
                    <Link href={`/expedientes/nuevo?id=${siniestro.id}`} className="boton boton-ancho">
                      Editar borrador
                    </Link>
                  </>
                ) : null}
                {puedeAnular && !anulando ? (
                  <button type="button" className="boton boton-ancho boton-peligro" onClick={() => setAnulando(true)}>
                    Anular expediente
                  </button>
                ) : null}
                {puedeAnular && anulando ? (
                  <div className="columna">
                    <p className="nota-pequena">
                      La anulación es por carga errónea. Conserva el registro y la auditoría, y el caso deja de contar como antecedente.
                    </p>
                    <Campo etiqueta="Motivo de la anulación" id="motivo-anulacion" errores={erroresDeCampo(error, "motivo")}>
                      <textarea id="motivo-anulacion" value={motivo} onChange={(e) => setMotivo(e.target.value)} />
                    </Campo>
                    <div className="acciones">
                      <button type="button" className="boton boton-peligro" disabled={trabajando} onClick={() => void anular()}>
                        {trabajando ? "Anulando…" : "Anular con este motivo"}
                      </button>
                      <button
                        type="button"
                        className="boton"
                        onClick={() => {
                          setAnulando(false);
                          setError(null);
                        }}
                      >
                        Cancelar
                      </button>
                    </div>
                  </div>
                ) : null}
                <ErrorFormulario error={error} />
              </div>
            </section>
          ) : null}
        </div>
      </div>
    </div>
  );
}
