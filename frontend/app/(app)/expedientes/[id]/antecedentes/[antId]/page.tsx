"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useApi } from "@/lib/useApi";
import { formatoMesAnio } from "@/lib/formato";
import { ETIQUETA_RESULTADO } from "@/lib/etiquetas";
import type { ResumenAntecedente } from "@/lib/tipos";
import { EncabezadoPagina, Vista } from "@/componentes/Vista";
import { ProtegerRol } from "@/componentes/ProtegerRol";
import { Cargando, ErrorCarga } from "@/componentes/Estados";

function Resumen() {
  const { id, antId } = useParams<{ id: string; antId: string }>();
  const { datos: r, error, cargando } = useApi<ResumenAntecedente>(`/siniestros/${id}/antecedentes/${antId}/resumen`);

  if (cargando && !r) {
    return (
      <Vista migas={[{ texto: "Expedientes", href: "/expedientes" }, { texto: "Antecedente" }]}>
        <Cargando />
      </Vista>
    );
  }
  if (error || !r) {
    return (
      <Vista migas={[{ texto: "Expedientes", href: "/expedientes" }, { texto: "Antecedente" }]}>
        {error ? (
          <ErrorCarga error={error}>
            <p>
              <Link href={`/expedientes/${id}?tab=analisis`}>Volver al análisis</Link>
            </p>
          </ErrorCarga>
        ) : null}
      </Vista>
    );
  }

  const vinculos = r.vinculos.map((v) => `${v.tipo === "bien" ? "Bien" : "Persona"}: ${v.etiqueta}`).join(" · ");
  const roles = Array.from(new Set(r.vinculos.map((v) => v.rol_en_antecedente))).join(" · ");

  return (
    <Vista
      migas={[
        { texto: "Expedientes", href: "/expedientes" },
        { texto: r.origen.numero_expediente, href: `/expedientes/${r.origen.id}?tab=analisis` },
        { texto: `Antecedente ${r.numero_expediente}` },
      ]}
    >
      <EncabezadoPagina
        titulo={`Resumen del antecedente ${r.numero_expediente}`}
        subtitulo={`Consulta hecha desde ${r.origen.numero_expediente}. Queda registrada en la auditoría.`}
      />
      <div className="rejilla rejilla-principal">
        <section className="tarjeta">
          <div className="tarjeta-cabecera">
            <h2>Datos compartidos</h2>
          </div>
          <div className="tabla-contenedor">
            <table className="tabla tabla-clave">
              <tbody>
                <tr>
                  <th scope="row">Tipo de siniestro</th>
                  <td>{r.tipo}</td>
                </tr>
                <tr>
                  <th scope="row">Fecha del hecho</th>
                  <td>{formatoMesAnio(r.fecha_hecho)}</td>
                </tr>
                <tr>
                  <th scope="row">Vínculo con tu caso</th>
                  <td>{vinculos || "—"}</td>
                </tr>
                <tr>
                  <th scope="row">Rol en el antecedente</th>
                  <td>{roles || "—"}</td>
                </tr>
                {r.cerrado ? (
                  <>
                    <tr>
                      <th scope="row">Resultado del reclamo</th>
                      <td>{r.resultado_reclamo ? ETIQUETA_RESULTADO[r.resultado_reclamo] : "—"}</td>
                    </tr>
                    <tr>
                      <th scope="row">Irregularidad confirmada</th>
                      <td>{r.irregularidad ? "Sí" : "No"}</td>
                    </tr>
                    <tr>
                      <th scope="row">Valoración pericial</th>
                      <td>
                        {r.valoracion !== null ? (
                          <>
                            <strong>{r.valoracion} / 10</strong>{" "}
                            <span className="nota-pequena">{r.valoracion_texto}</span>
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                    <tr>
                      <th scope="row">Justificación del perito</th>
                      <td>{r.justificacion || "—"}</td>
                    </tr>
                  </>
                ) : (
                  <tr>
                    <th scope="row">Estado</th>
                    <td>{r.estado_texto ?? "En análisis"}. Todavía no tiene datos de cierre.</td>
                  </tr>
                )}
                <tr>
                  <th scope="row">Perito responsable</th>
                  <td>{r.perito_responsable.nombre}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <div className="columna">
          <section className="tarjeta">
            <div className="tarjeta-cuerpo">
              <h3>Qué no se muestra</h3>
              <p>{r.no_se_muestra}</p>
            </div>
          </section>
          {r.contacto_perito ? (
            <section className="tarjeta">
              <div className="tarjeta-cuerpo">
                <h3>Contacto del perito {r.perito_responsable.nombre}</h3>
                <p>{r.contacto_perito.email}</p>
                <p className="nota-pequena">Lo habilitó en su perfil para consultas sobre sus casos.</p>
              </div>
            </section>
          ) : null}
          <Link href={`/expedientes/${r.origen.id}?tab=analisis`} className="boton boton-ancho">
            Volver al análisis
          </Link>
        </div>
      </div>
    </Vista>
  );
}

export default function PaginaResumenAntecedente() {
  return (
    <ProtegerRol roles={["perito"]}>
      <Resumen />
    </ProtegerRol>
  );
}
