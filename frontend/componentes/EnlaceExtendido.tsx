"use client";

// Enlace «extendido»: su área clicable cubre toda la tarjeta (la tarjeta tiene que ser `position: relative`).
// Es un enlace real: Enter lo abre, Espacio también, y el foco se ve alrededor de toda la tarjeta.
import Link from "next/link";
import type { KeyboardEvent, ReactNode } from "react";

export function EnlaceExtendido({ href, children, className, ...resto }: { href: string; children: ReactNode; className?: string; "aria-label"?: string }) {
  function alPulsar(evento: KeyboardEvent<HTMLAnchorElement>) {
    if (evento.key === " ") {
      evento.preventDefault();
      evento.currentTarget.click();
    }
  }
  return (
    <Link href={href} className={`enlace-extendido${className ? ` ${className}` : ""}`} onKeyDown={alPulsar} {...resto}>
      {children}
    </Link>
  );
}
