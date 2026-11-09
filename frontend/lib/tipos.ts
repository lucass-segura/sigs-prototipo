// Tipos de las respuestas de la API (docs/DISENO.md, secciones 5 y 6).

export type Rol = "perito" | "administrador" | "superadministrador";

export type EstadoSiniestro =
  | "borrador"
  | "en_analisis"
  | "cerrado"
  | "archivado"
  | "anulado";

export type Prioridad = "baja" | "media" | "alta";

export type EstadoTarea = "pendiente" | "en_curso" | "hecha";

export type EstadoSenal = "activada" | "no_activada" | "no_evaluable";

export type ResultadoReclamo =
  | "aprobado"
  | "rechazado"
  | "desistido"
  | "otra_finalizacion";

export type TipoIdentificador = "DNI" | "CUIT" | "PASAPORTE";

export type RolPersona = "asegurado" | "conductor" | "tercero" | "testigo";

export type TipoBien =
  | "vehiculo"
  | "motocicleta"
  | "telefono"
  | "computadora"
  | "otro";

export interface Espacio {
  id: number;
  nombre: string;
}

export interface Usuario {
  id: number;
  nombre: string;
  email: string;
  rol: Rol;
  espacio: Espacio | null;
  activo: boolean;
  contacto_email: string;
  contacto_visible: boolean;
}

export interface RespuestaSesion {
  autenticado: boolean;
  usuario: Usuario | null;
}

export interface Perfil {
  contacto_email: string;
  contacto_visible: boolean;
}

// ---------------------------------------------------------------- Expedientes

export interface ItemPanel {
  id: number;
  numero_expediente: string;
  tipo: string;
  fecha_hecho: string;
  estado: EstadoSiniestro;
  bien_principal: string | null;
  prioridad: Prioridad | null;
  puntaje: number | null;
  tareas_pendientes: number;
}

export interface ResumenPanel {
  en_analisis: number;
  prioridad_alta: number;
  tareas_vencen_semana: number;
  cerrados_mes: number;
}

export interface RespuestaPanel {
  resultados: ItemPanel[];
  resumen: ResumenPanel;
}

export interface Poliza {
  numero: string;
  compania: string;
  cobertura: string;
  inicio_vigencia: string | null;
  primer_pago: string | null;
}

export interface PersonaSiniestro {
  id?: number;
  tipo_identificador: TipoIdentificador;
  identificador: string;
  nombre: string;
  roles: RolPersona[];
}

export interface AtributosBien {
  motor?: string;
  chasis?: string;
  [clave: string]: unknown;
}

export interface BienSiniestro {
  id?: number;
  tipo: TipoBien;
  identificador_norm?: string;
  identificador?: string;
  descripcion: string;
  atributos?: AtributosBien | null;
  detalle_dano: string;
}

export interface Cierre {
  id: number;
  resultado_reclamo: ResultadoReclamo;
  irregularidad: boolean;
  conclusion: string;
  valoracion: number;
  valoracion_texto: string;
  justificacion: string;
  motivo_cambio: string;
  /** Respaldo de la irregularidad: solo lo ve el perito responsable, nunca el resumen de otros peritos. */
  documentos_respaldo: { id: number; tipo: string; nombre_original: string }[];
  observacion_respaldo: string;
  creado_en: string;
  perito: { id: number; nombre: string };
}

export interface RespuestaCierre {
  vigente: Cierre | null;
  historial: Cierre[];
}

export interface Siniestro {
  id: number;
  numero_expediente: string;
  tipo: string;
  fecha_hecho: string;
  fecha_denuncia: string | null;
  lugar: string;
  relato: string;
  estado: EstadoSiniestro;
  confirmado_en: string | null;
  motivo_anulacion: string;
  espacio: Espacio;
  perito: { id: number; nombre: string };
  es_responsable: boolean;
  poliza: Poliza | null;
  personas: PersonaSiniestro[];
  bienes: BienSiniestro[];
  cierre_vigente: Cierre | null;
}

/** Cuerpo de POST y PATCH /api/siniestros. */
export interface CuerpoSiniestro {
  numero_expediente?: string;
  poliza: Poliza;
  tipo: string;
  /** Se omite cuando está vacía para que la API responda que es obligatoria. */
  fecha_hecho?: string;
  fecha_denuncia: string | null;
  lugar: string;
  relato: string;
  personas: PersonaSiniestro[];
  bienes: BienSiniestro[];
  confirmar?: boolean;
}

// ------------------------------------------------------------------- Análisis

export interface AntecedenteSenal {
  id: number;
  numero_expediente: string;
  fecha_hecho: string;
  vinculo: string;
}

