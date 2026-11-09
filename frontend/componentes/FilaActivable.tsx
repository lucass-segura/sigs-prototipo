"use client";

// Fila de tabla clicable completa (mouse y teclado) sin romper los botones y enlaces de adentro.
import { useRouter } from "next/navigation";
import type { KeyboardEvent, MouseEvent, ReactNode } from "react";

const INTERACTIVOS = "a, button, input, select, textarea, label, summary, details, [role='button']";

export function FilaActivable({
  etiqueta,
  alActivar,
  children,
  className,
  activable = true,
}: {
  /** Lo que lee un lector de pantalla, por ejemplo «Abrir el expediente EXP-2026-0147». */
  etiqueta: string;
  alActivar: () => void;
  children: ReactNode;
  className?: string;
  activable?: boolean;
}) {
  function alHacerClic(evento: MouseEvent<HTMLTableRowElement>) {
    if (!activable || evento.defaultPrevented) return;
    if ((evento.target as HTMLElement).closest(INTERACTIVOS)) return;
    // Seleccionar texto con el mouse no es abrir la fila.
    if (window.getSelection()?.toString()) return;
    alActivar();
  }

  function alPulsar(evento: KeyboardEvent<HTMLTableRowElement>) {
    if (!activable || evento.target !== evento.currentTarget) return;
    if (evento.key === "Enter" || evento.key === " ") {
      evento.preventDefault();
      alActivar();
    }
  }

  return (
    <tr
      className={`${activable ? "fila-clicable" : ""}${className ? ` ${className}` : ""}`}
      tabIndex={activable ? 0 : undefined}
      aria-label={activable ? etiqueta : undefined}
      onClick={alHacerClic}
      onKeyDown={alPulsar}
    >
      {children}
    </tr>
  );
}

/** Fila que lleva a otra pantalla. El enlace de adentro sigue siendo un enlace real (clic derecho, nueva pestaña). */
export function FilaEnlace({ href, etiqueta, children, className }: { href: string; etiqueta: string; children: ReactNode; className?: string }) {
  const router = useRouter();
  return (
    <FilaActivable etiqueta={etiqueta} className={className} alActivar={() => router.push(href)}>
      {children}
    </FilaActivable>
  );
}
