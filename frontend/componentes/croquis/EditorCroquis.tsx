"use client";

// Editor de croquis con SVG propio (sin librerías): paleta, mover, rotar, duplicar, borrar, deshacer y rehacer.
// Los punteros (mouse, lápiz y dedo) usan la misma ruta de eventos, así que sirve también en una tablet.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as EventoTeclado, PointerEvent as EventoPuntero } from "react";
import {
  COLORES_PALETA,
  COLORES_VEHICULO,
  COLOR_VEHICULO_OTRO,
  MAX_ELEMENTOS,
  MAX_PUNTOS,
  NOMBRE_TIPO,
  PASO_CUADRICULA,
  mitadDeElemento,
  nuevoElemento,
  nuevoId,
} from "@/lib/croquis";
import type { Elemento, Escena, TipoElemento } from "@/lib/croquis";
import { useConfirmar } from "../Confirmar";
import { useNotificar } from "../Notificaciones";
import { EscenaSvg, IconoElemento } from "./EscenaSvg";

type Herramienta = "seleccionar" | "lapiz" | "mano";

interface ItemPaleta {
  clave: string;
  texto: string;
  tipo: TipoElemento;
  extra?: Partial<Elemento>;
}

const PALETA: { grupo: string; items: ItemPaleta[] }[] = [
  {
    grupo: "Calles",
    items: [
      { clave: "calle", texto: "Calle recta", tipo: "calle" },
      { clave: "cruce", texto: "Cruce", tipo: "cruce" },
      { clave: "curva", texto: "Curva", tipo: "curva" },
      { clave: "rotonda", texto: "Rotonda", tipo: "rotonda" },
    ],
  },
  {
    grupo: "Vehículos",
    items: [
      { clave: "auto-a", texto: "Auto A", tipo: "vehiculo", extra: { etiqueta: "A" } },
      { clave: "auto-b", texto: "Auto B", tipo: "vehiculo", extra: { etiqueta: "B" } },
      { clave: "auto-c", texto: "Auto C", tipo: "vehiculo", extra: { etiqueta: "C" } },
      { clave: "moto", texto: "Moto", tipo: "moto" },
    ],
  },
  {
    grupo: "Marcas",
    items: [
      { clave: "persona", texto: "Persona", tipo: "persona" },
      { clave: "flecha", texto: "Sentido", tipo: "flecha" },
      { clave: "impacto", texto: "Impacto", tipo: "impacto" },
      { clave: "texto", texto: "Texto", tipo: "texto" },
    ],
  },
];

const TIPOS_CON_COLOR: TipoElemento[] = ["vehiculo", "moto", "persona", "flecha", "texto", "lapiz"];

function normalizar(grados: number): number {
  let g = ((grados + 180) % 360 + 360) % 360 - 180;
  if (g === -180) g = 180;
  return Math.round(g * 10) / 10;
}

function ajustar(valor: number, paso: number): number {
  return Math.round(valor / paso) * paso;
}

interface Gesto {
  tipo: "mover" | "rotar" | "lapiz" | "mano";
  id?: string;
  antes: Escena;
  inicio: { x: number; y: number };
  origen?: { x: number; y: number };
  cliente?: { x: number; y: number; scrollX: number; scrollY: number };
  movido: boolean;
}

export interface EditorProps {
  escena: Escena;
  alCambiar: (escena: Escena, sinGuardar: boolean) => void;
  /** Referencia al `<svg>` del dibujo, para exportar el PNG. */
  svgRef: React.RefObject<SVGSVGElement | null>;
}