export interface Senal {
  codigo: string;
  nombre: string;
  grupo: string;
  estado: EstadoSenal;
  puntos: number;
  puntos_max: number;
  texto: string;
  dato: Record<string, unknown> | null;
  antecedentes: AntecedenteSenal[];
}

export interface GrupoEvaluacion {
  bruto: number;
  tope: number;
  puntos: number;
}

export interface Evaluacion {
  id: number;
  version: string;
  creada_en: string;
  motivo: string;
  puntaje: number;
  prioridad: Prioridad;
  grupos: Record<string, GrupoEvaluacion>;
  senales: Senal[];
  entradas: unknown;
}

export interface ResumenEvaluacion {
  id: number;
  version: string;
  creada_en: string;
  motivo: string;
  puntaje: number;
  prioridad: Prioridad;
}

export interface VinculoCoincidencia {
  tipo: "persona" | "bien";
  etiqueta: string;
  rol_en_antecedente: string;
  rol_en_caso: string;
}

export interface Coincidencia {
  antecedente_id: number;
  numero_expediente: string;
  tipo: string;
  fecha_hecho: string;
  estado: EstadoSiniestro;
  resultado_reclamo: ResultadoReclamo | null;
  vinculos: VinculoCoincidencia[];
  descripcion_vinculo: string;
}

export interface RespuestaCoincidencias {
  resultados: Coincidencia[];
  total: number;
  pagina: number;
  paginas: number;
  promedio_valoracion: { promedio: number | null; cantidad: number };
  mensaje_vacio: string | null;
}

export interface ResumenAntecedente {
  numero_expediente: string;
  tipo: string;
  fecha_hecho: string;
  estado: EstadoSiniestro;
  estado_texto?: string;
  vinculos: { tipo: "persona" | "bien"; etiqueta: string; rol_en_antecedente: string }[];
  cerrado: boolean;
  resultado_reclamo: ResultadoReclamo | null;
  irregularidad: boolean | null;
  valoracion: number | null;
  valoracion_texto: string | null;
  justificacion: string | null;
  perito_responsable: { nombre: string };
  contacto_perito: { email: string } | null;
  origen: { id: number; numero_expediente: string };
  no_se_muestra: string;
}

// ------------------------------------------------------------ Seguimiento etc.

export interface CambioTarea {
  estado_anterior: EstadoTarea | null;
  estado_nuevo: EstadoTarea;
  fecha: string;
  usuario: { id: number; nombre: string } | string | null;
}

export interface Tarea {
  id: number;
  titulo: string;
  estado: EstadoTarea;
  vence_en: string | null;
  creada_en: string;
  cambios: CambioTarea[];
}

export interface TareaConExpediente extends Tarea {
  siniestro: { id: number; numero_expediente: string; tipo: string };
}

export interface Nota {
  id: number;
  texto: string;
  creada_en: string;
  autor: { id: number; nombre: string };
}

export interface Documento {
  id: number;
  tipo: string;
  nombre_original: string;
  estado: string;
  recibido_en: string;
  tamanio: number;
}

// --------------------------------------------------------------------- Reglas

export interface ReglaConjunto {
  codigo: string;
  nombre: string;
  grupo: string;
  parametros: Record<string, unknown>;
  puntos_max: number;
  umbral_texto: string;
}

export interface Topes {
  grupos: Record<string, number>;
  total: number;
  prioridad: { media: number; alta: number };
}

export interface ConjuntoReglas {
  id: number;
  version: string;
  vigente_desde: string;
  activo: boolean;
  topes: Topes;
  reglas: ReglaConjunto[];
}

export interface VersionReglas {
  id: number;
  version: string;
  vigente_desde: string;
  activo: boolean;
  creado_en: string;
}

export interface RespuestaReglas {
  vigente: ConjuntoReglas;
  versiones: VersionReglas[];
}

export interface CuerpoVersionReglas {
  version: string;
  vigente_desde: string;
  reglas: Record<string, { parametros?: Record<string, unknown>; puntos_max?: number }>;
  topes: Topes;
}

// -------------------------------------------------------------- Administración

export interface UsuarioAdministrado extends Usuario {
  bloqueado_en: string | null;
  intentos_fallidos: number;
}

export interface EspacioAdministrado {
  id: number;
  nombre: string;
  creado_en?: string;
  cantidad_usuarios?: number;
  usuarios?: number;
}

export interface RegistroAuditoria {
  id: number;
  fecha: string;
  usuario: { id: number; nombre: string; email: string } | null;
  accion: string;
  objeto: string;
  resultado: "permitido" | "rechazado";
  siniestro_origen: { id: number; numero_expediente: string } | null;
}

export interface RespuestaAuditoria {
  resultados: RegistroAuditoria[];
  total: number;
  pagina: number;
  paginas: number;
  acciones: string[];
}
