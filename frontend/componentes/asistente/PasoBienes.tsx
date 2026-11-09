import { ETIQUETA_TIPO_BIEN, TIPOS_BIEN } from "@/lib/etiquetas";
import { bienesEnviables, indiceEnviado, tieneAtributosDeVehiculo } from "@/lib/asistenteSiniestro";
import type { TipoBien } from "@/lib/tipos";
import { Campo } from "../Campo";
import type { PropsPaso } from "./tipos";

export function PasoBienes({ datos, cambiar, mensajes }: PropsPaso) {
  const enviables = bienesEnviables(datos.bienes);
  return (
    <>
      {datos.bienes.length === 0 ? <p className="vacio">Todavía no agregaste bienes.</p> : null}
      {datos.bienes.map((b) => {
        const indice = indiceEnviado(enviables, b.clave);
        const ruta = (campo: string) => (indice === null ? undefined : `bienes.${indice}.${campo}`);
        const actualizar = (cambios: Partial<typeof b>) => cambiar({ tipo: "bien/actualizar", clave: b.clave, cambios });
        return (
          <div className="fila-persona" key={b.clave}>
            <div className="rejilla-campos col-3">
              <Campo etiqueta="Tipo" id={`b-tipo-${b.clave}`} errores={mensajes(`b-tipo-${b.clave}`, ruta("tipo"))}>
                <select id={`b-tipo-${b.clave}`} value={b.tipo} onChange={(e) => actualizar({ tipo: e.target.value as TipoBien })}>
                  {TIPOS_BIEN.map((t) => (
                    <option key={t} value={t}>
                      {ETIQUETA_TIPO_BIEN[t]}
                    </option>
                  ))}
                </select>
              </Campo>
              <Campo
                etiqueta="Identificador"
                id={`b-id-${b.clave}`}
                ayuda="Dominio, IMEI o número de serie. Se normaliza sin espacios ni guiones. Solo los vehículos y las motos se cruzan con otros casos por su patente."
                errores={mensajes(`b-id-${b.clave}`, ruta("identificador"))}
              >
                <input id={`b-id-${b.clave}`} className="mono" value={b.identificador} onChange={(e) => actualizar({ identificador: e.target.value })} />
              </Campo>
              <Campo etiqueta="Descripción" id={`b-desc-${b.clave}`} errores={mensajes(`b-desc-${b.clave}`, ruta("descripcion"))}>
                <input id={`b-desc-${b.clave}`} value={b.descripcion} onChange={(e) => actualizar({ descripcion: e.target.value })} />
              </Campo>
            </div>
            {tieneAtributosDeVehiculo(b.tipo) ? (
              <div className="rejilla-campos col-2">
                <Campo etiqueta="Motor (opcional)" id={`b-motor-${b.clave}`}>
                  <input id={`b-motor-${b.clave}`} className="mono" value={b.motor} onChange={(e) => actualizar({ motor: e.target.value })} />
                </Campo>
                <Campo etiqueta="Chasis (opcional)" id={`b-chasis-${b.clave}`}>
                  <input id={`b-chasis-${b.clave}`} className="mono" value={b.chasis} onChange={(e) => actualizar({ chasis: e.target.value })} />
                </Campo>
              </div>
            ) : null}
            <Campo etiqueta="Detalle del daño" id={`b-dano-${b.clave}`} errores={mensajes(`b-dano-${b.clave}`, ruta("detalle_dano"))}>
              <input id={`b-dano-${b.clave}`} value={b.detalle_dano} onChange={(e) => actualizar({ detalle_dano: e.target.value })} />
            </Campo>
            <div className="acciones-fila">
              <button type="button" className="boton boton-chico boton-peligro" onClick={() => cambiar({ tipo: "bien/quitar", clave: b.clave })}>
                Quitar bien
              </button>
            </div>
          </div>
        );
      })}
    </>
  );
}
