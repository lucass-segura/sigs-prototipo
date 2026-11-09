import { formatearFecha } from "@/lib/fechas";
import { TIPOS_SINIESTRO_SUGERIDOS } from "@/lib/etiquetas";
import type { CampoTexto } from "@/lib/asistenteSiniestro";
import { Campo } from "../Campo";
import { SelectorFecha } from "../fechas/SelectorFecha";
import { SelectorHora } from "../fechas/SelectorHora";
import { useAhora } from "../fechas/useAhora";
import type { PropsPaso } from "./tipos";

export const MENSAJE_FECHA_HECHO_REQUERIDA = "Elegí la fecha del hecho.";
export const MENSAJE_HORA_HECHO_REQUERIDA = "Elegí la hora del hecho.";
/** El mismo texto que devuelve la API (S34), para la fecha y para la hora. */
export const MENSAJE_HECHO_FUTURO = "La fecha del hecho no puede ser futura.";

export function PasoHecho({ datos, cambiar, mensajes, selector }: PropsPaso) {
  const ahora = useAhora();
  const poner = (campo: CampoTexto) => (valor: string) => cambiar({ tipo: "campo", campo, valor });
  return (
    <div className="tarjeta-cuerpo">
      <h3 className="paso-subtitulo">Hecho</h3>
      <Campo etiqueta="Tipo de siniestro" id="tipo" errores={mensajes("tipo", "tipo")}>
        <input id="tipo" list="tipos-siniestro" value={datos.tipo} onChange={(e) => poner("tipo")(e.target.value)} />
        <datalist id="tipos-siniestro">
          {TIPOS_SINIESTRO_SUGERIDOS.map((t) => (
            <option key={t} value={t} />
          ))}
        </datalist>
      </Campo>
      <div className="rejilla-campos rejilla-fecha-hora">
        <Campo
          etiqueta="Fecha del hecho"
          id="fecha-hecho"
          ayuda="No puede ser futura ni anterior al inicio de vigencia de la póliza."
          errores={mensajes("fecha-hecho", "fecha_hecho")}
        >
          <SelectorFecha
            id="fecha-hecho"
            etiqueta="Fecha del hecho"
            valor={datos.fechaHecho}
            onCambio={poner("fechaHecho")}
            minimo={datos.inicioVigencia || undefined}
            motivoMinimo={`Es anterior al inicio de vigencia de la póliza (${formatearFecha(datos.inicioVigencia)}): un hecho anterior no es un siniestro.`}
            noFuturo
            motivoMaximo={MENSAJE_HECHO_FUTURO}
            atajos={["hoy", "ayer"]}
            requerido
            mensajeRequerido={MENSAJE_FECHA_HECHO_REQUERIDA}
            {...selector("fecha-hecho")}
          />
        </Campo>
        <Campo etiqueta="Hora del hecho" id="hora-hecho">
          <SelectorHora
            id="hora-hecho"
            etiqueta="Hora del hecho"
            valor={datos.horaHecho}
            onCambio={poner("horaHecho")}
            maxima={datos.fechaHecho && datos.fechaHecho === ahora.fecha ? ahora.hora : undefined}
            motivoMaxima={MENSAJE_HECHO_FUTURO}
            requerido
            mensajeRequerido={MENSAJE_HORA_HECHO_REQUERIDA}
            {...selector("hora-hecho")}
          />
        </Campo>
      </div>
      <Campo etiqueta="Lugar" id="lugar" errores={mensajes("lugar", "lugar")}>
        <input id="lugar" value={datos.lugar} onChange={(e) => poner("lugar")(e.target.value)} />
      </Campo>
      <Campo etiqueta="Relato" id="relato" errores={mensajes("relato", "relato")}>
        <textarea id="relato" value={datos.relato} onChange={(e) => poner("relato")(e.target.value)} />
      </Campo>

      <h3 className="paso-subtitulo">Denuncia</h3>
      <div className="rejilla-campos rejilla-fecha-hora">
        <Campo etiqueta="Fecha de denuncia" id="fecha-denuncia" errores={mensajes("fecha-denuncia", "fecha_denuncia")}>
          <SelectorFecha
            id="fecha-denuncia"
            etiqueta="Fecha de denuncia"
            valor={datos.fechaDenuncia}
            onCambio={poner("fechaDenuncia")}
            atajos={["hoy"]}
            aviso={(v) => (datos.fechaHecho && v < datos.fechaHecho ? "La denuncia es anterior al día del hecho. Revisá las fechas." : null)}
            {...selector("fecha-denuncia")}
          />
        </Campo>
        <Campo etiqueta="Hora de la denuncia" id="hora-denuncia" errores={mensajes("hora-denuncia", "hora_denuncia")}>
          <SelectorHora
            id="hora-denuncia"
            etiqueta="Hora de la denuncia"
            valor={datos.horaDenuncia}
            onCambio={poner("horaDenuncia")}
            {...selector("hora-denuncia")}
          />
        </Campo>
      </div>
      <div className="rejilla-campos col-2">
        <Campo etiqueta="Número de denuncia" id="numero-denuncia" errores={mensajes("numero-denuncia", "numero_denuncia")}>
          <input id="numero-denuncia" className="mono" value={datos.numeroDenuncia} onChange={(e) => poner("numeroDenuncia")(e.target.value)} />
        </Campo>
        <Campo etiqueta="Asesor que carga" id="asesor" errores={mensajes("asesor", "asesor")}>
          <input id="asesor" value={datos.asesor} onChange={(e) => poner("asesor")(e.target.value)} />
        </Campo>
      </div>
      <Campo etiqueta="Intervenciones" id="intervenciones" errores={mensajes("intervenciones", "intervenciones")}>
        <input
          id="intervenciones"
          value={datos.intervenciones}
          placeholder="Por ejemplo, bomberos y policía"
          onChange={(e) => poner("intervenciones")(e.target.value)}
        />
      </Campo>
      <Campo etiqueta="Documentación adjunta" id="documentacion-adjunta" errores={mensajes("documentacion-adjunta", "documentacion_adjunta")}>
        <textarea
          id="documentacion-adjunta"
          value={datos.documentacionAdjunta}
          onChange={(e) => poner("documentacionAdjunta")(e.target.value)}
        />
      </Campo>
    </div>
  );
}
