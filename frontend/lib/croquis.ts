// Escena del croquis: lo que guarda el servidor (`documento.escena`) y con lo que el editor vuelve a dibujar.
// El formato lo valida el backend (`nucleo/croquis.py`): mantener juntos los dos lados.

export type TipoElemento =
  | "calle"
  | "cruce"
  | "curva"
  | "rotonda"
  | "vehiculo"
  | "moto"
  | "persona"
  | "flecha"
  | "impacto"
  | "texto"
  | "lapiz";

export interface Elemento {
  id: string;
  tipo: TipoElemento;
  x: number;
  y: number;
  rotacion?: number;
  escala?: number;
  etiqueta?: string;
  texto?: string;
  color?: string;
  /** Solo el lápiz: puntos relativos a (x, y). */
  puntos?: [number, number][];
}

export interface Escena {
  version: 1;
  ancho: number;
  alto: number;
  cuadricula: boolean;
  leyenda: boolean;
  norte: boolean;
  elementos: Elemento[];
}

export const ANCHO = 1200;
export const ALTO = 800;
export const PASO_CUADRICULA = 20;
export const MAX_ELEMENTOS = 500;
export const MAX_PUNTOS = 3000;

export const COLORES_VEHICULO: Record<string, string> = { A: "#2f6f62", B: "#3a5f9b", C: "#b9691f" };
export const COLOR_VEHICULO_OTRO = "#6b4a8f";
export const COLOR_TRAZO = "#1d2321";
export const COLORES_PALETA = ["#1d2321", "#9b2226", "#2f6f62", "#3a5f9b", "#b9691f", "#6b4a8f"];

export function escenaVacia(): Escena {
  return { version: 1, ancho: ANCHO, alto: ALTO, cuadricula: true, leyenda: true, norte: true, elementos: [] };
}

export const NOMBRE_TIPO: Record<TipoElemento, string> = {
  calle: "Calle recta",
  cruce: "Cruce",
  curva: "Curva",
  rotonda: "Rotonda",
  vehiculo: "Vehículo",
  moto: "Moto",
  persona: "Persona",
  flecha: "Flecha de sentido",
  impacto: "Punto de impacto",
  texto: "Texto",
  lapiz: "Trazo a mano alzada",
};

/** Medio ancho y medio alto del elemento sin escala, para dibujar la selección. */
export function mitadDeElemento(e: Elemento): { w: number; h: number } {
  switch (e.tipo) {
    case "calle":
      return { w: 200, h: 45 };
    case "cruce":
      return { w: 200, h: 200 };
    case "curva":
      return { w: 123, h: 100 };
    case "rotonda":
      return { w: 170, h: 170 };
    case "vehiculo":
      return { w: 42, h: 22 };
    case "moto":
      return { w: 28, h: 12 };
    case "persona":
      return { w: 14, h: 14 };
    case "flecha":
      return { w: 70, h: 16 };
    case "impacto":
      return { w: 26, h: 26 };
    case "texto":
      return { w: Math.max(24, ((e.texto ?? "").length * 13) / 2 + 6), h: 18 };
    case "lapiz": {
      const p = e.puntos ?? [[0, 0]];
      const w = Math.max(...p.map(([x]) => Math.abs(x))) + 6;
      const h = Math.max(...p.map(([, y]) => Math.abs(y))) + 6;
      return { w, h };
    }
  }
}

let contador = 0;
export function nuevoId(): string {
  contador += 1;
  return `e${Date.now().toString(36)}${contador.toString(36)}`;
}

/** Elemento nuevo en el centro de lo que se ve. */
export function nuevoElemento(tipo: TipoElemento, x: number, y: number, extra: Partial<Elemento> = {}): Elemento {
  const base: Elemento = { id: nuevoId(), tipo, x, y, rotacion: 0, escala: 1 };
  if (tipo === "vehiculo") {
    const etiqueta = extra.etiqueta ?? "A";
    base.etiqueta = etiqueta;
    base.color = COLORES_VEHICULO[etiqueta] ?? COLOR_VEHICULO_OTRO;
  }
  if (tipo === "moto") base.color = "#3b3f3d";
  if (tipo === "persona") base.color = "#c24d2c";
  if (tipo === "flecha") {
    base.color = COLOR_TRAZO;
    base.rotacion = 0;
  }
  if (tipo === "texto") {
    base.texto = "Texto";
    base.color = COLOR_TRAZO;
  }
  return { ...base, ...extra };
}

/** Lee una escena guardada: si no tiene el formato esperado devuelve `null`. */
export function leerEscena(dato: unknown): Escena | null {
  if (!dato || typeof dato !== "object") return null;
  const e = dato as Partial<Escena>;
  if (e.version !== 1 || !Array.isArray(e.elementos)) return null;
  return {
    version: 1,
    ancho: typeof e.ancho === "number" ? e.ancho : ANCHO,
    alto: typeof e.alto === "number" ? e.alto : ALTO,
    cuadricula: e.cuadricula !== false,
    leyenda: e.leyenda !== false,
    norte: e.norte !== false,
    elementos: e.elementos as Elemento[],
  };
}

export function tieneContenido(escena: Escena): boolean {
  return escena.elementos.length > 0;
}
