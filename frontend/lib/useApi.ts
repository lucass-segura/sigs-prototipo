"use client";

// Carga un recurso con GET y lo vuelve a pedir cuando cambia la ruta.
import { useCallback, useEffect, useState } from "react";
import { api, ErrorApi } from "./api";

export interface EstadoCarga<T> {
  datos: T | null;
  error: ErrorApi | null;
  cargando: boolean;
  recargar: () => void;
  reemplazar: (datos: T) => void;
}

export function useApi<T>(ruta: string | null): EstadoCarga<T> {
  const [datos, setDatos] = useState<T | null>(null);
  const [error, setError] = useState<ErrorApi | null>(null);
  const [cargando, setCargando] = useState(ruta !== null);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    if (ruta === null) {
      setCargando(false);
      return;
    }
    let vigente = true;
    setCargando(true);
    api<T>(ruta)
      .then((respuesta) => {
        if (!vigente) return;
        setDatos(respuesta);
        setError(null);
      })
      .catch((e: unknown) => {
        if (!vigente) return;
        setDatos(null);
        setError(e instanceof ErrorApi ? e : new ErrorApi(0, "Ocurrió un error inesperado.", []));
      })
      .finally(() => {
        if (vigente) setCargando(false);
      });
    return () => {
      vigente = false;
    };
  }, [ruta, version]);

  const recargar = useCallback(() => setVersion((v) => v + 1), []);

  return { datos, error, cargando, recargar, reemplazar: setDatos };
}
