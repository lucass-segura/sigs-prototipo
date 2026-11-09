// Asistente de «Registrar siniestro» (S33): pasos, estado del formulario, cuerpo que se envía a la API,
// qué paso es dueño de cada error, requisitos para confirmar y lo que se guarda en sessionStorage.
// Sin dependencias de React ni de otros módulos de lib/ (solo tipos) para poder probarlo con `node --test`.
import type { BienSiniestro, CuerpoSiniestro, PersonaSiniestro, RolPersona, TipoBien, TipoIdentificador } from "./tipos";

// ------------------------------------------------------------------ Pasos

export type IdPaso = "poliza" | "hecho" | "personas" | "bienes" | "revision";

export interface DefinicionPaso {
  id: IdPaso;
  nombre: string;
}

export const PASOS: readonly DefinicionPaso[] = [
  { id: "poliza", nombre: "Póliza" },
  { id: "hecho", nombre: "Hecho y denuncia" },
  { id: "personas", nombre: "Personas" },
  { id: "bienes", nombre: "Bienes" },
  { id: "revision", nombre: "Revisar y confirmar" },
];

export const indiceDePaso = (id: IdPaso): number => PASOS.findIndex((p) => p.id === id);

export const nombreDePaso = (id: IdPaso): string => PASOS[indiceDePaso(id)].nombre;

/** `Paso 2 de 5 · Hecho y denuncia` (el indicador compacto del teléfono). */
export function textoCompactoDePaso(id: IdPaso): string {
  return `Paso ${indiceDePaso(id) + 1} de ${PASOS.length} · ${nombreDePaso(id)}`;
}

export interface EstadoDePaso {
  actual: boolean;
  /** Ya se pasó por el paso y no tiene nada para corregir. */
  completo: boolean;
  error: boolean;
}

export function estadoDePaso(id: IdPaso, actual: IdPaso, visitados: readonly IdPaso[], conError: ReadonlySet<IdPaso>): EstadoDePaso {
  const error = conError.has(id);
  return {
    actual: id === actual,
    error,
    completo: id !== "revision" && id !== actual && !error && visitados.includes(id),
  };
}

// ------------------------------------------------------------------ Estado del formulario

export interface FilaPersona {
  clave: number;
  tipo_identificador: TipoIdentificador;
  identificador: string;
  nombre: string;
  roles: RolPersona[];
}

export interface FilaBien {
  clave: number;
  tipo: TipoBien;
  identificador: string;
  descripcion: string;
  detalle_dano: string;
  motor: string;
  chasis: string;
}

/** Todo lo que se carga en el asistente. Vive en un solo lugar, por encima de los pasos. */
export interface DatosSiniestro {
  compania: string;
  numeroPoliza: string;
  cobertura: string;
  inicioVigencia: string;
  primerPago: string;
  tipo: string;
  fechaHecho: string;
  horaHecho: string;
  fechaDenuncia: string;
  horaDenuncia: string;
  numeroDenuncia: string;
  asesor: string;
  intervenciones: string;
  documentacionAdjunta: string;
  lugar: string;
  relato: string;
  personas: FilaPersona[];
  bienes: FilaBien[];
}

export type CampoTexto = {
  [K in keyof DatosSiniestro]: DatosSiniestro[K] extends string ? K : never;
}[keyof DatosSiniestro];

const TIPOS_IDENTIFICADOR_VALIDOS: readonly string[] = ["DNI", "CUIT", "PASAPORTE"];
const ROLES_VALIDOS: readonly string[] = ["asegurado", "conductor", "tercero", "testigo"];
const TIPOS_BIEN_VALIDOS: readonly string[] = ["vehiculo", "motocicleta", "telefono", "computadora", "otro"];

let contadorClaves = 0;
/** Identifica cada fila para que React la siga aunque se quiten otras. */
export const nuevaClave = (): number => ++contadorClaves;

export const personaVacia = (): FilaPersona => ({
  clave: nuevaClave(),
  tipo_identificador: "DNI",
  identificador: "",
  nombre: "",
  roles: [],
});

