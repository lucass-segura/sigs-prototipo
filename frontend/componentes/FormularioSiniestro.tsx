"use client";

// Registro y edición de borradores (HU-03) con confirmación inmediata (HU-04), como asistente de cinco pasos (S33):
// 1 Póliza · 2 Hecho y denuncia · 3 Personas · 4 Bienes · 5 Revisar y confirmar.
// Todo lo cargado vive acá, por encima de los pasos, y se guarda en sessionStorage (por usuario y por borrador).
import { Fragment, useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ErrorApi, api } from "@/lib/api";
import {
  PASOS,
  armarCuerpo,
  bienVacio,
  claveAlmacen,
  datosIniciales,
  deserializar,
  idControlDeRuta,
  indiceDePaso,
  nombreDePaso,
  nuevaClave,
  pasoDeRuta,
  pasosConAvisos,
  pasosConError,
  personaVacia,
  primerPasoConError,
  reducirDatos,
  requisitosParaConfirmar,
  serializar,
  validarPaso,
} from "@/lib/asistenteSiniestro";
import type { Accion, DatosSiniestro, IdPaso } from "@/lib/asistenteSiniestro";
import { separarFechaHora } from "@/lib/fechas";
import { aInputFecha, aInputFechaHora, aInputHora } from "@/lib/formato";
import { useSesion } from "@/lib/sesion";
import type { Siniestro } from "@/lib/tipos";
import { useApi } from "@/lib/useApi";
import { ErrorFormulario } from "./Avisos";
import { useConfirmar } from "./Confirmar";
import { Cargando, ErrorCarga } from "./Estados";
import { useNotificar } from "./Notificaciones";
import { EncabezadoPagina, Vista } from "./Vista";
import { IndicadorPasos } from "./asistente/IndicadorPasos";
import { Paso } from "./asistente/Paso";
import { PasoBienes } from "./asistente/PasoBienes";
import { MENSAJE_FECHA_HECHO_REQUERIDA, MENSAJE_HORA_HECHO_REQUERIDA, PasoHecho } from "./asistente/PasoHecho";
import { PasoPersonas } from "./asistente/PasoPersonas";
import { PasoPoliza } from "./asistente/PasoPoliza";
import { PasoRevision } from "./asistente/PasoRevision";
import type { PropsPaso } from "./asistente/tipos";
import { useValidezFechas } from "./fechas/useValidezFechas";

/** Paso donde está cada selector de fecha u hora. */
const PASO_DE_SELECTOR: Record<string, IdPaso> = {
  "inicio-vigencia": "poliza",
  "primer-pago": "poliza",
  "fecha-hecho": "hecho",
  "hora-hecho": "hecho",
  "fecha-denuncia": "hecho",
  "hora-denuncia": "hecho",
};

/** Un obligatorio vacío es un dato que falta (se puede seguir); cualquier otro mensaje es un valor que no se puede enviar. */
const MENSAJE_DE_FALTANTE: Record<string, string> = {
  "fecha-hecho": MENSAJE_FECHA_HECHO_REQUERIDA,
  "hora-hecho": MENSAJE_HORA_HECHO_REQUERIDA,
};

const PASOS_CON_DATOS: IdPaso[] = ["poliza", "hecho", "personas", "bienes"];

const sinRevisiones = (): Record<IdPaso, number> => ({ poliza: 0, hecho: 0, personas: 0, bienes: 0, revision: 0 });

const revisionesDe = (pasos: readonly IdPaso[]): Record<IdPaso, number> => {
  const r = sinRevisiones();
  for (const p of pasos) r[p] = 1;
  return r;
};

