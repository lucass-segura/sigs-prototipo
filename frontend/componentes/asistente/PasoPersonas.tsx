import { ETIQUETA_ROL_PERSONA, ROLES_PERSONA, TIPOS_IDENTIFICADOR } from "@/lib/etiquetas";
import { indiceEnviado, personasEnviables } from "@/lib/asistenteSiniestro";
import type { TipoIdentificador } from "@/lib/tipos";
import { Campo } from "../Campo";
import type { PropsPaso } from "./tipos";

export function PasoPersonas({ datos, cambiar, mensajes }: PropsPaso) {
  const enviables = personasEnviables(datos.personas);
  return (
    <>
      {datos.personas.length === 0 ? <p className="vacio">Todavía no agregaste personas.</p> : null}
      {datos.personas.map((p) => {
        // Los errores de la API numeran las personas que se enviaron, no las filas en blanco.
        const indice = indiceEnviado(enviables, p.clave);
        const ruta = (campo: string) => (indice === null ? undefined : `personas.${indice}.${campo}`);
        const idRoles = `p-roles-${p.clave}`;
        const erroresRoles = mensajes(idRoles, ruta("roles"));
        return (
          <div className="fila-persona" key={p.clave}>
            <div className="rejilla-campos col-3">
              <Campo etiqueta="Tipo de identificador" id={`p-tipo-${p.clave}`} errores={mensajes(`p-tipo-${p.clave}`, ruta("tipo_identificador"))}>
                <select
                  id={`p-tipo-${p.clave}`}
                  value={p.tipo_identificador}
                  onChange={(e) =>
                    cambiar({ tipo: "persona/actualizar", clave: p.clave, cambios: { tipo_identificador: e.target.value as TipoIdentificador } })
                  }
                >
                  {TIPOS_IDENTIFICADOR.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </Campo>
              <Campo etiqueta="Identificador" id={`p-id-${p.clave}`} errores={mensajes(`p-id-${p.clave}`, ruta("identificador"))}>
                <input
                  id={`p-id-${p.clave}`}
                  className="mono"
                  value={p.identificador}
                  onChange={(e) => cambiar({ tipo: "persona/actualizar", clave: p.clave, cambios: { identificador: e.target.value } })}
                />
              </Campo>
              <Campo etiqueta="Nombre" id={`p-nombre-${p.clave}`} errores={mensajes(`p-nombre-${p.clave}`, ruta("nombre"))}>
                <input
                  id={`p-nombre-${p.clave}`}
                  value={p.nombre}
                  onChange={(e) => cambiar({ tipo: "persona/actualizar", clave: p.clave, cambios: { nombre: e.target.value } })}
                />
              </Campo>
            </div>
            <div className="campo">
              <span className="etiqueta-grupo" id={`p-rol-etiqueta-${p.clave}`}>
                Rol
              </span>
              <div className="grupo-casillas" role="group" aria-labelledby={`p-rol-etiqueta-${p.clave}`}>
                {ROLES_PERSONA.map((rol, i) => (
                  <label className="casilla" key={rol}>
                    <input
                      id={i === 0 ? idRoles : undefined}
                      type="checkbox"
                      checked={p.roles.includes(rol)}
                      onChange={() => cambiar({ tipo: "persona/alternarRol", clave: p.clave, rol })}
                    />
                    {ETIQUETA_ROL_PERSONA[rol]}
                  </label>
                ))}
              </div>
              {erroresRoles.length > 0 ? (
                <small className="error-campo" role="alert">
                  {erroresRoles.join(" ")}
                </small>
              ) : null}
            </div>
            <div className="acciones-fila">
              <button type="button" className="boton boton-chico boton-peligro" onClick={() => cambiar({ tipo: "persona/quitar", clave: p.clave })}>
                Quitar persona
              </button>
            </div>
          </div>
        );
      })}
    </>
  );
}
