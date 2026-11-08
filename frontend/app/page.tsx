"use client";

// La raíz redirige según la sesión y el rol.
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { rutaInicial, useSesion } from "@/lib/sesion";
import { Cargando } from "@/componentes/Estados";

export default function Inicio() {
  const { usuario, cargando } = useSesion();
  const router = useRouter();

  useEffect(() => {
    if (cargando) return;
    router.replace(usuario ? rutaInicial(usuario.rol) : "/ingresar");
  }, [usuario, cargando, router]);

  return (
    <div className="centrado">
      <Cargando />
    </div>
  );
}
