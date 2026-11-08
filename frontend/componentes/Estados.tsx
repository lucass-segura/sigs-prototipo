import type { ReactNode } from "react";
import type { ErrorApi } from "@/lib/api";

export function Cargando({ texto = "Cargando…" }: { texto?: string }) {
  return (
    <p className="cargando" role="status">
      {texto}
    </p>
  );
}

export function ErrorCarga({ error, children }: { error: ErrorApi; children?: ReactNode }) {
  return (
    <div className="aviso aviso-error" role="alert">
      <p>{error.message}</p>
      {children}
    </div>
  );
}

export function Vacio({ children }: { children: ReactNode }) {
  return <p className="vacio">{children}</p>;
}
