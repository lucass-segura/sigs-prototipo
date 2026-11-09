"use client";

// Cuadro de confirmación para acciones que no se pueden deshacer (anular, baja, bloqueo, descartar cambios).
import { createContext, useCallback, useContext, useId, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useAtrapaFoco } from "@/lib/useAtrapaFoco";

export interface OpcionesConfirmacion {
  titulo: string;
  mensaje: ReactNode;
  /** Texto del botón que confirma. */
  confirmar: string;
  /** Texto del botón que cancela. */
  cancelar?: string;
  /** Marca la acción como destructiva (botón rojo). */
  peligro?: boolean;
}

type Confirmador = (opciones: OpcionesConfirmacion) => Promise<boolean>;

const Contexto = createContext<Confirmador | null>(null);

interface Pendiente {
  opciones: OpcionesConfirmacion;
  resolver: (valor: boolean) => void;
}

function Dialogo({ pendiente, cerrar }: { pendiente: Pendiente; cerrar: (valor: boolean) => void }) {
  const caja = useRef<HTMLDivElement>(null);
  const cancelar = useRef<HTMLButtonElement>(null);
  const idTitulo = useId();
  const idMensaje = useId();
  const { opciones } = pendiente;
  // El foco empieza en «Cancelar»: confirmar una acción destructiva exige un gesto deliberado.
  useAtrapaFoco(caja, () => cerrar(false), cancelar);

  return (
    <div className="modal-fondo modal-fondo-alto" onMouseDown={(e) => e.target === e.currentTarget && cerrar(false)}>
      <div ref={caja} className="dialogo" role="alertdialog" aria-modal="true" aria-labelledby={idTitulo} aria-describedby={idMensaje}>
        <h2 id={idTitulo}>{opciones.titulo}</h2>
        <div id={idMensaje} className="dialogo-mensaje">
          {opciones.mensaje}
        </div>
        <div className="acciones dialogo-acciones">
          <button ref={cancelar} type="button" className="boton" onClick={() => cerrar(false)}>
            {opciones.cancelar ?? "Cancelar"}
          </button>
          <button type="button" className={`boton ${opciones.peligro ? "boton-peligro-solido" : "boton-principal"}`} onClick={() => cerrar(true)}>
            {opciones.confirmar}
          </button>
        </div>
      </div>
    </div>
  );
}

export function ConfirmarProvider({ children }: { children: ReactNode }) {
  const [pendiente, setPendiente] = useState<Pendiente | null>(null);

  const confirmar = useCallback<Confirmador>(
    (opciones) => new Promise<boolean>((resolver) => setPendiente({ opciones, resolver })),
    [],
  );

  const cerrar = useCallback(
    (valor: boolean) => {
      pendiente?.resolver(valor);
      setPendiente(null);
    },
    [pendiente],
  );

  return (
    <Contexto.Provider value={confirmar}>
      {children}
      {pendiente ? <Dialogo pendiente={pendiente} cerrar={cerrar} /> : null}
    </Contexto.Provider>
  );
}

export function useConfirmar(): Confirmador {
  const valor = useContext(Contexto);
  if (!valor) throw new Error("useConfirmar se usa dentro de ConfirmarProvider.");
  return valor;
}
