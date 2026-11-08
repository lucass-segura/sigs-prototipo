"use client";

import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { rutaInicial, useSesion } from "@/lib/sesion";
import { mensajeDeError } from "@/lib/api";
import { PanelAuth } from "@/componentes/PanelAuth";
import { Campo } from "@/componentes/Campo";

export default function PaginaIngresar() {
  const { usuario, cargando, ingresar } = useSesion();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (!cargando && usuario) router.replace(rutaInicial(usuario.rol));
  }, [cargando, usuario, router]);

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setEnviando(true);
    try {
      const u = await ingresar(email.trim(), password);
      router.replace(rutaInicial(u.rol));
    } catch (e) {
      setError(mensajeDeError(e));
      setEnviando(false);
    }
  }

  return (
    <PanelAuth titulo="Ingresar" subtitulo="Usá el correo con el que te dieron de alta.">
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
        <Campo etiqueta="Contraseña" id="password">
          <input
            id="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Campo>
        {error ? (
          <div className="aviso aviso-error" role="alert">
            <p>{error}</p>
          </div>
        ) : null}
        <p className="auth-ayuda">
          Si olvidaste la contraseña pedí el blanqueo al administrador del espacio.
          <br />
          <Link href="/restablecer">Restablecer contraseña</Link>
        </p>
        <button type="submit" className="boton boton-principal boton-ancho" disabled={enviando}>
          {enviando ? "Ingresando…" : "Ingresar"}
        </button>
      </form>
    </PanelAuth>
  );
}