export const bienVacio = (): FilaBien => ({
  clave: nuevaClave(),
  tipo: "vehiculo",
  identificador: "",
  descripcion: "",
  detalle_dano: "",
  motor: "",
  chasis: "",
});

export const tieneAtributosDeVehiculo = (tipo: TipoBien): boolean => tipo === "vehiculo" || tipo === "motocicleta";

export function datosIniciales(): DatosSiniestro {
  return {
    compania: "",
    numeroPoliza: "",
    cobertura: "",
    inicioVigencia: "",
    primerPago: "",
    tipo: "",
    fechaHecho: "",
    horaHecho: "",
    fechaDenuncia: "",
    horaDenuncia: "",
    numeroDenuncia: "",
    asesor: "",
    intervenciones: "",
    documentacionAdjunta: "",
    lugar: "",
    relato: "",
    personas: [personaVacia()],
    bienes: [bienVacio()],
  };
}

export type Accion =
  | { tipo: "campo"; campo: CampoTexto; valor: string }
  | { tipo: "persona/agregar"; clave: number }
  | { tipo: "persona/actualizar"; clave: number; cambios: Partial<FilaPersona> }
  | { tipo: "persona/alternarRol"; clave: number; rol: RolPersona }
  | { tipo: "persona/quitar"; clave: number }
  | { tipo: "bien/agregar"; clave: number }
  | { tipo: "bien/actualizar"; clave: number; cambios: Partial<FilaBien> }
  | { tipo: "bien/quitar"; clave: number }
  | { tipo: "reemplazar"; datos: DatosSiniestro };

export function reducirDatos(datos: DatosSiniestro, accion: Accion): DatosSiniestro {
  switch (accion.tipo) {
    case "campo":
      return datos[accion.campo] === accion.valor ? datos : { ...datos, [accion.campo]: accion.valor };
    case "persona/agregar":
      return { ...datos, personas: [...datos.personas, { ...personaVacia(), clave: accion.clave }] };
    case "persona/actualizar":
      return { ...datos, personas: datos.personas.map((f) => (f.clave === accion.clave ? { ...f, ...accion.cambios } : f)) };
    case "persona/alternarRol":
      return {
        ...datos,
        personas: datos.personas.map((f) =>
          f.clave === accion.clave
            ? { ...f, roles: f.roles.includes(accion.rol) ? f.roles.filter((r) => r !== accion.rol) : [...f.roles, accion.rol] }
            : f,
        ),
      };
    case "persona/quitar":
      return { ...datos, personas: datos.personas.filter((f) => f.clave !== accion.clave) };
    case "bien/agregar":
      return { ...datos, bienes: [...datos.bienes, { ...bienVacio(), clave: accion.clave }] };
    case "bien/actualizar":
      return { ...datos, bienes: datos.bienes.map((f) => (f.clave === accion.clave ? { ...f, ...accion.cambios } : f)) };
    case "bien/quitar":
      return { ...datos, bienes: datos.bienes.filter((f) => f.clave !== accion.clave) };
    case "reemplazar":
      return accion.datos;
  }
}

// ------------------------------------------------------------------ Cuerpo para la API

/** Las filas que se envían: las que tienen algún dato (una fila en blanco se ignora). */
export const personasEnviables = (personas: readonly FilaPersona[]): FilaPersona[] =>
  personas.filter((p) => p.identificador.trim() || p.nombre.trim() || p.roles.length);

export const bienesEnviables = (bienes: readonly FilaBien[]): FilaBien[] =>
  bienes.filter((b) => b.identificador.trim() || b.descripcion.trim() || b.detalle_dano.trim());

/** Lugar que ocupa la fila en lo que se envía (el índice de los errores `personas.N.…`), o null si no se envía. */
export function indiceEnviado<T extends { clave: number }>(enviables: readonly T[], clave: number): number | null {
  const i = enviables.findIndex((f) => f.clave === clave);
  return i === -1 ? null : i;
}

