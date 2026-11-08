"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { PanelAuth } from "@/componentes/PanelAuth";
import { FormularioContrasena } from "@/componentes/FormularioContrasena";

function Contenido() {
  const parametros = useSearchParams();
  const uid = parametros.get("uid") ?? "";
  const token = parametros.get("token") ?? "";
  return (
    <PanelAuth titulo="Primer ingreso" subtitulo="Definí tu contraseña. Solo vos la vas a conocer.">
      {uid && token ? (
        <FormularioContrasena uid={uid} token={token} etiquetaBoton="Guardar contraseña" />
      ) : (
        <div className="aviso aviso-error" role="alert">
          <p>El enlace no es válido o venció.</p>
        </div>
      )}
    </PanelAuth>
  );
}

export default function PaginaPrimerIngreso() {
  return (
    <Suspense fallback={null}>
      <Contenido />
    </Suspense>
  );
}
