"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { api, comoLista, erroresDeCampo } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { formatoFecha } from "@/lib/formato";
import type { EspacioAdministrado } from "@/lib/tipos";
import { EncabezadoPagina, Vista } from "@/componentes/Vista";
import { ProtegerRol } from "@/componentes/ProtegerRol";
import { Campo } from "@/componentes/Campo";
import { ErrorFormulario } from "@/componentes/Avisos";
import { ErrorCarga, Vacio } from "@/componentes/Estados";
import { EsqueletoTabla } from "@/componentes/Esqueletos";
import { useNotificar } from "@/componentes/Notificaciones";

function Espacios() {
  const lista = useApi<unknown>("/admin/espacios");
  const espacios = comoLista<EspacioAdministrado>(lista.datos);
  const [nombre, setNombre] = useState("");
  const [adminNombre, setAdminNombre] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [error, setError] = useState<unknown>(null);
  const notificar = useNotificar();
  const [creando, setCreando] = useState(false);

  async function crear(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setCreando(true);
    try {
      await api("/admin/espacios", {
        cuerpo: { nombre: nombre.trim(), admin_nombre: adminNombre.trim(), admin_email: adminEmail.trim() },
      });
      notificar.exito(`Se creó el espacio «${nombre.trim()}» y se envió el enlace de primer ingreso a ${adminEmail.trim()}.`);
      setNombre("");
      setAdminNombre("");
      setAdminEmail("");
      lista.recargar();
    } catch (e) {
      setError(e);
    } finally {
      setCreando(false);
    }
  }

  return (
    <Vista migas={[{ texto: "Espacios" }]}>
      <EncabezadoPagina
        titulo="Espacios de trabajo"
        subtitulo="Cada espacio tiene su administrador, que da de alta a los peritos. No hay registro abierto."
      />
      <div className="rejilla rejilla-principal">
        <div className="columna">
          <section className="tarjeta">
            <div className="tarjeta-cabecera">
              <h2>Espacios</h2>
            </div>
            {lista.cargando && !lista.datos ? (
              <EsqueletoTabla filas={3} columnas={3} etiqueta="Cargando espacios…" />
            ) : null}
            {lista.error ? (
              <div className="tarjeta-cuerpo">
                <ErrorCarga error={lista.error} />
              </div>
            ) : null}
            {lista.datos && espacios.length === 0 ? <Vacio>Todavía no hay espacios.</Vacio> : null}
            {espacios.length > 0 ? (
              <div className="tabla-contenedor">
                <table className="tabla tabla-apilada">
                  <thead>
                    <tr>
                      <th>Espacio</th>
                      <th>Usuarios</th>
                      <th>Creado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {espacios.map((e) => (
                      <tr key={e.id}>
                        <td data-label="Espacio">{e.nombre}</td>
                        <td data-label="Usuarios">{e.cantidad_usuarios ?? e.usuarios ?? "—"}</td>
                        <td data-label="Creado">{e.creado_en ? formatoFecha(e.creado_en) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>
        </div>

        <form className="tarjeta" onSubmit={crear}>
          <div className="tarjeta-cabecera">
            <h2>Crear espacio</h2>
          </div>
          <div className="tarjeta-cuerpo">
            <Campo etiqueta="Nombre del espacio" id="esp-nombre" errores={erroresDeCampo(error, "nombre")}>
              <input id="esp-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} required />
            </Campo>
            <Campo etiqueta="Nombre del administrador" id="esp-admin-nombre" errores={erroresDeCampo(error, "admin_nombre")}>
              <input id="esp-admin-nombre" value={adminNombre} onChange={(e) => setAdminNombre(e.target.value)} required />
            </Campo>
            <Campo etiqueta="Correo del administrador" id="esp-admin-email" errores={erroresDeCampo(error, "admin_email")}>
              <input id="esp-admin-email" type="email" value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} required />
            </Campo>
            <ErrorFormulario error={error} />
            <button type="submit" className="boton boton-principal boton-ancho" disabled={creando}>
              {creando ? "Creando…" : "Crear espacio y administrador"}
            </button>
            <p className="nota-pequena">El administrador recibe un enlace por correo para definir su contraseña.</p>
          </div>
        </form>
      </div>
    </Vista>
  );
}

export default function PaginaEspacios() {
  return (
    <ProtegerRol roles={["superadministrador"]}>
      <Espacios />
    </ProtegerRol>
  );
}
