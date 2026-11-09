"use client";

import { useEffect, useState } from "react";
import { ahoraLocal } from "@/lib/fechas";

/** Fecha y hora actuales de Buenos Aires; con `activo` se refrescan cada 20 segundos (por ejemplo, para «no futuro»). */
export function useAhora(activo = true): { fecha: string; hora: string } {
  const [ahora, setAhora] = useState(() => ahoraLocal());
  useEffect(() => {
    if (!activo) return;
    const refrescar = () => setAhora((previo) => {
      const nuevo = ahoraLocal();
      return nuevo.fecha === previo.fecha && nuevo.hora === previo.hora ? previo : nuevo;
    });
    refrescar();
    const intervalo = window.setInterval(refrescar, 20_000);
    return () => window.clearInterval(intervalo);
  }, [activo]);
  return ahora;
}
