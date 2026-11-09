"use client";

// Lógica común de los campos escritos a mano (fecha y hora): texto con máscara, valor que se envía,
// cuándo mostrar un error y qué se anuncia al lector de pantalla.
import { useEffect, useRef, useState } from "react";
import type { FocusEvent } from "react";
import type { EvaluacionCampo } from "@/lib/fechas";

export interface OpcionesCampo {
  /** Valor que maneja el formulario (`AAAA-MM-DD` / `HH:MM`, o vacío). */
  valor: string;
  onCambio: (valor: string) => void;
  /** Lee el texto contra los límites vigentes. */
  evaluar: (texto: string) => EvaluacionCampo;
  /** Cambia cuando cambian los límites (para volver a evaluar lo ya escrito). */
  contexto: string;
  formatear: (valor: string) => string;
  mascara: (texto: string) => string;
  /** Texto completo (con todas sus cifras) a partir del cual un error ya se muestra sin esperar. */
  largoCompleto: number;
  requerido: boolean;
  mensajeRequerido: string;
  revision: number;
  onInvalido?: (mensaje: string | null) => void;
  /** Frase para el lector de pantalla cuando el valor queda elegido. */
  anunciar: (valor: string) => string;
}

export function useCampoEscrito(o: OpcionesCampo) {
  const [texto, setTexto] = useState(() => o.formatear(o.valor));
  const [enfocado, setEnfocado] = useState(false);
  const [tocado, setTocado] = useState(false);
  const [forzado, setForzado] = useState(false);
  const [anuncio, setAnuncio] = useState("");

  // Lo último que dijo el padre, para distinguir un cambio de afuera de uno propio.
  const previo = useRef(o.valor);
  const ultimoAnunciado = useRef(o.valor);
  const evaluarRef = useRef(o.evaluar);
  evaluarRef.current = o.evaluar;
  const cambioRef = useRef(o.onCambio);
  cambioRef.current = o.onCambio;
  const formatearRef = useRef(o.formatear);
  formatearRef.current = o.formatear;

  const evaluacion = o.evaluar(texto);

  useEffect(() => {
    const esperado = evaluarRef.current(texto).valor;
    if (o.valor !== previo.current) {
      previo.current = o.valor;
      // Cambio de afuera (por ejemplo, se cargó un borrador): el texto lo sigue.
      if (o.valor !== esperado) setTexto(formatearRef.current(o.valor));
      return;
    }
    // Los límites cambiaron y lo escrito dejó de valer (o volvió a valer).
    if (esperado !== o.valor) cambioRef.current(esperado);
  }, [o.valor, texto, o.contexto]);

  // «Obligatorio y vacío» o «escrito pero no válido»: el formulario lo usa para no enviar.
  const invalido =
    evaluacion.estado === "error" || evaluacion.estado === "incompleto"
      ? evaluacion.mensaje
      : evaluacion.estado === "vacio" && o.requerido
        ? o.mensajeRequerido
        : null;

  const informar = o.onInvalido;
  useEffect(() => {
    informar?.(invalido);
  }, [informar, invalido]);

  useEffect(() => {
    if (o.revision > 0) setForzado(true);
  }, [o.revision]);

  const mostrar =
    forzado ||
    (!enfocado && tocado) ||
    (evaluacion.estado === "error" && texto.length >= o.largoCompleto);
  const mensaje = mostrar && invalido ? invalido : "";

  function anunciarValor(valor: string) {
    if (valor === ultimoAnunciado.current) return;
    ultimoAnunciado.current = valor;
    setAnuncio(valor ? o.anunciar(valor) : "Se borró el valor.");
  }

  function alEscribir(crudo: string) {
    const t = o.mascara(crudo);
    setTexto(t);
    setForzado(false);
    const { valor } = o.evaluar(t);
    if (valor !== o.valor) o.onCambio(valor);
  }

  /** Se eligió un valor desde el calendario o el reloj (o se borró). */
  function elegir(valor: string) {
    setTexto(o.formatear(valor));
    setForzado(false);
    if (valor !== o.valor) o.onCambio(valor);
    anunciarValor(valor);
  }

  /** Al salir del cuadro de texto: queda en el formato completo (`12/8/26` → `12/08/2026`) y se anuncia el valor. */
  function normalizar() {
    const lectura = o.evaluar(texto);
    if (lectura.estado === "ok") {
      setTexto(o.formatear(lectura.valor));
      anunciarValor(lectura.valor);
    }
  }

  /** Al salir de todo el campo (texto y botones): se muestran los errores pendientes. */
  function alSalir(e: FocusEvent<HTMLElement>, ceder: HTMLElement | null) {
    if (ceder && e.relatedTarget instanceof Node && ceder.contains(e.relatedTarget)) return;
    setEnfocado(false);
    setTocado(true);
  }

  return {
    texto,
    evaluacion,
    invalido,
    mensaje,
    anuncio,
    elegir,
    alEscribir,
    alSalir,
    normalizar,
    alEntrar: () => setEnfocado(true),
    /** El selector se cerró sin devolver el foco al campo (clic afuera): se da el campo por abandonado. */
    salir: () => {
      setEnfocado(false);
      setTocado(true);
    },
  };
}