/** Cuerpo de POST y PATCH /api/siniestros. No cambia respecto del formulario de una sola página. */
export function armarCuerpo(d: DatosSiniestro): CuerpoSiniestro {
  const personasEnviadas: PersonaSiniestro[] = personasEnviables(d.personas).map((p) => ({
    tipo_identificador: p.tipo_identificador,
    identificador: p.identificador.trim(),
    nombre: p.nombre.trim(),
    roles: p.roles,
  }));
  const bienesEnviados: BienSiniestro[] = bienesEnviables(d.bienes).map((b) => {
    const atributos: Record<string, string> = {};
    if (tieneAtributosDeVehiculo(b.tipo)) {
      if (b.motor.trim()) atributos.motor = b.motor.trim();
      if (b.chasis.trim()) atributos.chasis = b.chasis.trim();
    }
    return {
      tipo: b.tipo,
      identificador: b.identificador.trim(),
      descripcion: b.descripcion.trim(),
      detalle_dano: b.detalle_dano.trim(),
      atributos,
    };
  });
  return {
    poliza: {
      numero: d.numeroPoliza.trim(),
      compania: d.compania.trim(),
      cobertura: d.cobertura.trim(),
      inicio_vigencia: d.inicioVigencia || null,
      primer_pago: d.primerPago || null,
    },
    tipo: d.tipo.trim(),
    // Igual que `unirFechaHora` de lib/fechas: AAAA-MM-DDTHH:MM, y se omite si falta la fecha o la hora.
    ...(d.fechaHecho && d.horaHecho ? { fecha_hecho: `${d.fechaHecho}T${d.horaHecho}` } : {}),
    fecha_denuncia: d.fechaDenuncia || null,
    hora_denuncia: d.horaDenuncia || null,
    numero_denuncia: d.numeroDenuncia.trim(),
    asesor: d.asesor.trim(),
    intervenciones: d.intervenciones.trim(),
    documentacion_adjunta: d.documentacionAdjunta.trim(),
    lugar: d.lugar.trim(),
    relato: d.relato.trim(),
    personas: personasEnviadas,
    bienes: bienesEnviados,
  };
}

// ------------------------------------------------------------------ Errores de la API → paso

const CAMPOS_DEL_HECHO: readonly string[] = [
  "tipo",
  "fecha_hecho",
  "fecha_denuncia",
  "hora_denuncia",
  "numero_denuncia",
  "asesor",
  "intervenciones",
  "documentacion_adjunta",
  "lugar",
  "relato",
];

/** Paso dueño de un campo de la API (`poliza.numero`, `personas.0.identificador`, `fecha_hecho`…); null si no es de ninguno. */
export function pasoDeRuta(ruta: string): IdPaso | null {
  const raiz = ruta.split(".")[0];
  if (raiz === "poliza") return "poliza";
  if (raiz === "personas") return "personas";
  if (raiz === "bienes") return "bienes";
  return CAMPOS_DEL_HECHO.includes(raiz) ? "hecho" : null;
}

/** Pasos que tienen errores, en el orden del asistente. */
export function pasosConError(rutas: readonly string[]): IdPaso[] {
  const duenos = new Set<IdPaso>();
  for (const ruta of rutas) {
    const paso = pasoDeRuta(ruta);
    if (paso) duenos.add(paso);
  }
  return PASOS.map((p) => p.id).filter((id) => duenos.has(id));
}

/** Primer paso (en el orden del asistente) con errores de campo, o null. */
export const primerPasoConError = (rutas: readonly string[]): IdPaso | null => pasosConError(rutas)[0] ?? null;

const IDS_DE_CAMPO: Record<string, string> = {
  "poliza.compania": "compania",
  "poliza.numero": "numero-poliza",
  "poliza.cobertura": "cobertura",
  "poliza.inicio_vigencia": "inicio-vigencia",
  "poliza.primer_pago": "primer-pago",
  tipo: "tipo",
  fecha_hecho: "fecha-hecho",
  fecha_denuncia: "fecha-denuncia",
  hora_denuncia: "hora-denuncia",
  numero_denuncia: "numero-denuncia",
  asesor: "asesor",
  intervenciones: "intervenciones",
  documentacion_adjunta: "documentacion-adjunta",
  lugar: "lugar",
  relato: "relato",
};

