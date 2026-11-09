"use client";

// Diálogos y cajones accesibles: el foco entra, no se escapa con Tab, Esc cierra y el foco vuelve a donde estaba.
import { useEffect, useRef } from "react";
import type { RefObject } from "react";

const FOCALIZABLES =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// Con un diálogo sobre otro (por ejemplo, confirmar sobre el cajón del croquis) solo responde el de arriba.
const pila: symbol[] = [];

export function useAtrapaFoco(contenedor: RefObject<HTMLElement | null>, alCerrar: () => void, inicial?: RefObject<HTMLElement | null>) {
  const cierre = useRef(alCerrar);
  cierre.current = alCerrar;

  useEffect(() => {
    const marca = Symbol("atrapa-foco");
    pila.push(marca);
    const anterior = document.activeElement as HTMLElement | null;
    const nodo = contenedor.current;
    const bloqueado = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const destino = inicial?.current ?? nodo?.querySelector<HTMLElement>(FOCALIZABLES) ?? nodo;
    destino?.focus();

    function alPulsar(e: KeyboardEvent) {
      if (e.defaultPrevented || pila[pila.length - 1] !== marca) return;
      if (e.key === "Escape") {
        e.preventDefault();
        cierre.current();
        return;
      }
      if (e.key !== "Tab" || !nodo) return;
      const lista = Array.from(nodo.querySelectorAll<HTMLElement>(FOCALIZABLES)).filter((el) => el.offsetParent !== null);
      if (lista.length === 0) {
        e.preventDefault();
        return;
      }
      const primero = lista[0];
      const ultimo = lista[lista.length - 1];
      const activo = document.activeElement;
      if (e.shiftKey && (activo === primero || !nodo.contains(activo))) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && (activo === ultimo || !nodo.contains(activo))) {
        e.preventDefault();
        primero.focus();
      }
    }
    window.addEventListener("keydown", alPulsar);
    return () => {
      window.removeEventListener("keydown", alPulsar);
      pila.splice(pila.indexOf(marca), 1);
      document.body.style.overflow = bloqueado;
      if (anterior && document.contains(anterior)) anterior.focus();
    };
    // El foco inicial se toma una sola vez al abrir.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
}
