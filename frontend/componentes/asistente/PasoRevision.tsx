import type { ReactNode } from "react";
import { bienesEnviables, nombreDePaso, personasEnviables } from "@/lib/asistenteSiniestro";
import type { DatosSiniestro, IdPaso, Requisito } from "@/lib/asistenteSiniestro";
import { ETIQUETA_ROL_PERSONA, ETIQUETA_TIPO_BIEN } from "@/lib/etiquetas";
import { formatearFecha } from "@/lib/fechas";
import { AvisoVerde } from "../Avisos";

const o = (valor: string) => valor.trim() || "—";

function Dato({ clave, valor, mono }: { clave: string; valor: string; mono?: boolean }) {
  return (
    <div className="dato-par">
      <span className="dato-clave">{clave}</span>
      <span className={`dato-valor${mono ? " mono" : ""}`}>{valor}</span>
    </div>
  );
}

function Seccion({ titulo, paso, ir, children }: { titulo: string; paso: IdPaso; ir: (paso: IdPaso) => void; children: ReactNode }) {
  return (
    <section className="resumen-seccion" aria-label={titulo}>
      <div className="resumen-seccion-cabecera">
        <h3>{titulo}</h3>
        <button type="button" className="boton boton-chico" onClick={() => ir(paso)} aria-label={`Editar ${titulo.toLowerCase()}`}>
          Editar
        </button>
      </div>
      {children}
    </section>
  );
}

/** Paso 5: resumen por sección, lo que falta para confirmar y el botón de confirmar. */
export function PasoRevision({
  datos,
  requisitos,
  pasosConError,
  ir,
  confirmar,
  enviando,
}: {
  datos: DatosSiniestro;
  requisitos: Requisito[];
  pasosConError: IdPaso[];
  ir: (paso: IdPaso) => void;
  confirmar: () => void;
  enviando: boolean;
}) {
  const personas = personasEnviables(datos.personas);
  const bienes = bienesEnviables(datos.bienes);
  const faltan = requisitos.filter((r) => !r.cumplido);
  const fechaHecho = datos.fechaHecho ? `${formatearFecha(datos.fechaHecho)}${datos.horaHecho ? ` ${datos.horaHecho} h` : ""}` : "—";
  const fechaDenuncia = datos.fechaDenuncia
    ? `${formatearFecha(datos.fechaDenuncia)}${datos.horaDenuncia ? ` ${datos.horaDenuncia} h` : ""}`
    : datos.horaDenuncia
      ? `${datos.horaDenuncia} h`
      : "—";

  return (
    <>
      <div className="tarjeta-cuerpo">
        <section aria-labelledby="titulo-requisitos">
          <h3 id="titulo-requisitos">Qué hace falta para confirmar</h3>
          <ul className="requisitos">
            {requisitos.map((r) => (
              <li key={r.id} className={r.cumplido ? "requisito-cumplido" : "requisito-falta"}>
                <span className="requisito-marca" aria-hidden="true">
                  {r.cumplido ? "✓" : "!"}
                </span>
                <span className="requisito-texto">
                  <span className="solo-lectores">{r.cumplido ? "Listo: " : "Falta: "}</span>
                  {r.texto}
                </span>
                {!r.cumplido ? (
                  <span className="requisito-enlaces">
                    {r.pasos.map((p) => (
                      <button type="button" className="boton-enlace" key={p} onClick={() => ir(p)}>
                        Ir a {nombreDePaso(p)}
                      </button>
                    ))}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
          {pasosConError.length > 0 ? (
            <div className="aviso aviso-error" role="alert">
              <p>
                Hay datos para corregir en:{" "}
                {pasosConError.map((p, i) => (
                  <span key={p}>
                    {i > 0 ? ", " : ""}
                    <button type="button" className="boton-enlace" onClick={() => ir(p)}>
                      {nombreDePaso(p)}
                    </button>
                  </span>
                ))}
                .
              </p>
            </div>
          ) : null}
        </section>
      </div>

      <div className="tarjeta-cuerpo resumen">
        <Seccion titulo="Póliza" paso="poliza" ir={ir}>
          <Dato clave="Compañía" valor={o(datos.compania)} />
          <Dato clave="Número de póliza" valor={o(datos.numeroPoliza)} mono />
          <Dato clave="Cobertura" valor={o(datos.cobertura)} />
          <Dato clave="Inicio de vigencia" valor={datos.inicioVigencia ? formatearFecha(datos.inicioVigencia) : "—"} />
          <Dato clave="Primer pago" valor={datos.primerPago ? formatearFecha(datos.primerPago) : "—"} />
        </Seccion>

        <Seccion titulo="Hecho y denuncia" paso="hecho" ir={ir}>
          <Dato clave="Tipo de siniestro" valor={o(datos.tipo)} />
          <Dato clave="Fecha y hora del hecho" valor={fechaHecho} />
          <Dato clave="Lugar" valor={o(datos.lugar)} />
          <Dato clave="Relato" valor={o(datos.relato)} />
          <Dato clave="Fecha y hora de la denuncia" valor={fechaDenuncia} />
          <Dato clave="Número de denuncia" valor={o(datos.numeroDenuncia)} mono />
          <Dato clave="Asesor que carga" valor={o(datos.asesor)} />
          <Dato clave="Intervenciones" valor={o(datos.intervenciones)} />
          <Dato clave="Documentación adjunta" valor={o(datos.documentacionAdjunta)} />
        </Seccion>

        <Seccion titulo="Personas" paso="personas" ir={ir}>
          {personas.length === 0 ? (
            <p className="vacio">Todavía no cargaste personas.</p>
          ) : (
            <ul className="resumen-lista">
              {personas.map((p) => (
                <li key={p.clave}>
                  <strong>{p.nombre.trim() || "Sin nombre"}</strong>
                  <span className="mono">
                    {p.tipo_identificador} {p.identificador.trim() || "—"}
                  </span>
                  <span>{p.roles.length ? p.roles.map((r) => ETIQUETA_ROL_PERSONA[r]).join(", ") : "Sin rol"}</span>
                </li>
              ))}
            </ul>
          )}
        </Seccion>

        <Seccion titulo="Bienes" paso="bienes" ir={ir}>
          {bienes.length === 0 ? (
            <p className="vacio">Todavía no cargaste bienes.</p>
          ) : (
            <ul className="resumen-lista">
              {bienes.map((b) => (
                <li key={b.clave}>
                  <strong>{b.descripcion.trim() || ETIQUETA_TIPO_BIEN[b.tipo]}</strong>
                  <span className="mono">
                    {ETIQUETA_TIPO_BIEN[b.tipo]} {b.identificador.trim() || "—"}
                  </span>
                  <span>{b.detalle_dano.trim() || "Sin detalle del daño"}</span>
                </li>
              ))}
            </ul>
          )}
        </Seccion>
      </div>

      <div className="tarjeta-cuerpo confirmar-bloque">
        <button
          type="button"
          className="boton boton-principal boton-ancho"
          disabled={enviando || faltan.length > 0}
          aria-describedby={faltan.length > 0 ? "ayuda-confirmar" : undefined}
          onClick={confirmar}
        >
          {enviando ? "Confirmando…" : "Confirmar siniestro"}
        </button>
        {faltan.length > 0 ? (
          <small className="ayuda" id="ayuda-confirmar">
            Completá lo que falta para poder confirmar. Mientras tanto podés guardar el borrador.
          </small>
        ) : null}
        <AvisoVerde>Al confirmar, el sistema busca coincidencias y calcula el indicador con las reglas vigentes.</AvisoVerde>
      </div>
    </>
  );
}