const PREFIJOS_PERSONA: Record<string, string> = {
  identificador: "p-id",
  nombre: "p-nombre",
  tipo_identificador: "p-tipo",
  roles: "p-roles",
};

const PREFIJOS_BIEN: Record<string, string> = {
  identificador: "b-id",
  descripcion: "b-desc",
  detalle_dano: "b-dano",
  tipo: "b-tipo",
};

/** Id del control de la pantalla que corresponde a un campo de la API, para llevarle el foco. */
export function idControlDeRuta(ruta: string, d: DatosSiniestro): string | null {
  if (IDS_DE_CAMPO[ruta]) return IDS_DE_CAMPO[ruta];
  const m = /^(personas|bienes)\.(\d+)\.(\w+)/.exec(ruta);
  if (!m) return null;
  const indice = Number(m[2]);
  if (m[1] === "personas") {
    const fila = personasEnviables(d.personas)[indice];
    const prefijo = PREFIJOS_PERSONA[m[3]];
    return fila && prefijo ? `${prefijo}-${fila.clave}` : null;
  }
  const fila = bienesEnviables(d.bienes)[indice];
  const prefijo = PREFIJOS_BIEN[m[3]];
  return fila && prefijo ? `${prefijo}-${fila.clave}` : null;
}

// ------------------------------------------------------------------ Validación suave por paso

/** Mensajes por id de control. Se muestran al pasar de paso, pero no impiden avanzar (los mismos que da la API). */
export function validarPaso(d: DatosSiniestro, paso: IdPaso): Record<string, string> {
  const mensajes: Record<string, string> = {};
  if (paso === "personas") {
    for (const p of personasEnviables(d.personas)) {
      if (!p.identificador.trim()) mensajes[`p-id-${p.clave}`] = "El identificador de la persona es obligatorio.";
      if (p.roles.length === 0) mensajes[`p-roles-${p.clave}`] = "Indicá al menos un rol para la persona.";
    }
  }
  if (paso === "bienes") {
    for (const b of bienesEnviables(d.bienes)) {
      if (!b.identificador.trim()) mensajes[`b-id-${b.clave}`] = "El identificador del bien es obligatorio.";
    }
  }
  return mensajes;
}

/** Pasos que tienen mensajes de validación suave. */
export function pasosConAvisos(d: DatosSiniestro): IdPaso[] {
  return PASOS.map((p) => p.id).filter((id) => Object.keys(validarPaso(d, id)).length > 0);
}

// ------------------------------------------------------------------ Qué hace falta para confirmar

export interface Requisito {
  id: "poliza" | "fecha-hecho" | "vinculo";
  texto: string;
  cumplido: boolean;
  /** Pasos donde se resuelve. */
  pasos: IdPaso[];
}

/** Para confirmar no alcanza con cargar otros datos de la póliza: hace falta el número (S34). */
export const numeroDePolizaCargado = (d: DatosSiniestro): boolean => d.numeroPoliza.trim() !== "";

/** La misma regla del backend: número de póliza, fecha del hecho y al menos una persona o un bien. */
export function requisitosParaConfirmar(d: DatosSiniestro): Requisito[] {
  return [
    { id: "poliza", texto: "Póliza: cargá el número de póliza.", cumplido: numeroDePolizaCargado(d), pasos: ["poliza"] },
    { id: "fecha-hecho", texto: "Fecha y hora del hecho.", cumplido: d.fechaHecho !== "" && d.horaHecho !== "", pasos: ["hecho"] },
    {
      id: "vinculo",
      texto: "Al menos una persona o un bien.",
      cumplido: personasEnviables(d.personas).length > 0 || bienesEnviables(d.bienes).length > 0,
      pasos: ["personas", "bienes"],
    },
  ];
}

// ------------------------------------------------------------------ sessionStorage

/** Todas las claves del asistente empiezan así (para borrarlas juntas al salir). */
export const PREFIJO_ALMACEN = "sigs:siniestro:";

