"use client";

// Contenedor de los selectores: globito junto al campo en pantallas anchas y hoja desde abajo en el teléfono.
// Esc cierra, Tab queda adentro, un toque afuera cierra y el foco vuelve al campo que lo abrió.
import { useEffect, useLayoutEffect, useRef, useSyncExternalStore } from "react";
import type { KeyboardEvent, ReactNode, RefObject } from "react";
import { createPortal } from "react-dom";

const FOCALIZABLES =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

const CONSULTA_MOVIL = "(max-width: 820px)";

function suscribir(aviso: () => void) {
  const consulta = window.matchMedia(CONSULTA_MOVIL);
  consulta.addEventListener("change", aviso);
  return () => consulta.removeEventListener("change", aviso);
}

/** `true` en el teléfono (hasta 820 px de ancho), donde los selectores se abren como hoja desde abajo. */
export function useMovil(): boolean {
  return useSyncExternalStore(
    suscribir,
    () => window.matchMedia(CONSULTA_MOVIL).matches,
    () => false,
  );
}

export function Emergente({
  anclaje,
  etiqueta,
  ancho,
  alCerrar,
  children,
}: {
  /** Elemento junto al que se abre. */
  anclaje: RefObject<HTMLElement | null>;
  etiqueta: string;
  /** Ancho en pantallas anchas, en píxeles. */
  ancho: number;
  /** `devolverFoco`: el foco vuelve al campo (Esc, elegir) o se queda donde el usuario lo puso (clic afuera). */
  alCerrar: (devolverFoco: boolean) => void;
  children: ReactNode;
}) {
  const movil = useMovil();
  const panel = useRef<HTMLDivElement>(null);
  const cierre = useRef(alCerrar);
  cierre.current = alCerrar;

  // Posición junto al campo (o arriba si abajo no entra) y foco inicial.
  useLayoutEffect(() => {
    const nodo = panel.current;
    if (!nodo) return;
    function colocar() {
      const campo = anclaje.current;
      if (!nodo || !campo || movil) return;
      const r = campo.getBoundingClientRect();
      const alto = nodo.offsetHeight;
      const libreAbajo = window.innerHeight - r.bottom - 12;
      const libreArriba = r.top - 12;
      const abajo = alto <= libreAbajo || libreAbajo >= libreArriba;
      const top = abajo ? r.bottom + 6 : Math.max(8, r.top - alto - 6);
      const left = Math.max(8, Math.min(r.left, window.innerWidth - ancho - 8));
      nodo.style.top = `${top}px`;
      nodo.style.left = `${left}px`;
      nodo.style.maxHeight = `${Math.max(260, (abajo ? libreAbajo : libreArriba) + 6)}px`;
      nodo.style.visibility = "visible";
    }
    if (movil) nodo.style.visibility = "visible";
    colocar();
    const inicial = nodo.querySelector<HTMLElement>("[data-foco-inicial]") ?? nodo.querySelector<HTMLElement>(FOCALIZABLES) ?? nodo;
    inicial.focus({ preventScroll: true });

    const observador = new ResizeObserver(colocar);
    observador.observe(nodo);
    window.addEventListener("resize", colocar);
    window.addEventListener("scroll", colocar, true);
    return () => {
      observador.disconnect();
      window.removeEventListener("resize", colocar);
      window.removeEventListener("scroll", colocar, true);
    };
  }, [anclaje, ancho, movil]);

  // Un toque o clic afuera cierra; el propio campo se encarga de abrir y cerrar con su clic.
  useEffect(() => {
    function afuera(e: PointerEvent) {
      const destino = e.target as Node | null;
      if (!destino || panel.current?.contains(destino) || anclaje.current?.contains(destino)) return;
      cierre.current(false);
    }
    document.addEventListener("pointerdown", afuera, true);
    return () => document.removeEventListener("pointerdown", afuera, true);
  }, [anclaje]);

  // En el teléfono la página de atrás no se desplaza mientras la hoja está abierta.
  useEffect(() => {
    if (!movil) return;
    const previo = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previo;
    };
  }, [movil]);

  function alPulsar(e: KeyboardEvent<HTMLDivElement>) {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      cierre.current(true);
      return;
    }
    if (e.key !== "Tab") return;
    const lista = Array.from(e.currentTarget.querySelectorAll<HTMLElement>(FOCALIZABLES)).filter((el) => el.offsetParent !== null);
    if (lista.length === 0) {
      e.preventDefault();
      return;
    }
    const primero = lista[0];
    const ultimo = lista[lista.length - 1];
    const activo = document.activeElement;
    if (e.shiftKey && (activo === primero || activo === e.currentTarget)) {
      e.preventDefault();
      ultimo.focus();
    } else if (!e.shiftKey && activo === ultimo) {
      e.preventDefault();
      primero.focus();
    }
  }

  return createPortal(
    <>
      {movil ? <div className="emergente-fondo" aria-hidden="true" /> : null}
      <div
        ref={panel}
        className={`emergente${movil ? " emergente-hoja" : ""}`}
        role="dialog"
        aria-label={etiqueta}
        tabIndex={-1}
        style={{ width: movil ? undefined : ancho, visibility: "hidden" }}
        onKeyDown={alPulsar}
      >
        {movil ? (
          <div className="emergente-cabecera">
            <strong>{etiqueta}</strong>
            <button type="button" className="boton boton-chico" onClick={() => alCerrar(true)}>
              Cerrar
            </button>
          </div>
        ) : null}
        {children}
      </div>
    </>,
    document.body,
  );
}
