"use client";

// Definir la contraseña con el enlace del correo (primer ingreso o restablecimiento).
import { useState } from "react";
import type { FormEvent } from "react";
import Link from "next/link";
import { api, erroresDeCampo } from "@/lib/api";
import { useApi } from "@/lib/useApi";
import { Campo } from "./Campo";
import { ErrorFormulario, Exito } from "./Avisos";
import { Cargando } from "./Estados";

export function FormularioContrasena({ uid, token, etiquetaBoton }: { uid: string; token: string; etiquetaBoton: string }) {
  const enlace = useApi<{ valido: boolean; email: string | null }>(
    `/auth/enlace?uid=${encodeURIComponent(uid)}&token=${encodeURIComponent(token)}`,
  );
  const [password, setPassword] = useState("");
  const [repetida, setRepetida] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [mensajeLocal, setMensajeLocal] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [listo, setListo] = useState<string | null>(null);

  if (enlace.cargando) return <Cargando />;

  if (listo) {
    return (
      <div className="auth-caja-interior">
        <Exito>{listo}</Exito>
        <p className="auth-ayuda">
          <Link href="/ingresar">Ir a Ingresar</Link>
        </p>
      </div>
    );
  }

  if (enlace.error || !enlace.datos?.valido) {
    return (
      <div className="auth-caja-interior">
        <div className="aviso aviso-error" role="alert">
          <p>{enlace.error?.detalle ?? "El enlace no es válido o venció."}</p>
        </div>
        <p className="auth-ayuda">
          <Link href="/restablecer">Pedir un enlace nuevo</Link>
        </p>
      </div>
    );
  }

  async function enviar(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setMensajeLocal(null);
    if (password !== repetida) {
      setMensajeLocal("Las contraseñas no coinciden.");
      return;
    }
    setEnviando(true);
    try {
      const respuesta = await api<{ detalle: string }>("/auth/definir-contrasena", {
        cuerpo: { uid, token, password },
      });
      setListo(respuesta?.detalle ?? "Contraseña actualizada. Ya podés ingresar.");
    } catch (e) {
      setError(e);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <form onSubmit={enviar} noValidate>
      {enlace.datos?.email ? <p className="auth-ayuda">Cuenta: {enlace.datos.email}</p> : null}
      <Campo
        etiqueta="Contraseña nueva"
        id="password"
        ayuda="Mínimo 8 caracteres, con mayúscula, minúscula, número y un carácter especial."
        errores={erroresDeCampo(error, "password")}
      >
        <input
          id="password"
          type="password"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </Campo>
      <Campo etiqueta="Repetí la contraseña" id="repetida">
        <input
          id="repetida"
          type="password"
          autoComplete="new-password"
          value={repetida}
          onChange={(e) => setRepetida(e.target.value)}
          required
        />
      </Campo>
      {mensajeLocal ? (
        <div className="aviso aviso-error" role="alert">
          <p>{mensajeLocal}</p>
        </div>
      ) : null}
      <ErrorFormulario error={error} />
      <button type="submit" className="boton boton-principal boton-ancho" disabled={enviando}>
        {enviando ? "Guardando…" : etiquetaBoton}
      </button>
    </form>
  );
}
