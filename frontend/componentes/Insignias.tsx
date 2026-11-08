import type { EstadoSiniestro, Prioridad } from "@/lib/tipos";
import { ETIQUETA_ESTADO, ETIQUETA_PRIORIDAD } from "@/lib/etiquetas";

export function InsigniaEstado({ estado }: { estado: EstadoSiniestro }) {
  return <span className={`insignia insignia-estado-${estado}`}>{ETIQUETA_ESTADO[estado]}</span>;
}

/** «Alta · 55» en el panel; «Prioridad alta» en el análisis. */
export function InsigniaPrioridad({
  prioridad,
  puntaje,
  texto,
}: {
  prioridad: Prioridad;
  puntaje?: number | null;
  texto?: string;
}) {
  const contenido =
    texto ?? (puntaje == null ? ETIQUETA_PRIORIDAD[prioridad] : `${ETIQUETA_PRIORIDAD[prioridad]} · ${puntaje}`);
  return <span className={`insignia insignia-prioridad-${prioridad}`}>{contenido}</span>;
}
