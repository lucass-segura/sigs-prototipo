"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, erroresDeCampo } from "@/lib/api";
import { useSesion } from "@/lib/sesion";
import { ETIQUETA_ROL } from "@/lib/etiquetas";
import type { Usuario } from "@/lib/tipos";
import { EncabezadoPagina, Vista } from "@/componentes/Vista";
import { Campo } from "@/componentes/Campo";
import { ErrorFormulario, Exito } from "@/componentes/Avisos";

export default function PaginaPerfil() {
  const { usuario, reemplazarUsuario } = useSesion();
  const [correo, setCorreo] = useState("");
  const [visible, setVisible] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [exito, setExito] = useState(false);
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (!usuario) return;
    setCorreo(usuario.contacto_email ?? "");
    setVisible(usuario.contacto_visible);
  }, [usuario]);

  if (!usuario) return null;

  async function guardar(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setExito(false);
    setGuardando(true);
    try {
      const actualizado = await api<Usuario>("/perfil", {
        metodo: "PATCH",
        cuerpo: { contacto_email: correo.trim(), contacto_visible: visible },
      });
      reemplazarUsuario(actualizado);
      setExito(true);
    } catch (e) {
      setError(e);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <Vista migas={[{ texto: "Perfil" }]}>
      <EncabezadoPagina titulo="Perfil" subtitulo="Tus datos de cuenta y el correo de contacto que otros peritos pueden ver." />
      <div className="rejilla rejilla-principal">
        <div className="columna">
          <section className="tarjeta">
            <div className="tarjeta-cabecera">
              <h2>Cuenta</h2>
            </div>
            <div className="tabla-contenedor">
              <table className="tabla tabla-clave">
                <tbody>
                  <tr>
                    <th scope="row">Nombre</th>
                    <td>{usuario.nombre}</td>
                  </tr>
                  <tr>
                    <th scope="row">Correo de acceso</th>
                    <td>{usuario.email}</td>
                  </tr>
                  <tr>
                    <th scope="row">Rol</th>
                    <td>{ETIQUETA_ROL[usuario.rol]}</td>
                  </tr>
                  <tr>
                    <th scope="row">Espacio de trabajo</th>
                    <td>{usuario.espacio?.nombre ?? "Todos los espacios"}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <form className="tarjeta" onSubmit={guardar}>
            <div className="tarjeta-cabecera">
              <h2>Correo de contacto</h2>
            </div>
            <div className="tarjeta-cuerpo">
              <Campo etiqueta="Correo de contacto" id="contacto-email" errores={erroresDeCampo(error, "contacto_email")}>
                <input id="contacto-email" type="email" value={correo} onChange={(e) => setCorreo(e.target.value)} />
              </Campo>
              <label className="casilla">
                <input type="checkbox" checked={visible} onChange={(e) => setVisible(e.target.checked)} />
                Mostrar mi correo en los resúmenes de mis casos cerrados
              </label>
              <ErrorFormulario error={error} />
              {exito ? <Exito>Los cambios se guardaron y quedaron registrados en la auditoría.</Exito> : null}
              <div className="acciones">
                <button type="submit" className="boton boton-principal" disabled={guardando}>
                  {guardando ? "Guardando…" : "Guardar cambios"}
                </button>
              </div>
            </div>
          </form>
        </div>
        <div className="columna">
          <section className="tarjeta">
            <div className="tarjeta-cuerpo">
              <h3>¿Quién lo ve?</h3>
              <p className="nota-pequena">
                Si activás la opción, otros peritos ven este correo en el resumen de tus casos cerrados, para consultarte
                sobre un caso que trataste. Si la desactivás, no se muestra.
              </p>
            </div>
          </section>
        </div>
      </div>
    </Vista>
  );
}
