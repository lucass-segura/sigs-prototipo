import type { Accion, DatosSiniestro } from "@/lib/asistenteSiniestro";

/** Lo que reciben los pasos del asistente: los datos viven arriba, los pasos solo los muestran y los cambian. */
export interface PropsPaso {
  datos: DatosSiniestro;
  cambiar: (accion: Accion) => void;
  /** Mensajes de un control: los que devolvió la API (por su ruta) y los de la validación suave (por su id). */
  mensajes: (id: string, ruta?: string) => string[];
  /** Lo que necesitan los selectores de fecha y hora para informar si tienen un valor que no se puede enviar. */
  selector: (id: string) => { onInvalido: (mensaje: string | null) => void; revision: number };
}
