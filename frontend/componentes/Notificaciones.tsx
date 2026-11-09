"use client";

// Avisos breves (toasts) para confirmar una acción o informar un error sin cortar el trabajo.
import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

type Tipo = "exito" | "error" | "info";

interface Aviso {
  id: number;
  tipo: Tipo;
  texto: string;
}

interface ValorNotificaciones {
  exito: (texto: string) => void;
  error: (texto: string) => void;
  info: (texto: string) => void;
}

const Contexto = createContext<ValorNotificaciones | null>(null);

export function NotificacionesProvider({ children }: { children: ReactNode }) {
  const [avisos, setAvisos] = useState<Aviso[]>([]);
  const siguiente = useRef(1);

  const quitar = useCallback((id: number) => setAvisos((lista) => lista.filter((a) => a.id !== id)), []);

  const agregar = useCallback(
    (tipo: Tipo, texto: string) => {
      const id = siguiente.current++;
      setAvisos((lista) => [...lista.slice(-3), { id, tipo, texto }]);
      window.setTimeout(() => quitar(id), tipo === "error" ? 9000 : 5000);
    },
    [quitar],
  );

  const valor = useMemo<ValorNotificaciones>(
    () => ({
      exito: (t) => agregar("exito", t),
      error: (t) => agregar("error", t),
      info: (t) => agregar("info", t),
    }),
    [agregar],
  );

  return (
    <Contexto.Provider value={valor}>
      {children}
      <div className="avisos-flotantes" role="region" aria-label="Notificaciones">
        {avisos.map((a) => (
          <div key={a.id} className={`aviso-flotante aviso-flotante-${a.tipo}`} role={a.tipo === "error" ? "alert" : "status"}>
            <span>{a.texto}</span>
            <button type="button" className="aviso-cerrar" aria-label="Cerrar aviso" onClick={() => quitar(a.id)}>
              ×
            </button>
          </div>
        ))}
      </div>
    </Contexto.Provider>
  );
}

export function useNotificar(): ValorNotificaciones {
  const valor = useContext(Contexto);
  if (!valor) throw new Error("useNotificar se usa dentro de NotificacionesProvider.");
  return valor;
}
