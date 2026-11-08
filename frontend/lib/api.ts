// Cliente de la API: siempre mismo origen (`/api/...`), con cookie de sesión y CSRF.

export class ErrorApi extends Error {
  estado: number;
  /** Mensaje general (`{"detalle": ...}`). */
  detalle: string | null;
  /** Errores por campo, ya aplanados (`{"campo": ["mensaje"]}` de DRF, incluso anidados). */
  campos: { ruta: string; mensaje: string }[];

  constructor(estado: number, detalle: string | null, campos: { ruta: string; mensaje: string }[]) {
    super(detalle ?? campos[0]?.mensaje ?? "Ocurrió un error.");
    this.estado = estado;
    this.detalle = detalle;
    this.campos = campos;
  }
}

function leerCookie(nombre: string): string | null {
  if (typeof document === "undefined") return null;
  const partes = document.cookie ? document.cookie.split("; ") : [];
  for (const parte of partes) {
    const indice = parte.indexOf("=");
    if (indice === -1) continue;
    if (parte.slice(0, indice) === nombre) return decodeURIComponent(parte.slice(indice + 1));
  }
  return null;
}

/** Garantiza la cookie `csrftoken` pidiendo la sesión una sola vez cuando falta. */
async function obtenerCsrf(): Promise<string> {
  let token = leerCookie("csrftoken");
  if (!token) {
    await fetch("/api/auth/sesion", { credentials: "same-origin" });
    token = leerCookie("csrftoken");
  }
  return token ?? "";
}

function aplanar(valor: unknown, ruta: string, salida: { ruta: string; mensaje: string }[]) {
  if (valor == null) return;
  if (typeof valor === "string") {
    salida.push({ ruta, mensaje: valor });
  } else if (Array.isArray(valor)) {
    valor.forEach((elemento, indice) => {
      if (typeof elemento === "string") salida.push({ ruta, mensaje: elemento });
      else aplanar(elemento, ruta ? `${ruta}.${indice}` : String(indice), salida);
    });
  } else if (typeof valor === "object") {
    for (const [clave, interior] of Object.entries(valor as Record<string, unknown>)) {
      aplanar(interior, ruta ? `${ruta}.${clave}` : clave, salida);
    }
  }
}

function construirError(estado: number, cuerpo: unknown): ErrorApi {
  let detalle: string | null = null;
  const campos: { ruta: string; mensaje: string }[] = [];
  if (cuerpo && typeof cuerpo === "object" && !Array.isArray(cuerpo)) {
    const objeto = cuerpo as Record<string, unknown>;
    if (typeof objeto.detalle === "string") detalle = objeto.detalle;
    else if (typeof objeto.detail === "string") detalle = objeto.detail;
    for (const [clave, valor] of Object.entries(objeto)) {
      if (clave === "detalle" || clave === "detail") continue;
      aplanar(valor, clave, campos);
    }
  } else if (Array.isArray(cuerpo)) {
    aplanar(cuerpo, "", campos);
  }
  if (!detalle && campos.length === 0) {
    detalle =
      estado === 404
        ? "No se encontró lo que buscabas."
        : estado === 403
          ? "No tenés permiso para hacer esto."
          : estado >= 500
            ? "El servidor tuvo un problema. Probá de nuevo en unos minutos."
            : "No se pudo completar la solicitud.";
  }
  return new ErrorApi(estado, detalle, campos);
}

export const EVENTO_VERIFICAR_SESION = "sigs:verificar-sesion";

interface OpcionesApi {
  metodo?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  cuerpo?: unknown;
  formulario?: FormData;
}

export async function api<T = unknown>(ruta: string, opciones: OpcionesApi = {}): Promise<T> {
  const metodo = opciones.metodo ?? (opciones.cuerpo !== undefined || opciones.formulario ? "POST" : "GET");
  const cabeceras: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;

  if (opciones.formulario) {
    body = opciones.formulario;
  } else if (opciones.cuerpo !== undefined) {
    cabeceras["Content-Type"] = "application/json";
    body = JSON.stringify(opciones.cuerpo);
  }
  if (metodo !== "GET") cabeceras["X-CSRFToken"] = await obtenerCsrf();

  let respuesta: Response;
  try {
    respuesta = await fetch(`/api${ruta}`, { method: metodo, credentials: "same-origin", headers: cabeceras, body });
  } catch {
    throw new ErrorApi(0, "No se pudo conectar con el servidor. Revisá tu conexión.", []);
  }

  if (respuesta.status === 204) return undefined as T;

  let datos: unknown = null;
  const texto = await respuesta.text();
  if (texto) {
    try {
      datos = JSON.parse(texto);
    } catch {
      datos = null;
    }
  }

  if (!respuesta.ok) {
    if ((respuesta.status === 401 || respuesta.status === 403) && typeof window !== "undefined") {
      window.dispatchEvent(new Event(EVENTO_VERIFICAR_SESION));
    }
    throw construirError(respuesta.status, datos);
  }
  return datos as T;
}

/** Mensaje único en español para mostrar al lado de un formulario. */
export function mensajeDeError(error: unknown): string {
  if (error instanceof ErrorApi) return error.message;
  return "Ocurrió un error inesperado.";
}

/** Errores de un campo concreto (coincide con la ruta o con su prefijo). */
export function erroresDeCampo(error: unknown, campo: string): string[] {
  if (!(error instanceof ErrorApi)) return [];
  return error.campos
    .filter((c) => c.ruta === campo || c.ruta.startsWith(`${campo}.`))
    .map((c) => c.mensaje);
}

/** Algunos listados pueden venir como arreglo o como `{resultados: [...]}`. */
export function comoLista<T>(datos: unknown): T[] {
  if (Array.isArray(datos)) return datos as T[];
  if (datos && typeof datos === "object" && Array.isArray((datos as { resultados?: unknown }).resultados)) {
    return (datos as { resultados: T[] }).resultados;
  }
  return [];
}
