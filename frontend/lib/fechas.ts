// Fechas y horas de los selectores: lectura de lo que se escribe, formato es-AR y cuentas de calendario.
// Sin dependencias (ni de React ni del resto de lib/) para poder probarlo con `node --test`.
// Las fechas viajan como texto `AAAA-MM-DD`, las horas como `HH:MM` y la fecha con hora como `AAAA-MM-DDTHH:MM`.

export const ZONA = "America/Argentina/Buenos_Aires";

export const MESES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

/** Semana que empieza el lunes. */
export const DIAS_CORTOS = ["lu", "ma", "mi", "ju", "vi", "sá", "do"];
export const DIAS_LARGOS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];

export const ANIO_MINIMO = 1900;
export const ANIO_MAXIMO = 2100;

const pad = (n: number, largo = 2) => String(n).padStart(largo, "0");

export type ResultadoLectura =
  | { ok: true; valor: string }
  | { ok: false; mensaje: string; incompleta: boolean };

// ------------------------------------------------------------ Calendario

export function diasDelMes(anio: number, mes: number): number {
  return new Date(Date.UTC(anio, mes, 0)).getUTCDate();
}

export function esFechaReal(anio: number, mes: number, dia: number): boolean {
  return mes >= 1 && mes <= 12 && dia >= 1 && dia <= diasDelMes(anio, mes);
}

export function armarISO(anio: number, mes: number, dia: number): string {
  return `${pad(anio, 4)}-${pad(mes)}-${pad(dia)}`;
}

