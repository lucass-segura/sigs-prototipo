"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { FormularioSiniestro } from "@/componentes/FormularioSiniestro";
import { ProtegerRol } from "@/componentes/ProtegerRol";

function Contenido() {
  const parametros = useSearchParams();
  const id = Number(parametros.get("id"));
  return <FormularioSiniestro key={id || "nuevo"} idBorrador={Number.isInteger(id) && id > 0 ? id : null} />;
}

export default function PaginaNuevoSiniestro() {
  return (
    <ProtegerRol roles={["perito"]}>
      <Suspense fallback={null}>
        <Contenido />
      </Suspense>
    </ProtegerRol>
  );
}