export function EditorCroquis({ escena: escenaInicial, alCambiar, svgRef }: EditorProps) {
  const confirmar = useConfirmar();
  const notificar = useNotificar();
  const [escena, setEscena] = useState<Escena>(escenaInicial);
  const [pasado, setPasado] = useState<Escena[]>([]);
  const [futuro, setFuturo] = useState<Escena[]>([]);
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [herramienta, setHerramienta] = useState<Herramienta>("seleccionar");
  const [trazo, setTrazo] = useState<[number, number][] | null>(null);
  const [vista, setVista] = useState(1);
  const [colorTrazo, setColorTrazo] = useState(COLORES_PALETA[0]);
  const base = useRef(JSON.stringify(escenaInicial));
  const marco = useRef<HTMLDivElement>(null);
  const gesto = useRef<Gesto | null>(null);
  const escenaActual = useRef(escena);
  escenaActual.current = escena;
  const cuenta = useRef(0);

  // El cajón necesita saber qué hay en el editor y si hay cambios sin guardar.
  useEffect(() => {
    alCambiar(escena, JSON.stringify(escena) !== base.current);
  }, [escena, alCambiar]);

  const elegido = useMemo(() => escena.elementos.find((e) => e.id === seleccion) ?? null, [escena.elementos, seleccion]);

  const registrar = useCallback((antes: Escena) => {
    setPasado((p) => [...p.slice(-99), antes]);
    setFuturo([]);
  }, []);

  /** Cambio discreto: queda un paso en el historial. */
  const cambiar = useCallback(
    (fn: (e: Escena) => Escena) => {
      const antes = escenaActual.current;
      const despues = fn(antes);
      if (despues === antes) return;
      registrar(antes);
      setEscena(despues);
    },
    [registrar],
  );

  const actualizar = useCallback(
    (id: string, cambios: Partial<Elemento>) => {
      cambiar((e) => ({ ...e, elementos: e.elementos.map((el) => (el.id === id ? { ...el, ...cambios } : el)) }));
    },
    [cambiar],
  );

  function deshacer() {
    const previa = pasado[pasado.length - 1];
    if (!previa) return;
    setFuturo((f) => [escena, ...f]);
    setPasado((p) => p.slice(0, -1));
    setEscena(previa);
    if (seleccion && !previa.elementos.some((e) => e.id === seleccion)) setSeleccion(null);
  }

  function rehacer() {
    const siguiente = futuro[0];
    if (!siguiente) return;
    setPasado((p) => [...p, escena]);
    setFuturo((f) => f.slice(1));
    setEscena(siguiente);
    if (seleccion && !siguiente.elementos.some((e) => e.id === seleccion)) setSeleccion(null);
  }

  function agregar(item: ItemPaleta) {
    if (escena.elementos.length >= MAX_ELEMENTOS) {
      notificar.error(`El croquis no puede tener más de ${MAX_ELEMENTOS} elementos.`);
      return;
    }
    const centro = centroVisible();
    const desplazamiento = (cuenta.current++ % 6) * 24;
    const x = ajustar(centro.x + desplazamiento, 10);
    const y = ajustar(centro.y + desplazamiento, 10);
    const nuevo = nuevoElemento(item.tipo, x, y, item.extra);
    cambiar((e) => ({ ...e, elementos: [...e.elementos, nuevo] }));
    setSeleccion(nuevo.id);
    setHerramienta("seleccionar");
  }

  function duplicar() {
    if (!elegido) return;
    if (escena.elementos.length >= MAX_ELEMENTOS) {
      notificar.error(`El croquis no puede tener más de ${MAX_ELEMENTOS} elementos.`);
      return;
    }
    const copia: Elemento = { ...elegido, id: nuevoId(), x: elegido.x + 30, y: elegido.y + 30, puntos: elegido.puntos?.map((p) => [...p] as [number, number]) };
    cambiar((e) => ({ ...e, elementos: [...e.elementos, copia] }));
    setSeleccion(copia.id);
  }

  function borrar() {
    if (!elegido) return;
    const id = elegido.id;
    cambiar((e) => ({ ...e, elementos: e.elementos.filter((el) => el.id !== id) }));
    setSeleccion(null);
  }

  function ordenar(alFrente: boolean) {
    if (!elegido) return;
    const id = elegido.id;
    cambiar((e) => {
      const resto = e.elementos.filter((el) => el.id !== id);
      return { ...e, elementos: alFrente ? [...resto, elegido] : [elegido, ...resto] };
    });
  }

  async function limpiar() {
    if (escena.elementos.length === 0) return;
    const si = await confirmar({
      titulo: "¿Limpiar el croquis?",
      mensaje: "Se borran todos los elementos del dibujo. Podés deshacerlo con «Deshacer» mientras no cierres el editor.",
      confirmar: "Limpiar",
      peligro: true,
    });
    if (!si) return;
    cambiar((e) => ({ ...e, elementos: [] }));
    setSeleccion(null);
  }

  // ----------------------------------------------------------- Coordenadas

  function aEscena(clienteX: number, clienteY: number): { x: number; y: number } {
    const svg = svgRef.current;
    const matriz = svg?.getScreenCTM();
    if (!svg || !matriz) return { x: 0, y: 0 };
    const punto = svg.createSVGPoint();
    punto.x = clienteX;
    punto.y = clienteY;
    const p = punto.matrixTransform(matriz.inverse());
    return { x: p.x, y: p.y };
  }

  function centroVisible(): { x: number; y: number } {
    const caja = marco.current?.getBoundingClientRect();
    if (!caja) return { x: escena.ancho / 2, y: escena.alto / 2 };
    const p = aEscena(caja.left + caja.width / 2, caja.top + caja.height / 2);
    return {
      x: Math.min(Math.max(p.x, 100), escena.ancho - 100),
      y: Math.min(Math.max(p.y, 100), escena.alto - 100),
    };
  }

  // ----------------------------------------------------------- Punteros

  function alBajarPuntero(ev: EventoPuntero<SVGSVGElement>) {
    if (gesto.current || (ev.pointerType === "mouse" && ev.button !== 0)) return;
    const objetivo = ev.target as Element;
    const p = aEscena(ev.clientX, ev.clientY);
    const captura = () => ev.currentTarget.setPointerCapture(ev.pointerId);

    if (herramienta === "mano") {
      const m = marco.current;
      if (!m) return;
      gesto.current = { tipo: "mano", antes: escena, inicio: p, movido: false, cliente: { x: ev.clientX, y: ev.clientY, scrollX: m.scrollLeft, scrollY: m.scrollTop } };
      captura();
      return;
    }
    if (herramienta === "lapiz") {
      gesto.current = { tipo: "lapiz", antes: escena, inicio: p, movido: false };
      setTrazo([[p.x, p.y]]);
      setSeleccion(null);
      captura();
      return;
    }
    if (objetivo.closest("[data-rotar]") && elegido) {
      gesto.current = { tipo: "rotar", id: elegido.id, antes: escena, inicio: p, movido: false };
      captura();
      return;
    }
    const nodo = objetivo.closest("[data-elemento]");
    const id = nodo?.getAttribute("data-elemento");
    const el = id ? escena.elementos.find((e) => e.id === id) : null;
    if (el) {
      setSeleccion(el.id);
      gesto.current = { tipo: "mover", id: el.id, antes: escena, inicio: p, origen: { x: el.x, y: el.y }, movido: false };
      captura();
    } else {
      setSeleccion(null);
    }
  }

  function alMoverPuntero(ev: EventoPuntero<SVGSVGElement>) {
    const g = gesto.current;
    if (!g) return;
    if (g.tipo === "mano") {
      const m = marco.current;
      if (m && g.cliente) {
        m.scrollLeft = g.cliente.scrollX - (ev.clientX - g.cliente.x);
        m.scrollTop = g.cliente.scrollY - (ev.clientY - g.cliente.y);
      }
      return;
    }
    const p = aEscena(ev.clientX, ev.clientY);
    if (g.tipo === "lapiz") {
      setTrazo((actual) => {
        if (!actual || actual.length >= MAX_PUNTOS - 1) return actual;
        const ultimo = actual[actual.length - 1];
        return Math.hypot(p.x - ultimo[0], p.y - ultimo[1]) < 3 ? actual : [...actual, [p.x, p.y]];
      });
      return;
    }
    if (g.tipo === "mover" && g.origen && g.id) {
      let x = g.origen.x + (p.x - g.inicio.x);
      let y = g.origen.y + (p.y - g.inicio.y);
      if (escena.cuadricula) {
        x = ajustar(x, PASO_CUADRICULA / 2);
        y = ajustar(y, PASO_CUADRICULA / 2);
      }
      x = Math.min(Math.max(x, 0), escena.ancho);
      y = Math.min(Math.max(y, 0), escena.alto);
      const id = g.id;
      g.movido = true;
      setEscena((e) => ({ ...e, elementos: e.elementos.map((el) => (el.id === id ? { ...el, x, y } : el)) }));
      return;
    }
    if (g.tipo === "rotar" && g.id) {
      const el = escenaActual.current.elementos.find((e) => e.id === g.id);
      if (!el) return;
      let grados = (Math.atan2(p.y - el.y, p.x - el.x) * 180) / Math.PI + 90;
      const cercano = ajustar(grados, 15);
      if (ev.shiftKey || Math.abs(cercano - grados) < 4) grados = cercano;
      const id = g.id;
      g.movido = true;
      setEscena((e) => ({ ...e, elementos: e.elementos.map((x) => (x.id === id ? { ...x, rotacion: normalizar(grados) } : x)) }));
    }
  }

  function terminarGesto(ev: EventoPuntero<SVGSVGElement>) {
    const g = gesto.current;
    gesto.current = null;
    if (ev.currentTarget.hasPointerCapture(ev.pointerId)) ev.currentTarget.releasePointerCapture(ev.pointerId);
    if (!g) return;
    if (g.tipo === "lapiz") {
      const puntos = trazo;
      setTrazo(null);
      if (!puntos || puntos.length === 0) return;
      if (escenaActual.current.elementos.length >= MAX_ELEMENTOS) {
        notificar.error(`El croquis no puede tener más de ${MAX_ELEMENTOS} elementos.`);
        return;
      }
      const xs = puntos.map(([x]) => x);
      const ys = puntos.map(([, y]) => y);
      const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
      const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
      const relativos = (puntos.length === 1 ? [puntos[0], [puntos[0][0] + 0.1, puntos[0][1]]] : puntos).map(
        ([x, y]) => [Math.round((x - cx) * 10) / 10, Math.round((y - cy) * 10) / 10] as [number, number],
      );
      const nuevo = nuevoElemento("lapiz", Math.round(cx * 10) / 10, Math.round(cy * 10) / 10, {
        puntos: relativos,
        color: colorTrazo,
      });
      cambiar((e) => ({ ...e, elementos: [...e.elementos, nuevo] }));
      return;
    }
    if ((g.tipo === "mover" || g.tipo === "rotar") && g.movido) registrar(g.antes);
  }


  // ----------------------------------------------------------- Teclado

  function alPulsarTecla(ev: EventoTeclado<HTMLDivElement>) {
    const destino = ev.target as HTMLElement;
    if (destino.closest("input, textarea, select")) return;
    const comando = ev.ctrlKey || ev.metaKey;
    const tecla = ev.key.toLowerCase();
    if (comando && tecla === "z") {
      ev.preventDefault();
      if (ev.shiftKey) rehacer();
      else deshacer();
    } else if (comando && tecla === "y") {
      ev.preventDefault();
      rehacer();
    } else if (comando && tecla === "d" && elegido) {
      ev.preventDefault();
      duplicar();
    } else if ((tecla === "delete" || tecla === "backspace") && elegido && !destino.closest("button")) {
      ev.preventDefault();
      borrar();
    } else if (tecla === "escape" && elegido) {
      ev.preventDefault();
      ev.stopPropagation();
      setSeleccion(null);
    } else if (elegido && tecla === "r" && !comando) {
      ev.preventDefault();
      actualizar(elegido.id, { rotacion: normalizar((elegido.rotacion ?? 0) + (ev.shiftKey ? -15 : 15)) });
    } else if (elegido && ["arrowleft", "arrowright", "arrowup", "arrowdown"].includes(tecla) && !destino.closest("button")) {
      ev.preventDefault();
      const paso = ev.shiftKey ? 1 : 10;
      const dx = tecla === "arrowleft" ? -paso : tecla === "arrowright" ? paso : 0;
      const dy = tecla === "arrowup" ? -paso : tecla === "arrowdown" ? paso : 0;
      actualizar(elegido.id, { x: elegido.x + dx, y: elegido.y + dy });
    }
  }

  // ----------------------------------------------------------- Dibujo

  const seleccionado = elegido ? mitadDeElemento(elegido) : null;
  const factor = elegido?.escala ?? 1;
  const ayudaHerramienta =
    herramienta === "lapiz"
      ? "Lápiz: dibujá sobre el croquis con el mouse, el dedo o un stylus."
      : herramienta === "mano"
        ? "Mano: arrastrá para mover la vista cuando está ampliada."
        : "Tocá un elemento para moverlo; con el círculo verde lo rotás.";

  return (
    <div className="editor-croquis" onKeyDown={alPulsarTecla}>
      <div className="editor-barra" role="toolbar" aria-label="Herramientas del croquis">
        <div className="editor-grupo" role="group" aria-label="Herramienta">
          {(
            [
              ["seleccionar", "Seleccionar"],
              ["lapiz", "Lápiz"],
              ["mano", "Mano"],
            ] as [Herramienta, string][]
          ).map(([valor, texto]) => (
            <button
              key={valor}
              type="button"
              className={`boton boton-chico${herramienta === valor ? " boton-activo" : ""}`}
              aria-pressed={herramienta === valor}
              onClick={() => setHerramienta(valor)}
            >
              {texto}
            </button>
          ))}
        </div>
        <div className="editor-grupo" role="group" aria-label="Historial">
          <button type="button" className="boton boton-chico" onClick={deshacer} disabled={pasado.length === 0} title="Deshacer (Ctrl+Z)">
            Deshacer
          </button>
          <button type="button" className="boton boton-chico" onClick={rehacer} disabled={futuro.length === 0} title="Rehacer (Ctrl+Mayús+Z)">
            Rehacer
          </button>
          <button type="button" className="boton boton-chico boton-peligro" onClick={() => void limpiar()} disabled={escena.elementos.length === 0}>
            Limpiar
          </button>
        </div>
        <div className="editor-grupo" role="group" aria-label="Vista">
          <label className="casilla">
            <input type="checkbox" checked={escena.cuadricula} onChange={(e) => cambiar((s) => ({ ...s, cuadricula: e.target.checked }))} />
            Cuadrícula
          </label>
          <label className="casilla">
            <input type="checkbox" checked={escena.leyenda} onChange={(e) => cambiar((s) => ({ ...s, leyenda: e.target.checked }))} />
            Referencias
          </label>
          <label className="casilla">
            <input type="checkbox" checked={escena.norte} onChange={(e) => cambiar((s) => ({ ...s, norte: e.target.checked }))} />
            Norte
          </label>
          <button type="button" className="boton boton-chico" onClick={() => setVista((v) => Math.max(1, v - 0.5))} disabled={vista <= 1} aria-label="Alejar la vista">
            −
          </button>
          <span className="editor-zoom" aria-live="polite">
            {Math.round(vista * 100)} %
          </span>
          <button type="button" className="boton boton-chico" onClick={() => setVista((v) => Math.min(3, v + 0.5))} disabled={vista >= 3} aria-label="Acercar la vista">
            +
          </button>
        </div>
      </div>

      <div className="editor-cuerpo">
        <nav className="editor-paleta" aria-label="Paleta de elementos">
          {PALETA.map((grupo) => (
            <div key={grupo.grupo} className="paleta-grupo">
              <div className="paleta-titulo">{grupo.grupo}</div>
              <div className="paleta-items">
                {grupo.items.map((item) => (
                  <button key={item.clave} type="button" className="paleta-item" onClick={() => agregar(item)} title={`Agregar: ${item.texto}`}>
                    <IconoElemento e={nuevoElemento(item.tipo, 0, 0, item.extra)} />
                    <span>{item.texto}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="editor-lienzo">
          <div
            ref={marco}
            className={`editor-marco editor-marco-${herramienta}`}
            tabIndex={0}
            aria-label="Lienzo del croquis. Con un elemento elegido: flechas para moverlo, R para rotarlo, Suprimir para borrarlo."
          >
            <svg
              ref={svgRef}
              className="editor-svg"
              viewBox={`0 0 ${escena.ancho} ${escena.alto}`}
              style={{ width: `${vista * 100}%` }}
              role="img"
              aria-label={`Croquis con ${escena.elementos.length} ${escena.elementos.length === 1 ? "elemento" : "elementos"}`}
              onPointerDown={alBajarPuntero}
              onPointerMove={alMoverPuntero}
              onPointerUp={terminarGesto}
              onPointerCancel={terminarGesto}
            >
              <EscenaSvg escena={escena} />
              <g data-solo-editor="true">
                {trazo ? (
                  <polyline
                    points={trazo.map(([x, y]) => `${x},${y}`).join(" ")}
                    fill="none"
                    stroke={colorTrazo}
                    strokeWidth={4}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                ) : null}
                {elegido && seleccionado ? (
                  <g transform={`translate(${elegido.x} ${elegido.y}) rotate(${elegido.rotacion ?? 0})`}>
                    <rect
                      x={-seleccionado.w * factor - 5}
                      y={-seleccionado.h * factor - 5}
                      width={seleccionado.w * factor * 2 + 10}
                      height={seleccionado.h * factor * 2 + 10}
                      fill="none"
                      stroke="#2f6f62"
                      strokeWidth={2}
                      strokeDasharray="7 5"
                      pointerEvents="none"
                    />
                    <line x1={0} y1={-seleccionado.h * factor - 5} x2={0} y2={-seleccionado.h * factor - 32} stroke="#2f6f62" strokeWidth={2} pointerEvents="none" />
                    <g data-rotar="true" className="editor-asa">
                      <circle cx={0} cy={-seleccionado.h * factor - 38} r={22} fill="transparent" />
                      <circle cx={0} cy={-seleccionado.h * factor - 38} r={10} fill="#ffffff" stroke="#2f6f62" strokeWidth={3} />
                    </g>
                  </g>
                ) : null}
              </g>
            </svg>
          </div>
          <p className="nota-pequena editor-ayuda">{ayudaHerramienta}</p>
        </div>

        <aside className="editor-propiedades" aria-label="Propiedades">
          {herramienta === "lapiz" ? (
            <div className="propiedad">
              <h3>Lápiz</h3>
              <div className="propiedad-titulo">Color del trazo</div>
              <Colores actual={colorTrazo} alElegir={setColorTrazo} />
            </div>
          ) : null}
          {elegido ? (
            <>
              <div className="propiedad">
                <h3>
                  {NOMBRE_TIPO[elegido.tipo]}
                  {elegido.tipo === "vehiculo" && elegido.etiqueta ? ` ${elegido.etiqueta}` : ""}
                </h3>
              </div>
              <div className="propiedad">
                <div className="propiedad-titulo">Rotación</div>
                <div className="acciones">
                  <button type="button" className="boton boton-chico" aria-label="Rotar 15 grados a la izquierda" onClick={() => actualizar(elegido.id, { rotacion: normalizar((elegido.rotacion ?? 0) - 15) })}>
                    Girar −15°
                  </button>
                  <button type="button" className="boton boton-chico" aria-label="Rotar 15 grados a la derecha" onClick={() => actualizar(elegido.id, { rotacion: normalizar((elegido.rotacion ?? 0) + 15) })}>
                    Girar +15°
                  </button>
                  <label className="solo-lector" htmlFor="croquis-rotacion">
                    Rotación en grados
                  </label>
                  <input
                    id="croquis-rotacion"
                    className="entrada entrada-corta"
                    type="number"
                    min={-180}
                    max={180}
                    step={5}
                    value={Math.round(elegido.rotacion ?? 0)}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      if (Number.isFinite(v)) actualizar(elegido.id, { rotacion: normalizar(v) });
                    }}
                  />
                  <span className="nota-pequena">°</span>
                </div>
              </div>
              <div className="propiedad">
                <div className="propiedad-titulo">Tamaño</div>
                <div className="acciones">
                  <button type="button" className="boton boton-chico" aria-label="Achicar" onClick={() => actualizar(elegido.id, { escala: Math.max(0.3, Math.round((factor - 0.1) * 100) / 100) })}>
                    −
                  </button>
                  <span className="editor-zoom">{Math.round(factor * 100)} %</span>
                  <button type="button" className="boton boton-chico" aria-label="Agrandar" onClick={() => actualizar(elegido.id, { escala: Math.min(4, Math.round((factor + 0.1) * 100) / 100) })}>
                    +
                  </button>
                </div>
              </div>
              {elegido.tipo === "vehiculo" ? (
                <div className="propiedad">
                  <label className="propiedad-titulo" htmlFor="croquis-etiqueta">
                    Letra del vehículo
                  </label>
                  <input
                    id="croquis-etiqueta"
                    className="entrada entrada-corta"
                    maxLength={3}
                    value={elegido.etiqueta ?? ""}
                    onChange={(e) => {
                      const letra = e.target.value.toUpperCase();
                      actualizar(elegido.id, { etiqueta: letra, color: COLORES_VEHICULO[letra] ?? elegido.color ?? COLOR_VEHICULO_OTRO });
                    }}
                  />
                </div>
              ) : null}
              {elegido.tipo === "texto" ? (
                <div className="propiedad">
                  <label className="propiedad-titulo" htmlFor="croquis-texto">
                    Texto
                  </label>
                  <input
                    id="croquis-texto"
                    className="entrada"
                    maxLength={60}
                    value={elegido.texto ?? ""}
                    onChange={(e) => actualizar(elegido.id, { texto: e.target.value })}
                  />
                </div>
              ) : null}
              {TIPOS_CON_COLOR.includes(elegido.tipo) ? (
                <div className="propiedad">
                  <div className="propiedad-titulo">Color</div>
                  <Colores actual={elegido.color ?? COLORES_PALETA[0]} alElegir={(c) => actualizar(elegido.id, { color: c })} />
                </div>
              ) : null}
              <div className="propiedad acciones">
                <button type="button" className="boton boton-chico" onClick={duplicar}>
                  Duplicar
                </button>
                <button type="button" className="boton boton-chico" onClick={() => ordenar(true)}>
                  Al frente
                </button>
                <button type="button" className="boton boton-chico" onClick={() => ordenar(false)}>
                  Al fondo
                </button>
                <button type="button" className="boton boton-chico boton-peligro" onClick={borrar}>
                  Eliminar
                </button>
              </div>
            </>
          ) : herramienta !== "lapiz" ? (
            <div className="propiedad">
              <h3>Cómo se usa</h3>
              <ul className="lista-simple nota-pequena">
                <li>Tocá un elemento de la paleta para sumarlo al croquis.</li>
                <li>Arrastralo para moverlo y usá el círculo verde para rotarlo.</li>
                <li>Armá las calles primero y después los vehículos, las personas y las flechas de sentido.</li>
                <li>Marcá el punto de impacto y escribí las referencias con «Texto».</li>
              </ul>
            </div>
          ) : null}
          <details className="propiedad editor-atajos">
            <summary>Atajos de teclado</summary>
            <ul className="lista-simple nota-pequena">
              <li>Ctrl+Z / Ctrl+Mayús+Z: deshacer y rehacer</li>
              <li>Ctrl+D: duplicar · Suprimir: eliminar</li>
              <li>Flechas: mover (Mayús para ir de a 1) · R: rotar 15°</li>
              <li>Esc: soltar la selección</li>
            </ul>
          </details>
        </aside>
      </div>
    </div>
  );
}

function Colores({ actual, alElegir }: { actual: string; alElegir: (color: string) => void }) {
  return (
    <div className="colores" role="group" aria-label="Colores">
      {COLORES_PALETA.map((c) => (
        <button
          key={c}
          type="button"
          className={`color-muestra${actual === c ? " color-muestra-activo" : ""}`}
          style={{ background: c }}
          aria-label={`Color ${c}`}
          aria-pressed={actual === c}
          onClick={() => alElegir(c)}
        />
      ))}
    </div>
  );
}