/** `AAAA-MM-DD` → partes numéricas; `null` si no es una fecha real. */
export function partesISO(iso: string | null | undefined): { a: number; m: number; d: number } | null {
  if (!iso || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return null;
  const a = Number(iso.slice(0, 4));
  const m = Number(iso.slice(5, 7));
  const d = Number(iso.slice(8, 10));
  return esFechaReal(a, m, d) ? { a, m, d } : null;
}

export function sumarDiasISO(iso: string, dias: number): string {
  const p = partesISO(iso);
  if (!p) return iso;
  const f = new Date(Date.UTC(p.a, p.m - 1, p.d + dias));
  return armarISO(f.getUTCFullYear(), f.getUTCMonth() + 1, f.getUTCDate());
}

/** Suma meses conservando el día; si el mes nuevo es más corto queda en su último día. */
export function sumarMesesISO(iso: string, meses: number): string {
  const p = partesISO(iso);
  if (!p) return iso;
  const total = p.a * 12 + (p.m - 1) + meses;
  const a = Math.floor(total / 12);
  const m = (total % 12) + 1;
  return armarISO(a, m, Math.min(p.d, diasDelMes(a, m)));
}

export function finDeMesISO(iso: string): string {
  const p = partesISO(iso);
  return p ? armarISO(p.a, p.m, diasDelMes(p.a, p.m)) : iso;
}

export function inicioDeMesISO(iso: string): string {
  const p = partesISO(iso);
  return p ? armarISO(p.a, p.m, 1) : iso;
}

/** 0 = lunes … 6 = domingo. */
export function diaDeSemana(iso: string): number {
  const p = partesISO(iso);
  if (!p) return 0;
  return (new Date(Date.UTC(p.a, p.m - 1, p.d)).getUTCDay() + 6) % 7;
}

/** Lunes de la semana del día dado. */
export function inicioDeSemanaISO(iso: string): string {
  return sumarDiasISO(iso, -diaDeSemana(iso));
}

export function finDeSemanaISO(iso: string): string {
  return sumarDiasISO(iso, 6 - diaDeSemana(iso));
}

/** Seis semanas de siete días (lunes a domingo) que cubren el mes de `iso`. */
export function matrizDelMes(iso: string): string[][] {
  const primero = inicioDeMesISO(iso);
  const desde = inicioDeSemanaISO(primero);
  return Array.from({ length: 6 }, (_, semana) =>
    Array.from({ length: 7 }, (_, dia) => sumarDiasISO(desde, semana * 7 + dia)),
  );
}

export function compararISO(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** `"antes"` o `"despues"` si la fecha queda fuera de [minimo, maximo]; `null` si está dentro. */
export function fueraDeRango(iso: string, minimo?: string, maximo?: string): "antes" | "despues" | null {
  if (minimo && iso < minimo) return "antes";
  if (maximo && iso > maximo) return "despues";
  return null;
}

/** Lleva la fecha al rango permitido. */
export function ajustarARango(iso: string, minimo?: string, maximo?: string): string {
  if (minimo && iso < minimo) return minimo;
  if (maximo && iso > maximo) return maximo;
  return iso;
}

// ------------------------------------------------------------ Formato

/** `2026-08-12` → `12/08/2026`; vacío si no es una fecha. */
export function formatearFecha(iso: string | null | undefined): string {
  const p = partesISO(iso);
  return p ? `${pad(p.d)}/${pad(p.m)}/${pad(p.a, 4)}` : "";
}

/** `2026-08-12` → `miércoles 12 de agosto de 2026` (para el lector de pantalla y los títulos). */
export function nombreLargoFecha(iso: string | null | undefined): string {
  const p = partesISO(iso);
  if (!p || !iso) return "";
  return `${DIAS_LARGOS[diaDeSemana(iso)]} ${p.d} de ${MESES[p.m - 1]} de ${p.a}`;
}

export function capitalizar(texto: string): string {
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

/** `agosto de 2026` */
export function nombreMesAnio(iso: string): string {
  const p = partesISO(iso);
  return p ? `${MESES[p.m - 1]} de ${p.a}` : "";
}

// ------------------------------------------------------------ Hoy y ahora (Buenos Aires)

/** Fecha y hora de pared en la zona de Argentina. */
export function ahoraLocal(instante: Date = new Date()): { fecha: string; hora: string } {
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
  for (const p of formato.formatToParts(instante)) mapa[p.type] = p.value;
  return { fecha: `${mapa.year}-${mapa.month}-${mapa.day}`, hora: `${mapa.hour}:${mapa.minute}` };
}

// ------------------------------------------------------------ Fechas escritas a mano

/** Con solo dígitos y barras en su lugar (`12/0`, `12/08/2`) el formato se rearma solo; si hay otra forma (`1/`, `12/8/`), se respeta. */
function formatoAutomatico(texto: string): boolean {
  const tramos = texto.split(/[/.\-\s]/);
  return tramos.length <= 3 && tramos.slice(0, -1).every((t) => t.length === 2);
}

/** Lo que se ve mientras se escribe: solo dígitos y separadores; las barras se agregan solas (`120826` → `12/08/26`). */
export function mascaraFecha(texto: string): string {
  const limpio = texto.replace(/[^\d/.\-\s]/g, "");
  if (!formatoAutomatico(limpio)) return limpio.slice(0, 10);
  const d = limpio.replace(/\D/g, "").slice(0, 8);
  if (d.length <= 2) return d;
  if (d.length <= 4) return `${d.slice(0, 2)}/${d.slice(2)}`;
  return `${d.slice(0, 2)}/${d.slice(2, 4)}/${d.slice(4)}`;
}

const ERROR_FORMATO_FECHA = "Escribí la fecha como día, mes y año, por ejemplo 12/08/2026.";

/**
 * Lee una fecha escrita a mano: `12/08/2026`, `12/8/26`, `120826`, `12082026`, `12-8-26`, `12.08`.
 * Sin año se toma el de `hoy`; con dos cifras de año se toma 20aa.
 */
export function analizarFecha(texto: string, hoy: string): ResultadoLectura {
  const t = texto.trim();
  if (t === "") return { ok: false, mensaje: "", incompleta: true };
  if (/[^\d/.\-\s]/.test(t)) {
    return { ok: false, mensaje: "Usá solo números y barras, por ejemplo 12/08/2026.", incompleta: false };
  }

  let dia: string;
  let mes: string;
  let anio: string | undefined;
  if (/^\d+$/.test(t)) {
    if (t.length === 4) [dia, mes] = [t.slice(0, 2), t.slice(2)];
    else if (t.length === 6) [dia, mes, anio] = [t.slice(0, 2), t.slice(2, 4), t.slice(4)];
    else if (t.length === 8) [dia, mes, anio] = [t.slice(0, 2), t.slice(2, 4), t.slice(4)];
    else return { ok: false, mensaje: ERROR_FORMATO_FECHA, incompleta: t.length < 8 };
  } else {
    if (/[/.\-\s]$/.test(t)) return { ok: false, mensaje: ERROR_FORMATO_FECHA, incompleta: true };
    const partes = t.split(/[/.\-\s]+/).filter(Boolean);
    if (partes.length < 2 || partes.length > 3) return { ok: false, mensaje: ERROR_FORMATO_FECHA, incompleta: partes.length < 2 };
    [dia, mes, anio] = partes;
  }

  if (dia.length > 2 || mes.length > 2) return { ok: false, mensaje: ERROR_FORMATO_FECHA, incompleta: false };
  // Un «0» solo es el principio de un día o un mes ("0" → "08"): se sigue escribiendo.
  if (dia === "0" || mes === "0") return { ok: false, mensaje: ERROR_FORMATO_FECHA, incompleta: true };
  const d = Number(dia);
  const m = Number(mes);
  let a: number;
  if (anio === undefined) {
    a = Number(hoy.slice(0, 4));
  } else if (anio.length === 2) {
    a = 2000 + Number(anio);
  } else if (anio.length === 4) {
    a = Number(anio);
  } else {
    return { ok: false, mensaje: "El año tiene que ser de 2 o de 4 cifras, por ejemplo 26 o 2026.", incompleta: anio.length < 4 };
  }

  if (m < 1 || m > 12) return { ok: false, mensaje: `El mes ${mes} no existe: va de 1 a 12.`, incompleta: false };
  if (a < ANIO_MINIMO || a > ANIO_MAXIMO) {
    return { ok: false, mensaje: `El año tiene que estar entre ${ANIO_MINIMO} y ${ANIO_MAXIMO}.`, incompleta: false };
  }
  if (d < 1 || d > diasDelMes(a, m)) {
    return {
      ok: false,
      mensaje: `${MESES[m - 1].charAt(0).toUpperCase()}${MESES[m - 1].slice(1)} de ${a} tiene ${diasDelMes(a, m)} días: el día ${dia} no existe.`,
      incompleta: false,
    };
  }
  return { ok: true, valor: armarISO(a, m, d) };
}

// ------------------------------------------------------------ Horas

/** Cantidad de cifras de la hora cuando solo se escribieron dígitos: `930` → 1 (9:30), `2340` → 2. */
function cifrasDeHora(digitos: string): number {
  if (digitos.length === 0) return 0;
  if (Number(digitos[0]) > 2) return 1;
  if (digitos.length >= 2 && Number(digitos.slice(0, 2)) > 23) return 1;
  return 2;
}

/** Lo que se ve mientras se escribe la hora: los dos puntos se agregan solos (`2340` → `23:40`, `930` → `9:30`). */
export function mascaraHora(texto: string): string {
  const limpio = texto.replace(/[^\d:.\s]/g, "");
  const d = limpio.replace(/\D/g, "").slice(0, 4);
  const h = cifrasDeHora(d);
  const tramos = limpio.split(/[:.\s]/);
  // Si la hora se escribió con otra cantidad de cifras que la automática (`1:30`), se respeta.
  if (tramos.length > 1 && tramos[0].length !== h) return limpio.slice(0, 5);
  return d.length <= h ? d : `${d.slice(0, h)}:${d.slice(h)}`;
}

const ERROR_FORMATO_HORA = "Escribí la hora como horas y minutos, por ejemplo 23:40.";

/** Lee una hora escrita a mano: `23:40`, `2340`, `9:30`, `930`, `9`, `9.30` (24 h). */
export function analizarHora(texto: string): ResultadoLectura {
  const t = texto.trim();
  if (t === "") return { ok: false, mensaje: "", incompleta: true };
  if (/[^\d:.\s]/.test(t)) return { ok: false, mensaje: "Usá solo números y dos puntos, por ejemplo 23:40.", incompleta: false };

  let h: string;
  let mi: string;
  if (/^\d+$/.test(t)) {
    if (t.length > 4) return { ok: false, mensaje: ERROR_FORMATO_HORA, incompleta: false };
    const cifras = cifrasDeHora(t);
    h = t.slice(0, cifras);
    mi = t.slice(cifras) || "00";
  } else {
    if (/[:.\s]$/.test(t)) return { ok: false, mensaje: ERROR_FORMATO_HORA, incompleta: true };
    const partes = t.split(/[:.\s]+/).filter(Boolean);
    if (partes.length !== 2) return { ok: false, mensaje: ERROR_FORMATO_HORA, incompleta: partes.length < 2 };
    [h, mi] = partes;
  }
  if (h.length > 2 || mi.length > 2) return { ok: false, mensaje: ERROR_FORMATO_HORA, incompleta: false };
  if (mi.length === 1) return { ok: false, mensaje: "Escribí los minutos con dos cifras, por ejemplo 09:05.", incompleta: true };
  if (Number(h) > 23) return { ok: false, mensaje: `La hora ${h} no existe: va de 00 a 23.`, incompleta: false };
  if (Number(mi) > 59) return { ok: false, mensaje: `Los minutos ${mi} no existen: van de 00 a 59.`, incompleta: false };
  return { ok: true, valor: `${pad(Number(h))}:${mi}` };
}

/** `23:40:00` o `23:40` → `23:40`. */
export function formatearHora(valor: string | null | undefined): string {
  return valor && /^\d{2}:\d{2}/.test(valor) ? valor.slice(0, 5) : "";
}

export function compararHora(a: string, b: string): number {
  return a < b ? -1 : a > b ? 1 : 0;
}

// ------------------------------------------------------------ Evaluar lo escrito contra los límites

export interface LimitesFecha {
  minimo?: string;
  maximo?: string;
  motivoMinimo?: string;
  motivoMaximo?: string;
}

export interface EvaluacionCampo {
  /** `vacio`: nada escrito; `incompleto`: se está escribiendo; `error`: no se puede usar; `ok`: valor listo. */
  estado: "vacio" | "incompleto" | "error" | "ok";
  /** Valor que se envía (`""` si no hay uno válido). */
  valor: string;
  mensaje: string;
}

export function mensajeFueraDeRango(iso: string, limites: LimitesFecha): string | null {
  const lado = fueraDeRango(iso, limites.minimo, limites.maximo);
  if (lado === "antes") {
    return limites.motivoMinimo ?? `La fecha no puede ser anterior al ${formatearFecha(limites.minimo)}.`;
  }
  if (lado === "despues") {
    return limites.motivoMaximo ?? `La fecha no puede ser posterior al ${formatearFecha(limites.maximo)}.`;
  }
  return null;
}

export function evaluarFecha(texto: string, hoy: string, limites: LimitesFecha = {}): EvaluacionCampo {
  if (texto.trim() === "") return { estado: "vacio", valor: "", mensaje: "" };
  const lectura = analizarFecha(texto, hoy);
  if (!lectura.ok) {
    return { estado: lectura.incompleta ? "incompleto" : "error", valor: "", mensaje: lectura.mensaje };
  }
  const fuera = mensajeFueraDeRango(lectura.valor, limites);
  if (fuera) return { estado: "error", valor: "", mensaje: fuera };
  return { estado: "ok", valor: lectura.valor, mensaje: "" };
}

export interface LimitesHora {
  minima?: string;
  maxima?: string;
  motivoMinima?: string;
  motivoMaxima?: string;
}

export function evaluarHora(texto: string, limites: LimitesHora = {}): EvaluacionCampo {
  if (texto.trim() === "") return { estado: "vacio", valor: "", mensaje: "" };
  const lectura = analizarHora(texto);
  if (!lectura.ok) {
    return { estado: lectura.incompleta ? "incompleto" : "error", valor: "", mensaje: lectura.mensaje };
  }
  if (limites.minima && lectura.valor < limites.minima) {
    return { estado: "error", valor: "", mensaje: limites.motivoMinima ?? `La hora no puede ser anterior a las ${limites.minima}.` };
  }
  if (limites.maxima && lectura.valor > limites.maxima) {
    return { estado: "error", valor: "", mensaje: limites.motivoMaxima ?? `La hora no puede ser posterior a las ${limites.maxima}.` };
  }
  return { estado: "ok", valor: lectura.valor, mensaje: "" };
}

// ------------------------------------------------------------ Fecha con hora

/** `AAAA-MM-DD` + `HH:MM` → `AAAA-MM-DDTHH:MM` (el mismo formato que antes enviaba `datetime-local`). */
export function unirFechaHora(fecha: string, hora: string): string {
  return fecha && hora ? `${fecha}T${hora}` : "";
}

export function separarFechaHora(valor: string | null | undefined): { fecha: string; hora: string } {
  const m = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/.exec(valor ?? "");
  return m ? { fecha: m[1], hora: m[2] } : { fecha: "", hora: "" };
}

// ------------------------------------------------------------ Atajos

export type AtajoFecha = "hoy" | "ayer" | "manana" | "en7dias" | "finDeMes" | "sinFecha";

export const TEXTO_ATAJO: Record<AtajoFecha, string> = {
  hoy: "Hoy",
  ayer: "Ayer",
  manana: "Mañana",
  en7dias: "En 7 días",
  finDeMes: "Fin de mes",
  sinFecha: "Sin fecha",
};

/** Fecha a la que lleva el atajo (`""` para «Sin fecha»). */
export function resolverAtajo(atajo: AtajoFecha, hoy: string): string {
  switch (atajo) {
    case "hoy":
      return hoy;
    case "ayer":
      return sumarDiasISO(hoy, -1);
    case "manana":
      return sumarDiasISO(hoy, 1);
    case "en7dias":
      return sumarDiasISO(hoy, 7);
    case "finDeMes":
      return finDeMesISO(hoy);
    case "sinFecha":
      return "";
  }
}

// ------------------------------------------------------------ Horas del selector

export const HORAS = Array.from({ length: 24 }, (_, i) => pad(i));
export const MINUTOS_PASO_5 = Array.from({ length: 12 }, (_, i) => pad(i * 5));

/** Minutos de la columna: de a 5 y, si la hora escrita tiene otro minuto, también ese. */
export function minutosDeColumna(actual: string): string[] {
  if (!/^\d{2}$/.test(actual) || MINUTOS_PASO_5.includes(actual)) return MINUTOS_PASO_5;
  return [...MINUTOS_PASO_5, actual].sort();
}

export function horaPermitida(hora: string, minima?: string, maxima?: string): boolean {
  if (minima && hora < minima.slice(0, 2)) return false;
  if (maxima && hora > maxima.slice(0, 2)) return false;
  return true;
}

export function minutoPermitido(hora: string, minuto: string, minima?: string, maxima?: string): boolean {
  const valor = `${hora}:${minuto}`;
  if (minima && valor < minima) return false;
  if (maxima && valor > maxima) return false;
  return true;
}
