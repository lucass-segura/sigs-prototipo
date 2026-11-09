"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { api, comoLista, erroresDeCampo } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { useSesion } from "@/lib/sesion";
import { formatoFechaHora } from "@/lib/formato";
import { ETIQUETA_ROL } from "@/lib/etiquetas";
import type { Rol, UsuarioAdministrado } from "@/lib/tipos";
import { EncabezadoPagina, Vista } from "@/componentes/Vista";
import { ProtegerRol } from "@/componentes/ProtegerRol";
import { Campo } from "@/componentes/Campo";
import { ErrorFormulario } from "@/componentes/Avisos";
import { ErrorCarga, Vacio } from "@/componentes/Estados";
import { EsqueletoTabla } from "@/componentes/Esqueletos";
import { useConfirmar } from "@/componentes/Confirmar";
import { useNotificar } from "@/componentes/Notificaciones";

function estadoDeCuenta(u: UsuarioAdministrado): { texto: string; clase: string } {
  if (!u.activo) return { texto: "Dado de baja", clase: "insignia-estado-anulado" };
  if (u.bloqueado_en) return { texto: "Bloqueado", clase: "insignia-rechazado" };
  return { texto: "Activo", clase: "insignia-estado-en_analisis" };
}

function Usuarios() {
  const { usuario } = useSesion();
  const lista = useApi<unknown>("/admin/usuarios");
  const usuarios = comoLista<UsuarioAdministrado>(lista.datos);

  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [rol, setRol] = useState<Extract<Rol, "perito" | "administrador">>("perito");
  const [errorAlta, setErrorAlta] = useState<unknown>(null);
  const confirmarAccion = useConfirmar();
  const notificar = useNotificar();
  const [creando, setCreando] = useState(false);
  const [errorAccion, setErrorAccion] = useState<unknown>(null);
  const [ocupado, setOcupado] = useState<number | null>(null);

  async function alta(evento: FormEvent) {
    evento.preventDefault();
    setErrorAlta(null);
    setCreando(true);
    try {
      await api("/admin/usuarios", { cuerpo: { nombre: nombre.trim(), email: email.trim(), rol } });
      notificar.exito(`Se dio de alta a ${email.trim()}. Le enviamos el enlace de primer ingreso.`);
      setNombre("");
      setEmail("");
      setRol("perito");
      lista.recargar();
    } catch (e) {
      setErrorAlta(e);
    } finally {
      setCreando(false);
    }
  }

  async function accion(
    u: UsuarioAdministrado,
    ruta: "baja" | "bloquear" | "reenviar-enlace",
    confirmacion: { titulo: string; mensaje: string; confirmar: string } | null,
    mensaje?: string,
  ) {
    if (confirmacion && !(await confirmarAccion({ ...confirmacion, peligro: true }))) return;
    setErrorAccion(null);
    setOcupado(u.id);
    try {
      await api(`/admin/usuarios/${u.id}/${ruta}`, { metodo: "POST", cuerpo: {} });
      if (mensaje) notificar.exito(mensaje);
      lista.recargar();
    } catch (e) {
      setErrorAccion(e);
    } finally {
      setOcupado(null);
    }
  }

  return (
    <Vista migas={[{ texto: "Usuarios" }]}>
      <EncabezadoPagina
        titulo="Usuarios"
        subtitulo={`Altas, bajas y bloqueos del espacio ${usuario?.espacio?.nombre ?? ""}. El usuario define su propia contraseña con el enlace que recibe por correo.`}
      />
      <div className="rejilla rejilla-principal">
        <div className="columna">
          <ErrorFormulario error={errorAccion} />
          <section className="tarjeta">
            <div className="tarjeta-cabecera">
              <h2>Usuarios del espacio</h2>
            </div>
            {lista.cargando && !lista.datos ? (
              <div className="tarjeta-cuerpo">
                <EsqueletoTabla filas={4} columnas={5} etiqueta="Cargando usuarios…" />
              </div>
            ) : null}
            {lista.error ? (
              <div className="tarjeta-cuerpo">
                <ErrorCarga error={lista.error} />
              </div>
            ) : null}
            {lista.datos && usuarios.length === 0 ? <Vacio>No hay usuarios en el espacio.</Vacio> : null}
            {usuarios.length > 0 ? (
              <div className="tabla-contenedor">
                <table className="tabla tabla-apilada">
                  <thead>
                    <tr>
                      <th>Nombre</th>
                      <th>Correo</th>
                      <th>Rol</th>
                      <th>Estado</th>
                      <th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usuarios.map((u) => {
                      const estado = estadoDeCuenta(u);
                      const esYo = u.id === usuario?.id;
                      return (
                        <tr key={u.id}>
                          <td data-label="Nombre">{u.nombre}</td>
                          <td data-label="Correo">{u.email}</td>
                          <td data-label="Rol">{ETIQUETA_ROL[u.rol]}</td>
                          <td data-label="Estado">
                            <span className={`insignia ${estado.clase}`}>{estado.texto}</span>
                            {u.bloqueado_en ? <div className="nota-pequena">desde {formatoFechaHora(u.bloqueado_en)}</div> : null}
                            {u.intentos_fallidos > 0 ? (
                              <div className="nota-pequena">
                                {u.intentos_fallidos} {u.intentos_fallidos === 1 ? "intento fallido" : "intentos fallidos"}
                              </div>
                            ) : null}
                          </td>
                          <td>
                            <div className="acciones">
                              <button
                                type="button"
                                className="boton boton-chico"
                                disabled={ocupado === u.id}
                                onClick={() =>
                                  void accion(u, "reenviar-enlace", null, `Se reenvió el enlace a ${u.email}.`)
                                }
                              >
                                Reenviar enlace
                              </button>
                              {u.activo && !esYo ? (
                                <>
                                  <button
                                    type="button"
                                    className="boton boton-chico"
                                    disabled={ocupado === u.id}
                                    onClick={() =>
                                      void accion(
                                        u,
                                        "bloquear",
                                        {
                                          titulo: `¿Bloquear a ${u.nombre}?`,
                                          mensaje: "Se bloquea la cuenta y se cierran todas sus sesiones abiertas. Puede volver a ingresar con un enlace de restablecimiento.",
                                          confirmar: "Bloquear y cerrar sesiones",
                                        },
                                        `Se bloqueó la cuenta de ${u.nombre} y se cerraron sus sesiones.`,
                                      )
                                    }
                                  >
                                    Bloquear y cerrar sesiones
                                  </button>
                                  <button
                                    type="button"
                                    className="boton boton-chico boton-peligro"
                                    disabled={ocupado === u.id}
                                    onClick={() =>
                                      void accion(
                                        u,
                                        "baja",
                                        {
                                          titulo: `¿Dar de baja a ${u.nombre}?`,
                                          mensaje: "No va a poder ingresar más. Se conservan su historial y su auditoría.",
                                          confirmar: "Dar de baja",
                                        },
                                        `Se dio de baja a ${u.nombre}.`,
                                      )
                                    }
                                  >
                                    Dar de baja
                                  </button>
                                </>
                              ) : null}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : null}
          </section>
        </div>

        <form className="tarjeta" onSubmit={alta}>
          <div className="tarjeta-cabecera">
            <h2>Alta de usuario</h2>
          </div>
          <div className="tarjeta-cuerpo">
            <Campo etiqueta="Nombre" id="alta-nombre" errores={erroresDeCampo(errorAlta, "nombre")}>
              <input id="alta-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} required />
            </Campo>
            <Campo etiqueta="Correo electrónico" id="alta-email" errores={erroresDeCampo(errorAlta, "email")}>
              <input id="alta-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </Campo>
            <Campo etiqueta="Rol" id="alta-rol" errores={erroresDeCampo(errorAlta, "rol")}>
              <select id="alta-rol" value={rol} onChange={(e) => setRol(e.target.value as "perito" | "administrador")}>
                <option value="perito">Perito</option>
                <option value="administrador">Administrador</option>
              </select>
            </Campo>
            <ErrorFormulario error={errorAlta} />
            <button type="submit" className="boton boton-principal boton-ancho" disabled={creando}>
              {creando ? "Dando de alta…" : "Dar de alta"}
            </button>
            <p className="nota-pequena">Se envía el enlace de primer ingreso. Ni vos ni el superadministrador conocen la contraseña.</p>
          </div>
        </form>
      </div>
    </Vista>
  );
}

export default function PaginaUsuarios() {
  return (
    <ProtegerRol roles={["administrador"]}>
      <Usuarios />
    </ProtegerRol>
  );
}
