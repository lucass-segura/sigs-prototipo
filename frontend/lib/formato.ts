// Formato de fechas y textos de la interfaz (zona horaria de Argentina).

const ZONA = "America/Argentina/Buenos_Aires";

const MESES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

/** Partes (año, mes, día, hora, minuto) en la zona de Argentina. */
function partes(valor: string): { a: string; m: string; d: string; h: string; mi: string } | null {
  if (/^\d{4}-\d{2}-\d{2}$/.test(valor)) {
    return { a: valor.slice(0, 4), m: valor.slice(5, 7), d: valor.slice(8, 10), h: "00", mi: "00" };
  }
  const fecha = new Date(valor);
  if (Number.isNaN(fecha.getTime())) return null;
  const formato = new Intl.DateTimeFormat("en-CA", {
    timeZone: ZONA,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
  const mapa: Record<string, string> = {};
  for (const p of formato.formatToParts(fecha)) mapa[p.type] = p.value;
  return { a: mapa.year, m: mapa.month, d: mapa.day, h: mapa.hour, mi: mapa.minute };
}

/** 12/08/2026 */
export function formatoFecha(valor: string | null | undefined): string {
  if (!valor) return "—";
  const p = partes(valor);
  return p ? `${p.d}/${p.m}/${p.a}` : valor;
}

/** 12/08/2026 23:40 */
export function formatoFechaHora(valor: string | null | undefined): string {
  if (!valor) return "—";
  const p = partes(valor);
  return p ? `${p.d}/${p.m}/${p.a} ${p.h}:${p.mi}` : valor;
}

/** 12/08 */
export function formatoDiaMes(valor: string | null | undefined): string {
  if (!valor) return "—";
  const p = partes(valor);
  return p ? `${p.d}/${p.m}` : valor;
}

/** 07/2025 */
export function formatoMesAnioCorto(valor: string | null | undefined): string {
  if (!valor) return "—";
  const p = partes(valor);
  return p ? `${p.m}/${p.a}` : valor;
}

/** Julio de 2025 */
export function formatoMesAnio(valor: string | null | undefined): string {
  if (!valor) return "—";
  const p = partes(valor);
  if (!p) return valor;
  const mes = MESES[Number(p.m) - 1] ?? p.m;
  return `${mes.charAt(0).toUpperCase()}${mes.slice(1)} de ${p.a}`;
}

/** Valor para `<input type="datetime-local">` a partir de un ISO. */
export function aInputFechaHora(valor: string | null | undefined): string {
  if (!valor) return "";
  const p = partes(valor);
  return p ? `${p.a}-${p.m}-${p.d}T${p.h}:${p.mi}` : "";
}

/** Valor para `<input type="date">` a partir de un ISO. */
export function aInputFecha(valor: string | null | undefined): string {
  if (!valor) return "";
  const p = partes(valor);
  return p ? `${p.a}-${p.m}-${p.d}` : "";
}

/** Valor para `<input type="time">` a partir de `HH:MM:SS`. */
export function aInputHora(valor: string | null | undefined): string {
  return valor ? valor.slice(0, 5) : "";
}

/** 10:20 h */
export function formatoHora(valor: string | null | undefined): string {
  return valor ? `${valor.slice(0, 5)} h` : "—";
}

export function hoyISO(): string {
  const p = partes(new Date().toISOString());
  return p ? `${p.a}-${p.m}-${p.d}` : "";
}

/** `true` si la fecha (día) es anterior a hoy. */
export function estaVencida(valor: string | null | undefined): boolean {
  if (!valor) return false;
  const dia = aInputFecha(valor);
  return dia !== "" && dia < hoyISO();
}

/** 7,0 */
export function formatoDecimal(n: number, decimales = 1): string {
  return n.toFixed(decimales).replace(".", ",");
}

export function formatoTamanio(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1).replace(".", ",")} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

export function formatoVersionCorta(version: string): string {
  return version.replace(/^RS-/, "");
}
