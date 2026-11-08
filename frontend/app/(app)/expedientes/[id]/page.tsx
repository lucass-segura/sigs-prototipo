"use client";

import { Suspense } from "react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useApi } from "@/lib/useApi";
import { formatoFecha } from "@/lib/formato";
import { textoBienPrincipal } from "@/lib/etiquetas";
import type { Siniestro } from "@/lib/tipos";
import { EncabezadoPagina, Vista } from "@/componentes/Vista";
import { ProtegerRol } from "@/componentes/ProtegerRol";
import { Cargando, ErrorCarga } from "@/componentes/Estados";
import { InsigniaEstado } from "@/componentes/Insignias";
import { PestanaDatos } from "@/componentes/expediente/PestanaDatos";
import { PestanaAnalisis } from "@/componentes/expediente/PestanaAnalisis";
import { PestanaSeguimiento } from "@/componentes/expediente/PestanaSeguimiento";
import { PestanaDocumentos } from "@/componentes/expediente/PestanaDocumentos";
import { PestanaCierre } from "@/componentes/expediente/PestanaCierre";

const PESTANAS = [
  { clave: "datos", texto: "Datos" },
  { clave: "analisis", texto: "Análisis" },
  { clave: "seguimiento", texto: "Seguimiento" },
  { clave: "documentos", texto: "Documentos" },
  { clave: "cierre", texto: "Cierre" },
] as const;

type ClavePestana = (typeof PESTANAS)[number]["clave"];

function DetalleExpediente() {
  const parametros = useParams<{ id: string }>();
  const consulta = useSearchParams();
  const router = useRouter();
  const id = parametros.id;
  const { datos: s, error, cargando, recargar } = useApi<Siniestro>(`/siniestros/${id}`);

  const pedida = consulta.get("tab");
  const pestana: ClavePestana = PESTANAS.some((p) => p.clave === pedida) ? (pedida as ClavePestana) : "datos";

  if (cargando && !s) {
    return (
      <Vista migas={[{ texto: "Expedientes", href: "/expedientes" }, { texto: "…" }]}>
        <Cargando />
      </Vista>
    );
  }
  if (error || !s) {
    return (
      <Vista migas={[{ texto: "Expedientes", href: "/expedientes" }, { texto: "Expediente" }]}>
        {error ? (
          <ErrorCarga error={error}>
            <p>
              <Link href="/expedientes">Volver a Mis expedientes</Link>
            </p>
          </ErrorCarga>
        ) : null}
      </Vista>
    );
  }

  const bien = textoBienPrincipal(s.bienes[0]);
  const partes = [
    s.confirmado_en ? `Confirmado el ${formatoFecha(s.confirmado_en)}` : "Sin confirmar",
    s.poliza?.numero ? `Póliza ${s.poliza.numero}` : null,
    bien,
  ].filter(Boolean);

  const subtitulo =
    pestana === "cierre" ? "Al cerrar, el resumen queda disponible para otros peritos con los datos permitidos." : partes.join(" · ");

  return (
    <Vista migas={[{ texto: "Expedientes", href: "/expedientes" }, { texto: s.numero_expediente }]}>
      <EncabezadoPagina
        titulo={`${s.numero_expediente} · ${s.tipo}`}
        subtitulo={subtitulo}
        lateral={<InsigniaEstado estado={s.estado} />}
      />
      <nav className="pestanas" aria-label="Secciones del expediente">
        {PESTANAS.map((p) => (
          <Link
            key={p.clave}
            href={`/expedientes/${s.id}?tab=${p.clave}`}
            scroll={false}
            className={pestana === p.clave ? "activa" : undefined}
            aria-current={pestana === p.clave ? "page" : undefined}
          >
            {p.texto}
          </Link>
        ))}
      </nav>

      {pestana === "datos" ? (
        <PestanaDatos
          siniestro={s}
          alCambiar={recargar}
          alConfirmar={() => {
            recargar();
            router.push(`/expedientes/${s.id}?tab=analisis`);
          }}
        />
      ) : null}
      {pestana === "analisis" ? <PestanaAnalisis siniestro={s} /> : null}
      {pestana === "seguimiento" ? <PestanaSeguimiento siniestro={s} /> : null}
      {pestana === "documentos" ? <PestanaDocumentos siniestro={s} /> : null}
      {pestana === "cierre" ? <PestanaCierre siniestro={s} alCambiar={recargar} /> : null}
    </Vista>
  );
}

export default function PaginaExpediente() {
  return (
    <ProtegerRol roles={["perito"]}>
      <Suspense fallback={null}>
        <DetalleExpediente />
      </Suspense>
    </ProtegerRol>
  );
}
