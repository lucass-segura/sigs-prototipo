import { SelectorFecha } from "../fechas/SelectorFecha";
import { Campo } from "../Campo";
import type { PropsPaso } from "./tipos";

export function PasoPoliza({ datos, cambiar, mensajes, selector }: PropsPaso) {
  const poner = (campo: "compania" | "numeroPoliza" | "cobertura") => (valor: string) => cambiar({ tipo: "campo", campo, valor });
  return (
    <div className="tarjeta-cuerpo">
      <div className="rejilla-campos rejilla-poliza">
        <Campo etiqueta="Compañía" id="compania" errores={mensajes("compania", "poliza.compania")}>
          <input id="compania" value={datos.compania} onChange={(e) => poner("compania")(e.target.value)} />
        </Campo>
        <Campo etiqueta="Número de póliza" id="numero-poliza" errores={mensajes("numero-poliza", "poliza.numero")}>
          <input id="numero-poliza" value={datos.numeroPoliza} onChange={(e) => poner("numeroPoliza")(e.target.value)} />
        </Campo>
        <Campo etiqueta="Cobertura" id="cobertura" errores={mensajes("cobertura", "poliza.cobertura")}>
          <input id="cobertura" value={datos.cobertura} onChange={(e) => poner("cobertura")(e.target.value)} />
        </Campo>
        <Campo etiqueta="Inicio de vigencia" id="inicio-vigencia" errores={mensajes("inicio-vigencia", "poliza.inicio_vigencia")}>
          <SelectorFecha
            id="inicio-vigencia"
            etiqueta="Inicio de vigencia"
            valor={datos.inicioVigencia}
            onCambio={(valor) => cambiar({ tipo: "campo", campo: "inicioVigencia", valor })}
            atajos={["hoy"]}
            {...selector("inicio-vigencia")}
          />
        </Campo>
        <Campo etiqueta="Primer pago" id="primer-pago" errores={mensajes("primer-pago", "poliza.primer_pago")}>
          <SelectorFecha
            id="primer-pago"
            etiqueta="Primer pago"
            valor={datos.primerPago}
            onCambio={(valor) => cambiar({ tipo: "campo", campo: "primerPago", valor })}
            atajos={["hoy"]}
            aviso={(v) => (datos.fechaHecho && v > datos.fechaHecho ? "El primer pago es posterior al día del hecho." : null)}
            {...selector("primer-pago")}
          />
        </Campo>
      </div>
    </div>
  );
}