/** Una entrada por usuario y por borrador (o «nuevo»). */
export const claveAlmacen = (usuarioId: number, idBorrador: number | null): string =>
  `${PREFIJO_ALMACEN}${usuarioId}:${idBorrador ?? "nuevo"}`;

export interface Guardado {
  datos: DatosSiniestro;
  paso: IdPaso;
  visitados: IdPaso[];
}

const VERSION_ALMACEN = 1;

export function serializar(g: Guardado): string {
  return JSON.stringify({ version: VERSION_ALMACEN, paso: g.paso, visitados: g.visitados, datos: g.datos });
}

const texto = (v: unknown): string => (typeof v === "string" ? v : "");
const esObjeto = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);
const esPaso = (v: unknown): v is IdPaso => PASOS.some((p) => p.id === v);

/** Lee lo guardado con cuidado: lo que no tiene la forma esperada se descarta (null) o se completa con vacíos. */
export function deserializar(crudo: string | null): Guardado | null {
  if (!crudo) return null;
  let bruto: unknown;
  try {
    bruto = JSON.parse(crudo);
  } catch {
    return null;
  }
  if (!esObjeto(bruto) || bruto.version !== VERSION_ALMACEN || !esObjeto(bruto.datos)) return null;
  const d = bruto.datos;
  const base = datosIniciales();
  const personas = Array.isArray(d.personas)
    ? d.personas.filter(esObjeto).map<FilaPersona>((p) => ({
        clave: nuevaClave(),
        tipo_identificador: TIPOS_IDENTIFICADOR_VALIDOS.includes(texto(p.tipo_identificador)) ? (p.tipo_identificador as TipoIdentificador) : "DNI",
        identificador: texto(p.identificador),
        nombre: texto(p.nombre),
        roles: Array.isArray(p.roles) ? (p.roles.filter((r) => ROLES_VALIDOS.includes(texto(r))) as RolPersona[]) : [],
      }))
    : base.personas;
  const bienes = Array.isArray(d.bienes)
    ? d.bienes.filter(esObjeto).map<FilaBien>((b) => ({
        clave: nuevaClave(),
        tipo: TIPOS_BIEN_VALIDOS.includes(texto(b.tipo)) ? (b.tipo as TipoBien) : "vehiculo",
        identificador: texto(b.identificador),
        descripcion: texto(b.descripcion),
        detalle_dano: texto(b.detalle_dano),
        motor: texto(b.motor),
        chasis: texto(b.chasis),
      }))
    : base.bienes;
  const datos: DatosSiniestro = {
    compania: texto(d.compania),
    numeroPoliza: texto(d.numeroPoliza),
    cobertura: texto(d.cobertura),
    inicioVigencia: texto(d.inicioVigencia),
    primerPago: texto(d.primerPago),
    tipo: texto(d.tipo),
    fechaHecho: texto(d.fechaHecho),
    horaHecho: texto(d.horaHecho),
    fechaDenuncia: texto(d.fechaDenuncia),
    horaDenuncia: texto(d.horaDenuncia),
    numeroDenuncia: texto(d.numeroDenuncia),
    asesor: texto(d.asesor),
    intervenciones: texto(d.intervenciones),
    documentacionAdjunta: texto(d.documentacionAdjunta),
    lugar: texto(d.lugar),
    relato: texto(d.relato),
    personas,
    bienes,
  };
  return {
    datos,
    paso: esPaso(bruto.paso) ? bruto.paso : "poliza",
    visitados: Array.isArray(bruto.visitados) ? bruto.visitados.filter(esPaso) : [],
  };
}

type Almacen = Pick<Storage, "length" | "key" | "removeItem">;

/** Borra lo guardado de todos los borradores (al cerrar la sesión). */
export function borrarGuardados(almacen: Almacen): void {
  const claves: string[] = [];
  for (let i = 0; i < almacen.length; i++) {
    const clave = almacen.key(i);
    if (clave?.startsWith(PREFIJO_ALMACEN)) claves.push(clave);
  }
  for (const clave of claves) almacen.removeItem(clave);
}
