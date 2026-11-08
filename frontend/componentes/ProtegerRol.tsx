"use client";

import type { ReactNode } from "react";
import { useSesion } from "@/lib/sesion";
import type { Rol } from "@/lib/tipos";
import { Vista } from "./Vista";

/** Oculta la pantalla a los roles no permitidos (la API igual verifica cada solicitud). */
export function ProtegerRol({ roles, children }: { roles: Rol[]; children: ReactNode }) {
  const { usuario } = useSesion();
  if (!usuario) return null;
  if (!roles.includes(usuario.rol)) {
    return (
      <Vista migas={[{ texto: "Acceso denegado" }]}>
        <div className="aviso aviso-error" role="alert">
          <p>Tu perfil no tiene acceso a esta pantalla.</p>
        </div>
      </Vista>
    );
  }
  return <>{children}</>;
}