/** Datos de un borrador que ya está en el servidor. */
function precargar(s: Siniestro): DatosSiniestro {
  const hecho = separarFechaHora(aInputFechaHora(s.fecha_hecho));
  return {
    compania: s.poliza?.compania ?? "",
    numeroPoliza: s.poliza?.numero ?? "",
    cobertura: s.poliza?.cobertura ?? "",
    inicioVigencia: aInputFecha(s.poliza?.inicio_vigencia),
    primerPago: aInputFecha(s.poliza?.primer_pago),
    tipo: s.tipo,
    fechaHecho: hecho.fecha,
    horaHecho: hecho.hora,
    fechaDenuncia: aInputFecha(s.fecha_denuncia),
    horaDenuncia: aInputHora(s.hora_denuncia),
    numeroDenuncia: s.numero_denuncia ?? "",
    asesor: s.asesor ?? "",
    intervenciones: s.intervenciones ?? "",
    documentacionAdjunta: s.documentacion_adjunta ?? "",
    lugar: s.lugar ?? "",
    relato: s.relato ?? "",
    personas: s.personas.length
      ? s.personas.map((p) => ({
          clave: nuevaClave(),
          tipo_identificador: p.tipo_identificador,
          identificador: p.identificador,
          nombre: p.nombre,
          roles: p.roles,
        }))
      : [personaVacia()],
    bienes: s.bienes.length
      ? s.bienes.map((b) => ({
          clave: nuevaClave(),
          tipo: b.tipo,
          identificador: b.identificador_norm ?? b.identificador ?? "",
          descripcion: b.descripcion ?? "",
          detalle_dano: b.detalle_dano ?? "",
          motor: typeof b.atributos?.motor === "string" ? b.atributos.motor : "",
          chasis: typeof b.atributos?.chasis === "string" ? b.atributos.chasis : "",
        }))
      : [bienVacio()],
  };
}

/** El primero en el orden de la pantalla. */
function primeroEnPantalla(ids: string[]): string | null {
  const elementos = ids.map((id) => document.getElementById(id)).filter((el): el is HTMLElement => el !== null);
  elementos.sort((a, b) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1));
  return elementos[0]?.id ?? ids[0] ?? null;
}

const leerAlmacen = (clave: string): string | null => {
  try {
    return window.sessionStorage.getItem(clave);
  } catch {
    return null;
  }
};

