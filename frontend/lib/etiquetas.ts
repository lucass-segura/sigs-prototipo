// Textos en español de los valores que devuelve la API.
import type {
  EstadoSiniestro,
  EstadoTarea,
  Prioridad,
  ResultadoReclamo,
  Rol,
  RolPersona,
  TipoBien,
  TipoIdentificador,
} from "./tipos";

export const ETIQUETA_ESTADO: Record<EstadoSiniestro, string> = {
  borrador: "Borrador",
  en_analisis: "En análisis",
  cerrado: "Cerrado",
  archivado: "Archivado",
  anulado: "Anulado",
};

export const ETIQUETA_PRIORIDAD: Record<Prioridad, string> = {
  alta: "Alta",
  media: "Media",
  baja: "Baja",
};

export const ETIQUETA_ESTADO_TAREA: Record<EstadoTarea, string> = {
  pendiente: "Pendiente",
  en_curso: "En curso",
  hecha: "Hecho",
};

export const ESTADOS_TAREA: EstadoTarea[] = ["pendiente", "en_curso", "hecha"];

export const ETIQUETA_RESULTADO: Record<ResultadoReclamo, string> = {
  aprobado: "Aprobado",
  rechazado: "Rechazado",
  desistido: "Desistido",
  otra_finalizacion: "Otra finalización",
};

export const ETIQUETA_ROL: Record<Rol, string> = {
  perito: "Perito",
  administrador: "Administrador",
  superadministrador: "Superadministrador",
};

export const ROLES_PERSONA: RolPersona[] = ["asegurado", "conductor", "tercero", "testigo"];

export const ETIQUETA_ROL_PERSONA: Record<RolPersona, string> = {
  asegurado: "Asegurado",
  conductor: "Conductor",
  tercero: "Tercero",
  testigo: "Testigo",
};

export const TIPOS_IDENTIFICADOR: TipoIdentificador[] = ["DNI", "CUIT", "PASAPORTE"];

export const TIPOS_BIEN: TipoBien[] = ["vehiculo", "motocicleta", "telefono", "computadora", "otro"];

export const ETIQUETA_TIPO_BIEN: Record<TipoBien, string> = {
  vehiculo: "Vehículo",
  motocicleta: "Motocicleta",
  telefono: "Teléfono",
  computadora: "Computadora",
  otro: "Otro",
};

export const TIPOS_SINIESTRO_SUGERIDOS = [
  "Incendio total",
  "Choque en calle",
  "Robo parcial de vehículo",
  "Robo de rueda de auxilio",
  "Robo de celular",
  "Robo de notebook",
  "Robo en comercio",
  "Daño por granizo",
];

export const TIPOS_DOCUMENTO_SUGERIDOS = [
  "Fotografía",
  "Acta policial",
  "Informe pericial",
  "Cédula del vehículo",
  "Denuncia",
  "Otro",
];

/** Escala de valoración (tabla 2 del TFG). */
export const ESCALA_VALORACION: { desde: number; hasta: number; texto: string }[] = [
  { desde: 1, hasta: 2, texto: "No verificado, con elementos que lo contradicen" },
  { desde: 3, hasta: 4, texto: "Inconsistencias relevantes" },
  { desde: 5, hasta: 6, texto: "Dudas concretas" },
  { desde: 7, hasta: 8, texto: "Verificado con observaciones menores" },
  { desde: 9, hasta: 10, texto: "Verificado sin observaciones" },
];

export function textoValoracion(n: number): string {
  return ESCALA_VALORACION.find((e) => n >= e.desde && n <= e.hasta)?.texto ?? "";
}

export const ETIQUETA_MOTIVO_EVALUACION: Record<string, string> = {
  confirmacion: "confirmación del siniestro",
  recalculo: "recálculo del perito",
  antecedente_confirmado: "nuevo antecedente confirmado",
  escenario: "escenario de prueba",
};

/** Texto del bien principal para la cabecera: «Vehículo AB123CD». */
export function textoBienPrincipal(bien: { tipo: TipoBien; identificador_norm?: string; identificador?: string } | undefined): string | null {
  if (!bien) return null;
  const id = bien.identificador_norm ?? bien.identificador ?? "";
  return `${ETIQUETA_TIPO_BIEN[bien.tipo] ?? "Bien"} ${id}`.trim();
}
