"use client";

// Marco de la aplicación para usuarios con sesión: barra lateral verde oscuro y contenido claro.
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useSesion } from "@/lib/sesion";
import { ETIQUETA_ROL } from "@/lib/etiquetas";
import type { Rol } from "@/lib/tipos";
import { Cargando } from "@/componentes/Estados";

interface ItemMenu {
  texto: string;
  href: string;
  /** Prefijos de ruta que dejan el ítem resaltado. */
  activo: (ruta: string) => boolean;
}

function menuPorRol(rol: Rol): ItemMenu[] {
  const reglas: ItemMenu = {
    texto: "Reglas del indicador",
    href: "/reglas",
    activo: (r) => r.startsWith("/reglas"),
  };
  const perfil: ItemMenu = { texto: "Perfil", href: "/perfil", activo: (r) => r.startsWith("/perfil") };
  if (rol === "perito") {
    return [
      {
        texto: "Expedientes",
        href: "/expedientes",
        activo: (r) => r.startsWith("/expedientes") && r !== "/expedientes/nuevo",
      },
      { texto: "Nuevo siniestro", href: "/expedientes/nuevo", activo: (r) => r === "/expedientes/nuevo" },
      { texto: "Tareas", href: "/tareas", activo: (r) => r.startsWith("/tareas") },
      reglas,
      perfil,
    ];
  }
  if (rol === "administrador") {
    return [
      { texto: "Usuarios", href: "/admin/usuarios", activo: (r) => r.startsWith("/admin/usuarios") },
      { texto: "Auditoría", href: "/admin/auditoria", activo: (r) => r.startsWith("/admin/auditoria") },
      reglas,
      perfil,
    ];
  }
  return [
    { texto: "Espacios", href: "/admin/espacios", activo: (r) => r.startsWith("/admin/espacios") },
    reglas,
    perfil,
  ];
}

export default function LayoutAplicacion({ children }: { children: ReactNode }) {
  const { usuario, cargando, salir } = useSesion();
  const router = useRouter();
  const ruta = usePathname();
  const [menuAbierto, setMenuAbierto] = useState(false);

  useEffect(() => {
    if (!cargando && !usuario) router.replace("/ingresar");
  }, [cargando, usuario, router]);

  useEffect(() => {
    setMenuAbierto(false);
  }, [ruta]);

  if (cargando || !usuario) {
    return (
      <div className="centrado">
        <Cargando />
      </div>
    );
  }

  const menu = menuPorRol(usuario.rol);

  return (
    <div className="aplicacion">
      <aside className={`lateral${menuAbierto ? " lateral-abierto" : ""}`}>
        <div className="lateral-cabecera">
          <div>
            <div className="marca">SIGS</div>
            <div className="marca-sub">Gestión de siniestros</div>
          </div>
          <button
            type="button"
            className="boton-menu"
            aria-expanded={menuAbierto}
            aria-controls="menu-principal"
            onClick={() => setMenuAbierto((a) => !a)}
          >
            Menú
          </button>
        </div>
        <nav id="menu-principal" className="lateral-menu" aria-label="Principal">
          <div className="lateral-seccion">Trabajo</div>
          {menu.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={item.activo(ruta) ? "activo" : undefined}
              aria-current={item.activo(ruta) ? "page" : undefined}
            >
              {item.texto}
            </Link>
          ))}
        </nav>
        <div className="lateral-pie">
          <div className="lateral-usuario">
            {ETIQUETA_ROL[usuario.rol]} {usuario.nombre}
          </div>
          <div className="lateral-espacio">{usuario.espacio ? `Espacio ${usuario.espacio.nombre}` : "Todos los espacios"}</div>
          <button
            type="button"
            className="boton-salir"
            onClick={async () => {
              await salir();
              router.replace("/ingresar");
            }}
          >
            Salir
          </button>
        </div>
      </aside>
      <div className="contenido">{children}</div>
    </div>
  );
}
