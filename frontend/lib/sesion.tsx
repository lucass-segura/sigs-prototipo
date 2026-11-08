"use client";

// Contexto de sesión: usuario autenticado, ingreso y salida.
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api, EVENTO_VERIFICAR_SESION } from "./api";
import type { RespuestaSesion, Rol, Usuario } from "./tipos";

interface ValorSesion {
  usuario: Usuario | null;
  cargando: boolean;
  ingresar: (email: string, password: string) => Promise<Usuario>;
  salir: () => Promise<void>;
  recargar: () => Promise<void>;
  reemplazarUsuario: (usuario: Usuario) => void;
}

const ContextoSesion = createContext<ValorSesion | null>(null);

export function SesionProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(true);
  const verificando = useRef(false);

  const recargar = useCallback(async () => {
    if (verificando.current) return;
    verificando.current = true;
    try {
      const datos = await api<RespuestaSesion>("/auth/sesion");
      setUsuario(datos.autenticado ? datos.usuario : null);
    } catch {
      setUsuario(null);
    } finally {
      verificando.current = false;
      setCargando(false);
    }
  }, []);

  useEffect(() => {
    void recargar();
  }, [recargar]);

  // Cuando la API rechaza una solicitud se revisa si la sesión sigue vigente (por ejemplo, tras 60 min sin actividad).
  useEffect(() => {
    const alVerificar = () => void recargar();
    window.addEventListener(EVENTO_VERIFICAR_SESION, alVerificar);
    return () => window.removeEventListener(EVENTO_VERIFICAR_SESION, alVerificar);
  }, [recargar]);

  const ingresar = useCallback(async (email: string, password: string) => {
    const datos = await api<{ usuario: Usuario }>("/auth/ingresar", { cuerpo: { email, password } });
    setUsuario(datos.usuario);
    return datos.usuario;
  }, []);

  const salir = useCallback(async () => {
    try {
      await api("/auth/salir", { metodo: "POST", cuerpo: {} });
    } finally {
      setUsuario(null);
    }
  }, []);

  const valor = useMemo<ValorSesion>(
    () => ({ usuario, cargando, ingresar, salir, recargar, reemplazarUsuario: setUsuario }),
    [usuario, cargando, ingresar, salir, recargar],
  );

  return <ContextoSesion.Provider value={valor}>{children}</ContextoSesion.Provider>;
}

export function useSesion(): ValorSesion {
  const valor = useContext(ContextoSesion);
  if (!valor) throw new Error("useSesion se usa dentro de SesionProvider.");
  return valor;
}

/** Pantalla de inicio según el rol. */
export function rutaInicial(rol: Rol): string {
  if (rol === "administrador") return "/admin/usuarios";
  if (rol === "superadministrador") return "/admin/espacios";
  return "/expedientes";
}
