"use client";

import { useCallback, useRef, useState } from "react";

/**
 * Junta lo que informan los selectores de un formulario: si alguno tiene un valor que no se puede enviar
 * (fuera de los límites o vacío siendo obligatorio), `revisar()` lo marca en pantalla y devuelve `true`.
 *
 *   const validez = useValidezFechas();
 *   <SelectorFecha {...validez.props("fecha-hecho")} … />
 *   if (validez.revisar()) return;   // antes de enviar
 */
export function useValidezFechas() {
  const [invalidos, setInvalidos] = useState<Record<string, string>>({});
  const [revision, setRevision] = useState(0);
  const actuales = useRef<Record<string, string>>({});

  const informar = useCallback((id: string, mensaje: string | null) => {
    if ((actuales.current[id] ?? null) === mensaje) return;
    const siguiente = { ...actuales.current };
    if (mensaje) siguiente[id] = mensaje;
    else delete siguiente[id];
    actuales.current = siguiente;
    setInvalidos(siguiente);
  }, []);

  const props = useCallback(
    (id: string) => ({ onInvalido: (mensaje: string | null) => informar(id, mensaje), revision }),
    [informar, revision],
  );

  /** Muestra los mensajes de todos los selectores y dice si hay alguno que impida enviar. Enfoca el primero. */
  const revisar = useCallback((): boolean => {
    const campos = Object.keys(actuales.current)
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null)
      .sort((a, b) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
    if (Object.keys(actuales.current).length === 0) return false;
    setRevision((n) => n + 1);
    campos[0]?.focus();
    return true;
  }, []);

  return { invalidos, props, revisar, hayInvalidos: Object.keys(invalidos).length > 0 };
}