export function FormularioSiniestro({ idBorrador }: { idBorrador: number | null }) {
  const router = useRouter();
  const { usuario } = useSesion();
  const confirmarAccion = useConfirmar();
  const notificar = useNotificar();
  const edicion = useApi<Siniestro>(idBorrador ? `/siniestros/${idBorrador}` : null);
  const clave = usuario ? claveAlmacen(usuario.id, idBorrador) : null;

  const [datos, despachar] = useReducer(reducirDatos, undefined, datosIniciales);
  const [paso, setPaso] = useState<IdPaso>("poliza");
  const [visitados, setVisitados] = useState<IdPaso[]>([]);
  const [revisiones, setRevisiones] = useState<Record<IdPaso, number>>(sinRevisiones);
  const [hidratado, setHidratado] = useState(false);
  const [tocado, setTocado] = useState(false);
  const [recuperado, setRecuperado] = useState(false);
  const [generacion, setGeneracion] = useState(0);
  const [error, setError] = useState<unknown>(null);
  const [errorDeFechas, setErrorDeFechas] = useState(false);
  // Pasos que se tocaron después del último error de la API: sus errores ya no valen.
  const [editados, setEditados] = useState<IdPaso[]>([]);
  const [enviando, setEnviando] = useState<null | "borrador" | "confirmar">(null);
  const [anuncio, setAnuncio] = useState("");
  const [foco, setFoco] = useState<{ id: string | null; n: number }>({ id: null, n: 0 });
  const validez = useValidezFechas();
  const inicializado = useRef(false);
  const sinPersistir = useRef(false);

  // El aviso general de fechas se va solo cuando ya no queda ningún selector marcado.
  useEffect(() => {
    if (errorDeFechas && !validez.hayInvalidos) {
      setError(null);
      setErrorDeFechas(false);
    }
  }, [errorDeFechas, validez.hayInvalidos]);

  // Carga inicial, una sola vez: lo que quedó guardado en esta pestaña gana; si no, el borrador del servidor.
  useEffect(() => {
    if (inicializado.current || !clave) return;
    if (idBorrador && !edicion.datos) return;
    const s = edicion.datos;
    if (s && (s.estado !== "borrador" || !s.es_responsable)) return;
    inicializado.current = true;
    const guardado = deserializar(leerAlmacen(clave));
    if (guardado) {
      despachar({ tipo: "reemplazar", datos: guardado.datos });
      setPaso(guardado.paso);
      setVisitados(guardado.visitados);
      setRevisiones(revisionesDe(guardado.visitados));
      setTocado(true);
      setRecuperado(true);
    } else if (s) {
      despachar({ tipo: "reemplazar", datos: precargar(s) });
      setVisitados(PASOS_CON_DATOS);
      setRevisiones(revisionesDe(PASOS_CON_DATOS));
    }
    setHidratado(true);
  }, [clave, idBorrador, edicion.datos]);

  // Cada cambio se guarda en sessionStorage (solo de esta pestaña; nunca en localStorage).
  useEffect(() => {
    if (!hidratado || !tocado || !clave || sinPersistir.current) return;
    try {
      window.sessionStorage.setItem(clave, serializar({ datos, paso, visitados }));
    } catch {
      // Sin espacio o sin sessionStorage: el formulario sigue funcionando, solo que no sobrevive a recargar.
    }
  }, [hidratado, tocado, clave, datos, paso, visitados]);

  // El foco va al título del paso (o al campo con error) cada vez que se navega.
  useEffect(() => {
    if (foco.n === 0) return;
    const destino = (foco.id && document.getElementById(foco.id)) || document.getElementById(`titulo-paso-${paso}`);
    destino?.focus();
  }, [foco, paso]);

  const cambiar = useCallback(
    (accion: Accion) => {
      despachar(accion);
      setTocado(true);
      setRecuperado(false);
      setEditados((e) => (e.includes(paso) ? e : [...e, paso]));
    },
    [paso],
  );

  // ---------------------------------------------------------------- Errores y avisos de cada paso

  const camposApi = useMemo(() => {
    const todos = error instanceof ErrorApi ? error.campos : [];
    return todos.filter((c) => {
      const dueno = pasoDeRuta(c.ruta);
      return !(dueno && editados.includes(dueno));
    });
  }, [error, editados]);

  const errorVigente = useMemo(() => {
    if (!(error instanceof ErrorApi)) return error;
    return error.detalle || camposApi.length > 0 ? new ErrorApi(error.estado, error.detalle, camposApi) : null;
  }, [error, camposApi]);

  // La validación suave de un paso se muestra una vez que se pasó por él.
  const avisos = useMemo(() => {
    const todos: Record<string, string> = {};
    for (const p of PASOS) if (visitados.includes(p.id)) Object.assign(todos, validarPaso(datos, p.id));
    return todos;
  }, [datos, visitados]);

  const mensajes = useCallback(
    (id: string, ruta?: string): string[] => {
      const deApi = ruta ? camposApi.filter((c) => c.ruta === ruta || c.ruta.startsWith(`${ruta}.`)).map((c) => c.mensaje) : [];
      return [...new Set([...deApi, ...(avisos[id] ? [avisos[id]] : [])])];
    },
    [camposApi, avisos],
  );

  const conError = useMemo(() => {
    const pasos = new Set<IdPaso>(pasosConError(camposApi.map((c) => c.ruta)));
    for (const id of Object.keys(validez.invalidos)) {
      const dueno = PASO_DE_SELECTOR[id];
      if (dueno && visitados.includes(dueno)) pasos.add(dueno);
    }
    for (const p of pasosConAvisos(datos)) if (visitados.includes(p)) pasos.add(p);
    return pasos;
  }, [camposApi, validez.invalidos, visitados, datos]);

  const requisitos = useMemo(() => requisitosParaConfirmar(datos), [datos]);

  const selector = useCallback(
    (id: string) => ({ ...validez.props(id), revision: revisiones[PASO_DE_SELECTOR[id]] }),
    [validez, revisiones],
  );

  // ---------------------------------------------------------------- Navegación

  function marcarRevisados(pasos: IdPaso[]) {
    setVisitados((v) => [...v, ...pasos.filter((p) => !v.includes(p))]);
    setRevisiones((r) => {
      const siguiente = { ...r };
      for (const p of pasos) siguiente[p] += 1;
      return siguiente;
    });
  }

  function pedirFoco(id: string | null) {
    setFoco((f) => ({ id, n: f.n + 1 }));
  }

  function tieneProblemas(p: IdPaso): boolean {
    return (
      Object.keys(validarPaso(datos, p)).length > 0 || Object.keys(validez.invalidos).some((id) => PASO_DE_SELECTOR[id] === p)
    );
  }

  function irA(destino: IdPaso, idCampo: string | null = null) {
    if (destino !== paso) {
      marcarRevisados([paso]);
      setTocado(true);
      setAnuncio(tieneProblemas(paso) ? `El paso «${nombreDePaso(paso)}» tiene datos para revisar.` : "");
    }
    setPaso(destino);
    pedirFoco(idCampo);
  }

  function siguiente() {
    // Un valor que no se puede leer (por ejemplo una fecha a medio escribir) frena; lo que falta no.
    const ilegibles = Object.keys(validez.invalidos).filter(
      (id) => PASO_DE_SELECTOR[id] === paso && validez.invalidos[id] !== MENSAJE_DE_FALTANTE[id],
    );
    if (ilegibles.length > 0) {
      marcarRevisados([paso]);
      pedirFoco(primeroEnPantalla(ilegibles));
      return;
    }
    irA(PASOS[indiceDePaso(paso) + 1].id);
  }

  function anterior() {
    irA(PASOS[indiceDePaso(paso) - 1].id);
  }

  // ---------------------------------------------------------------- Guardar, confirmar y descartar

  async function guardar(confirmar: boolean) {
    setError(null);
    setErrorDeFechas(false);
    setEditados([]);
    // Un selector con una fecha u hora que no se puede enviar se marca y no se manda nada.
    const invalidos = Object.keys(validez.invalidos);
    if (invalidos.length > 0) {
      const afectados = PASOS.map((p) => p.id).filter((id) => invalidos.some((i) => PASO_DE_SELECTOR[i] === id));
      marcarRevisados(afectados);
      const destino = afectados[0] ?? paso;
      irA(destino, primeroEnPantalla(invalidos.filter((i) => PASO_DE_SELECTOR[i] === destino)));
      setError(new ErrorApi(400, "Revisá las fechas y horas marcadas en rojo antes de guardar.", []));
      setErrorDeFechas(true);
      return;
    }
    setEnviando(confirmar ? "confirmar" : "borrador");
    try {
      const cuerpo = armarCuerpo(datos);
      let id: number;
      if (idBorrador) {
        await api<Siniestro>(`/siniestros/${idBorrador}`, { metodo: "PATCH", cuerpo });
        id = idBorrador;
        if (confirmar) await api<Siniestro>(`/siniestros/${id}/confirmar`, { metodo: "POST", cuerpo: {} });
      } else {
        const creado = await api<Siniestro>("/siniestros", { cuerpo: { ...cuerpo, confirmar } });
        id = creado.id;
      }
      // Ya está guardado en el servidor: lo que quedaba en esta pestaña se borra.
      sinPersistir.current = true;
      if (clave) {
        try {
          window.sessionStorage.removeItem(clave);
        } catch {
          // Nada que borrar.
        }
      }
      router.push(`/expedientes/${id}?tab=${confirmar ? "analisis" : "datos"}`);
    } catch (e) {
      setError(e);
      setEnviando(null);
      // Un error de un campo lleva al paso que lo tiene y le da el foco.
      if (e instanceof ErrorApi) {
        const rutas = e.campos.map((c) => c.ruta);
        const destino = primerPasoConError(rutas);
        if (destino) {
          marcarRevisados(pasosConError(rutas));
          const primera = e.campos.find((c) => pasoDeRuta(c.ruta) === destino);
          irA(destino, primera ? idControlDeRuta(primera.ruta, datos) : null);
        }
      }
    }
  }

  async function descartar() {
    const seguro = await confirmarAccion({
      titulo: "¿Descartar lo cargado?",
      mensaje: idBorrador
        ? "Se borran los cambios que hiciste en esta pantalla y el borrador vuelve a quedar como lo guardaste."
        : "Se borra todo lo que cargaste en este formulario. No se puede deshacer.",
      confirmar: "Descartar",
      peligro: true,
    });
    if (!seguro) return;
    if (clave) {
      try {
        window.sessionStorage.removeItem(clave);
      } catch {
        // Nada que borrar.
      }
    }
    const s = idBorrador ? edicion.datos : null;
    despachar({ tipo: "reemplazar", datos: s ? precargar(s) : datosIniciales() });
    setPaso("poliza");
    setVisitados(s ? PASOS_CON_DATOS : []);
    setRevisiones(s ? revisionesDe(PASOS_CON_DATOS) : sinRevisiones());
    setTocado(false);
    setRecuperado(false);
    setError(null);
    setErrorDeFechas(false);
    setEditados([]);
    setAnuncio("");
    setGeneracion((g) => g + 1);
    pedirFoco(null);
    notificar.info("Descartaste lo cargado.");
  }

  // ---------------------------------------------------------------- Pantalla

  const titulo = idBorrador ? "Editar borrador" : "Registrar siniestro";
  const migas = idBorrador
    ? [{ texto: "Expedientes", href: "/expedientes" }, { texto: "Editar borrador" }]
    : [{ texto: "Expedientes", href: "/expedientes" }, { texto: "Nuevo siniestro" }];

  if (idBorrador && edicion.cargando) {
    return (
      <Vista migas={migas}>
        <Cargando />
      </Vista>
    );
  }
  if (idBorrador && edicion.error) {
    return (
      <Vista migas={migas}>
        <ErrorCarga error={edicion.error} />
      </Vista>
    );
  }
  if (idBorrador && edicion.datos && (edicion.datos.estado !== "borrador" || !edicion.datos.es_responsable)) {
    return (
      <Vista migas={migas}>
        <div className="aviso aviso-error" role="alert">
          <p>Solo el perito responsable puede editar un expediente en borrador.</p>
        </div>
      </Vista>
    );
  }

  const propsPaso: PropsPaso = { datos, cambiar, mensajes, selector };
  const indice = indiceDePaso(paso);

  return (
    <Vista migas={migas}>
      <EncabezadoPagina
        titulo={titulo}
        subtitulo="Los datos quedan en borrador hasta que confirmes. Solo un siniestro confirmado se analiza."
      />
      {!hidratado ? (
        <Cargando />
      ) : (
        <>
          <IndicadorPasos actual={paso} visitados={visitados} conError={conError} alElegir={(destino) => irA(destino)} />
          {recuperado ? (
            <div className="aviso aviso-verde" role="status">
              <p>Recuperamos lo que habías cargado en esta pestaña.</p>
            </div>
          ) : null}
          <div className="rejilla rejilla-principal">
            <div className="columna">
              <Fragment key={generacion}>
                <Paso id="poliza" activo={paso === "poliza"}>
                  <PasoPoliza {...propsPaso} />
                </Paso>
                <Paso id="hecho" activo={paso === "hecho"}>
                  <PasoHecho {...propsPaso} />
                </Paso>
                <Paso
                  id="personas"
                  activo={paso === "personas"}
                  accion={
                    <button type="button" className="boton boton-chico" onClick={() => cambiar({ tipo: "persona/agregar", clave: nuevaClave() })}>
                      Agregar
                    </button>
                  }
                >
                  <PasoPersonas {...propsPaso} />
                </Paso>
                <Paso
                  id="bienes"
                  activo={paso === "bienes"}
                  accion={
                    <button type="button" className="boton boton-chico" onClick={() => cambiar({ tipo: "bien/agregar", clave: nuevaClave() })}>
                      Agregar
                    </button>
                  }
                >
                  <PasoBienes {...propsPaso} />
                </Paso>
                <Paso id="revision" activo={paso === "revision"}>
                  <PasoRevision
                    datos={datos}
                    requisitos={requisitos}
                    pasosConError={PASOS.map((p) => p.id).filter((id) => conError.has(id))}
                    ir={(destino) => irA(destino)}
                    confirmar={() => void guardar(true)}
                    enviando={enviando === "confirmar"}
                  />
                </Paso>
              </Fragment>

              <ErrorFormulario error={errorVigente} />

              <div className="asistente-pie">
                <div>
                  {indice > 0 ? (
                    <button
                      type="button"
                      className="boton"
                      aria-label={`Anterior: ${PASOS[indice - 1].nombre}`}
                      disabled={enviando !== null}
                      onClick={anterior}
                    >
                      Anterior
                    </button>
                  ) : null}
                </div>
                <div className="asistente-pie-derecha">
                  <button type="button" className="boton" disabled={enviando !== null} onClick={() => void guardar(false)}>
                    {enviando === "borrador" ? "Guardando…" : "Guardar borrador"}
                  </button>
                  {paso !== "revision" ? (
                    <button
                      type="button"
                      className="boton boton-principal"
                      aria-label={`Siguiente: ${PASOS[indice + 1].nombre}`}
                      disabled={enviando !== null}
                      onClick={siguiente}
                    >
                      Siguiente
                    </button>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="columna">
              <section className="tarjeta">
                <div className="tarjeta-cuerpo">
                  <h3>Antes de confirmar</h3>
                  <p className="subtitulo">
                    Revisá que el identificador de cada persona y bien sea exacto. Un nombre parecido no alcanza para encontrar
                    antecedentes.
                  </p>
                  <p className="nota-pequena">
                    Lo que cargás se conserva si recargás la página, mientras no cierres la pestaña ni salgas del sistema.
                  </p>
                  <button type="button" className="boton boton-ancho boton-peligro" disabled={enviando !== null} onClick={() => void descartar()}>
                    Descartar
                  </button>
                </div>
              </section>
            </div>
          </div>
        </>
      )}
      <span className="solo-lectores" role="status" aria-live="polite">
        {anuncio}
      </span>
    </Vista>
  );
}
