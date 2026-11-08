import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { SesionProvider } from "@/lib/sesion";
import "./globals.css";

export const metadata: Metadata = {
  title: "SIGS · Gestión de siniestros",
  description: "Sistema Integral de Gestión de Siniestros y Prevención de Fraude. Prototipo académico con datos ficticios.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function LayoutRaiz({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body>
        <SesionProvider>{children}</SesionProvider>
      </body>
    </html>
  );
}
