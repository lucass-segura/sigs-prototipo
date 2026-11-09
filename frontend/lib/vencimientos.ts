// Cómo se agrupa y se describe el vencimiento de una tarea (días de calendario, zona de Argentina).
import { diasDesdeHoy, formatoDiaMes } from "./formato";
import type { EstadoTarea } from "./tipos";

export type GrupoVencimiento = "vencida" | "hoy" | "semana" | "mas_adelante" | "sin_fecha" | "hecha";

/** «Esta semana» son los próximos 7 días, igual que el contador del panel. */
export const DIAS_SEMANA = 7;

export function grupoDeVencimiento(estado: EstadoTarea, vence: string | null): GrupoVencimiento {
  if (estado === "hecha") return "hecha";
  const dias = diasDesdeHoy(vence);
  if (dias === null) return "sin_fecha";
  if (dias < 0) return "vencida";
  if (dias === 0) return "hoy";
  if (dias <= DIAS_SEMANA) return "semana";
  return "mas_adelante";
}

export const TITULO_GRUPO: Record<GrupoVencimiento, string> = {
  vencida: "Vencidas",
  hoy: "Vencen hoy",
  semana: "Esta semana",
  mas_adelante: "Más adelante",
  sin_fecha: "Sin fecha",
  hecha: "Hechas",
};

export const ORDEN_GRUPOS: GrupoVencimiento[] = ["vencida", "hoy", "semana", "mas_adelante", "sin_fecha", "hecha"];

export interface InsigniaVencimiento {
  texto: string;
  clase: "vencida" | "hoy" | "semana" | "normal" | "sin-fecha";
}

function plural(n: number, uno: string, varios: string) {
  return `${n} ${n === 1 ? uno : varios}`;
}

/** Texto corto del vencimiento para la tarjeta: «Vencida hace 3 días», «Vence hoy», «Vence el 27/08»… */
export function insigniaDeVencimiento(estado: EstadoTarea, vence: string | null): InsigniaVencimiento {
  const grupo = grupoDeVencimiento(estado, vence);
  const dias = diasDesdeHoy(vence);
  if (grupo === "sin_fecha") return { texto: "Sin fecha", clase: "sin-fecha" };
  if (grupo === "hecha") return { texto: vence ? `Vencía el ${formatoDiaMes(vence)}` : "Sin fecha", clase: "sin-fecha" };
  if (grupo === "vencida") return { texto: `Vencida hace ${plural(Math.abs(dias ?? 0), "día", "días")}`, clase: "vencida" };
  if (grupo === "hoy") return { texto: "Vence hoy", clase: "hoy" };
  if (grupo === "semana") return { texto: dias === 1 ? "Vence mañana" : `Vence en ${dias} días`, clase: "semana" };
  return { texto: `Vence el ${formatoDiaMes(vence)}`, clase: "normal" };
}
