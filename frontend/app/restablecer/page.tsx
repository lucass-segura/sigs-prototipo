"use client";

import { Suspense, useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { PanelAuth } from "@/componentes/PanelAuth";
import { Campo } from "@/componentes/Campo";
import { ErrorFormulario, Exito } from "@/componentes/Avisos";
import { FormularioContrasena } from "@/componentes/FormularioContrasena";

function PedirEnlace() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const respuesta = await api<{ detalle: string }>("/auth/restablecer", { cuerpo: { email: email.trim() } });
      setMensaje(respuesta?.detalle ?? "Si el correo está registrado, te enviamos un enlace para restablecer la contraseña.");
    } catch (e) {
      setError(e);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <PanelAuth titulo="Restablecer contraseña" subtitulo="Te enviamos un enlace al correo. Vence en 1 hora y se usa una sola vez.">
      {mensaje ? (
        <>
          <Exito>{mensaje}</Exito>
          <p className="auth-ayuda">
            <Link href="/ingresar">Volver a Ingresar</Link>
          </p>
        </>
      ) : (
        <form onSubmit={enviar}>
          <Campo etiqueta="Correo electrónico" id="email">
            <input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </Campo>
          <ErrorFormulario error={error} />
          <button type="submit" className="boton boton-principal boton-ancho" disabled={enviando}>
            {enviando ? "Enviando…" : "Enviar enlace"}
          </button>
          <p className="auth-ayuda">
            <Link href="/ingresar">Volver a Ingresar</Link>
          </p>
        </form>
      )}
    </PanelAuth>
  );
}

function Contenido() {
  const parametros = useSearchParams();
  const uid = parametros.get("uid");
  const token = parametros.get("token");
  if (uid && token) {
    return (
      <PanelAuth titulo="Restablecer contraseña" subtitulo="Elegí una contraseña nueva para tu cuenta.">
        <FormularioContrasena uid={uid} token={token} etiquetaBoton="Restablecer contraseña" />
      </PanelAuth>
    );
  }
  return <PedirEnlace />;
}

export default function PaginaRestablecer() {
  return (
    <Suspense fallback={null}>
      <Contenido />
    </Suspense>
  );
}
