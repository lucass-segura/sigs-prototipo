import type { ReactNode } from "react";
import { ErrorApi, mensajeDeError } from "@/lib/api";

/** Errores de la API en español: el detalle general y, debajo, los errores de campo. */
export function ErrorFormulario({ error }: { error: unknown }) {
  if (!error) return null;
  const e = error instanceof ErrorApi ? error : null;
  return (
    <div className="aviso aviso-error" role="alert">
      {e && e.detalle ? <p>{e.detalle}</p> : null}
      {e && e.campos.length > 0 ? (
        <ul>
          {e.campos.map((c, i) => (
            <li key={`${c.ruta}-${i}`}>
              {etiquetaDeRuta(c.ruta)}
              {c.mensaje}
            </li>
          ))}
        </ul>
      ) : null}
      {!e ? <p>{mensajeDeError(error)}</p> : null}
    </div>
  );
}

const NOMBRES_CAMPO: Record<string, string> = {
  email: "Correo",
  password: "Contraseña",
  nombre: "Nombre",
  rol: "Rol",
  fecha_hecho: "Fecha del hecho",
  fecha_denuncia: "Fecha de denuncia",
  tipo: "Tipo",
  lugar: "Lugar",
  relato: "Relato",
  poliza: "Póliza",
  numero: "Número",
  compania: "Compañía",
  cobertura: "Cobertura",
  inicio_vigencia: "Inicio de vigencia",
  primer_pago: "Primer pago",
  personas: "Persona",
  bienes: "Bien",
  identificador: "Identificador",
  tipo_identificador: "Tipo de identificador",
  roles: "Roles",
  descripcion: "Descripción",
  detalle_dano: "Detalle del daño",
  atributos: "Atributos",
  valoracion: "Valoración",
  justificacion: "Justificación",
  conclusion: "Conclusión",
  respaldo: "Respaldo",
  documentos_respaldo: "Documentos de respaldo",
  observacion_respaldo: "Observación de respaldo",
  resultado_reclamo: "Resultado del reclamo",
  irregularidad: "Irregularidad",
  motivo_cambio: "Motivo del cambio",
  motivo: "Motivo",
  texto: "Texto",
  titulo: "Título",
  vence_en: "Vencimiento",
  archivo: "Archivo",
  contacto_email: "Correo de contacto",
  version: "Versión",
  vigente_desde: "Vigente desde",
  reglas: "Reglas",
  topes: "Topes",
  admin_nombre: "Nombre del administrador",
  admin_email: "Correo del administrador",
  estado: "Estado",
  uid: "Enlace",
  token: "Enlace",
  non_field_errors: "",
};

function etiquetaDeRuta(ruta: string): string {
  const partes = ruta.split(".");
  const nombres: string[] = [];
  for (let i = 0; i < partes.length; i++) {
    const parte = partes[i];
    if (/^\d+$/.test(parte)) {
      const anterior = nombres.pop() ?? "";
      nombres.push(`${anterior} ${Number(parte) + 1}`.trim());
    } else {
      nombres.push(NOMBRES_CAMPO[parte] ?? parte);
    }
  }
  const texto = nombres.filter(Boolean).join(" · ");
  return texto ? `${texto}: ` : "";
}

export function AvisoAmbar({ children }: { children: ReactNode }) {
  return <div className="aviso aviso-ambar">{children}</div>;
}

export function AvisoVerde({ children }: { children: ReactNode }) {
  return <div className="aviso aviso-verde">{children}</div>;
}

export function Exito({ children }: { children: ReactNode }) {
  return (
    <div className="aviso aviso-exito" role="status">
      {children}
    </div>
  );
}
