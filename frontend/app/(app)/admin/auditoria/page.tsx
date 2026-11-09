"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { comoLista } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { formatoFechaHora } from "@/lib/formato";
import type { RespuestaAuditoria, UsuarioAdministrado } from "@/lib/tipos";
import { EncabezadoPagina, Vista } from "@/componentes/Vista";
import { ProtegerRol } from "@/componentes/ProtegerRol";
import { Campo } from "@/componentes/Campo";
import { AvisoVerde } from "@/componentes/Avisos";
import { ErrorCarga, Vacio } from "@/componentes/Estados";
import { EsqueletoTabla } from "@/componentes/Esqueletos";

interface Filtros {
  usuario: string;
  accion: string;
  resultado: string;
}

function Auditoria() {
  const [filtros, setFiltros] = useState<Filtros>({ usuario: "", accion: "", resultado: "" });
  const [aplicados, setAplicados] = useState<Filtros>(filtros);
  const [pagina, setPagina] = useState(1);

  const consulta = new URLSearchParams();
  if (aplicados.usuario) consulta.set("usuario", aplicados.usuario);
  if (aplicados.accion) consulta.set("accion", aplicados.accion);
  if (aplicados.resultado) consulta.set("resultado", aplicados.resultado);
  consulta.set("pagina", String(pagina));
  const { datos, error, cargando } = useApi<RespuestaAuditoria>(`/auditoria?${consulta.toString()}`);

  // La API filtra por id de usuario: se elige de la lista de usuarios del espacio.
  const usuarios = comoLista<UsuarioAdministrado>(useApi<unknown>("/admin/usuarios").datos);
  const acciones = datos?.acciones ?? [];

  function aplicar(evento: FormEvent) {
    evento.preventDefault();
    setPagina(1);
    setAplicados(filtros);
  }

  return (
    <Vista migas={[{ texto: "Auditoría" }]}>
      <EncabezadoPagina
        titulo="Auditoría del espacio"
        subtitulo="Cada consulta y cada cambio queda registrado. El registro es de solo lectura: no se puede editar ni borrar."
      />
      <section className="tarjeta">
        <form className="herramientas" onSubmit={aplicar}>
          <Campo etiqueta="Usuario" id="aud-usuario">
            <select id="aud-usuario" value={filtros.usuario} onChange={(e) => setFiltros({ ...filtros, usuario: e.target.value })}>
              <option value="">Todos</option>
              {usuarios.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nombre} ({u.email})
                </option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Acción" id="aud-accion">
            <select id="aud-accion" value={filtros.accion} onChange={(e) => setFiltros({ ...filtros, accion: e.target.value })}>
              <option value="">Todas</option>
              {acciones.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </select>
          </Campo>
          <Campo etiqueta="Resultado" id="aud-resultado">
            <select id="aud-resultado" value={filtros.resultado} onChange={(e) => setFiltros({ ...filtros, resultado: e.target.value })}>
              <option value="">Todos</option>
              <option value="permitido">Permitido</option>
              <option value="rechazado">Rechazado</option>
            </select>
          </Campo>
          <div className="campo" style={{ justifyContent: "flex-end" }}>
            <button type="submit" className="boton boton-principal">
              Filtrar
            </button>
          </div>
        </form>

        {cargando && !datos ? (
          <EsqueletoTabla filas={6} columnas={6} etiqueta="Cargando la auditoría…" />
        ) : null}
        {error ? (
          <div className="tarjeta-cuerpo">
            <ErrorCarga error={error} />
          </div>
        ) : null}
        {datos && datos.resultados.length === 0 ? <Vacio>No hay registros con esos filtros.</Vacio> : null}
        {datos && datos.resultados.length > 0 ? (
          <>
            <div className="tabla-contenedor">
              <table className="tabla tabla-apilada">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Usuario</th>
                    <th>Acción</th>
                    <th>Objeto</th>
                    <th>Resultado</th>
                    <th>Siniestro de origen</th>
                  </tr>
                </thead>
                <tbody>
                  {datos.resultados.map((r) => (
                    <tr key={r.id}>
                      <td data-label="Fecha">{formatoFechaHora(r.fecha)}</td>
                      <td data-label="Usuario">
                        {r.usuario ? (
                          <>
                            {r.usuario.nombre}
                            <div className="nota-pequena">{r.usuario.email}</div>
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td className="mono-celda" data-label="Acción">{r.accion}</td>
                      <td className="mono-celda" data-label="Objeto">{r.objeto || "—"}</td>
                      <td data-label="Resultado">
                        <span className={`insignia insignia-${r.resultado}`}>{r.resultado === "permitido" ? "Permitido" : "Rechazado"}</span>
                      </td>
                      <td className="mono-celda" data-label="Siniestro de origen">{r.siniestro_origen?.numero_expediente ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="paginacion">
              <button type="button" className="boton boton-chico" disabled={pagina <= 1} onClick={() => setPagina((p) => p - 1)}>
                Anterior
              </button>
              <span>
                Página {datos.pagina} de {Math.max(datos.paginas, 1)} · {datos.total} registros
              </span>
              <button type="button" className="boton boton-chico" disabled={pagina >= datos.paginas} onClick={() => setPagina((p) => p + 1)}>
                Siguiente
              </button>
            </div>
          </>
        ) : null}
      </section>
      <AvisoVerde>Los registros no tienen botones de edición ni de borrado: la API y la base los rechazan.</AvisoVerde>
    </Vista>
  );
}

export default function PaginaAuditoria() {
  return (
    <ProtegerRol roles={["administrador"]}>
      <Auditoria />
    </ProtegerRol>
  );
}
