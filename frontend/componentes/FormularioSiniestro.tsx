"use client";

// Registro y edición de borradores (HU-03) con confirmación inmediata (HU-04).
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, erroresDeCampo } from "@/lib/api";
import { aInputFecha, aInputFechaHora } from "@/lib/formato";
import {
  ETIQUETA_ROL_PERSONA,
  ETIQUETA_TIPO_BIEN,
  ROLES_PERSONA,
  TIPOS_BIEN,
  TIPOS_IDENTIFICADOR,
  TIPOS_SINIESTRO_SUGERIDOS,
} from "@/lib/etiquetas";
import type {
  BienSiniestro,
  CuerpoSiniestro,
  PersonaSiniestro,
  RolPersona,
  Siniestro,
  TipoBien,
  TipoIdentificador,
} from "@/lib/tipos";
import { useApi } from "@/lib/useApi";
import { Campo } from "./Campo";
import { AvisoVerde, ErrorFormulario } from "./Avisos";
import { Cargando, ErrorCarga } from "./Estados";
import { EncabezadoPagina, Vista } from "./Vista";

interface FilaPersona {
  clave: number;
  tipo_identificador: TipoIdentificador;
  identificador: string;
  nombre: string;
  roles: RolPersona[];
}

interface FilaBien {
  clave: number;
  tipo: TipoBien;
  identificador: string;
  descripcion: string;
  detalle_dano: string;
  motor: string;
  chasis: string;
}

let contadorClaves = 0;
const nuevaClave = () => ++contadorClaves;

const personaVacia = (): FilaPersona => ({
  clave: nuevaClave(),
  tipo_identificador: "DNI",
  identificador: "",
  nombre: "",
  roles: [],
});

const bienVacio = (): FilaBien => ({
  clave: nuevaClave(),
  tipo: "vehiculo",
  identificador: "",
  descripcion: "",
  detalle_dano: "",
  motor: "",
  chasis: "",
});

const tieneAtributosDeVehiculo = (tipo: TipoBien) => tipo === "vehiculo" || tipo === "motocicleta";

export function FormularioSiniestro({ idBorrador }: { idBorrador: number | null }) {
  const router = useRouter();
  const edicion = useApi<Siniestro>(idBorrador ? `/siniestros/${idBorrador}` : null);

  const [compania, setCompania] = useState("");
  const [numeroPoliza, setNumeroPoliza] = useState("");
  const [cobertura, setCobertura] = useState("");
  const [inicioVigencia, setInicioVigencia] = useState("");
  const [primerPago, setPrimerPago] = useState("");
  const [tipo, setTipo] = useState("");
  const [fechaHecho, setFechaHecho] = useState("");
  const [fechaDenuncia, setFechaDenuncia] = useState("");
  const [lugar, setLugar] = useState("");
  const [relato, setRelato] = useState("");
  const [personas, setPersonas] = useState<FilaPersona[]>(() => [personaVacia()]);
  const [bienes, setBienes] = useState<FilaBien[]>(() => [bienVacio()]);
  const [error, setError] = useState<unknown>(null);
  const [enviando, setEnviando] = useState<null | "borrador" | "confirmar">(null);
  const [precargado, setPrecargado] = useState(false);

  // Con un borrador existente se cargan sus datos una sola vez.
  useEffect(() => {
    const s = edicion.datos;
    if (!s || precargado) return;
    setPrecargado(true);
    setCompania(s.poliza?.compania ?? "");
    setNumeroPoliza(s.poliza?.numero ?? "");
    setCobertura(s.poliza?.cobertura ?? "");
    setInicioVigencia(aInputFecha(s.poliza?.inicio_vigencia));
    setPrimerPago(aInputFecha(s.poliza?.primer_pago));
    setTipo(s.tipo);
    setFechaHecho(aInputFechaHora(s.fecha_hecho));
    setFechaDenuncia(aInputFecha(s.fecha_denuncia));
    setLugar(s.lugar ?? "");
    setRelato(s.relato ?? "");
    setPersonas(
      s.personas.length
        ? s.personas.map((p) => ({
            clave: nuevaClave(),
            tipo_identificador: p.tipo_identificador,
            identificador: p.identificador,
            nombre: p.nombre,
            roles: p.roles,
          }))
        : [personaVacia()],
    );
    setBienes(
      s.bienes.length
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
    );
  }, [edicion.datos, precargado]);

  function armarCuerpo(): CuerpoSiniestro {
    const personasEnviadas: PersonaSiniestro[] = personas
      .filter((p) => p.identificador.trim() || p.nombre.trim() || p.roles.length)
      .map((p) => ({
        tipo_identificador: p.tipo_identificador,
        identificador: p.identificador.trim(),
        nombre: p.nombre.trim(),
        roles: p.roles,
      }));
    const bienesEnviados: BienSiniestro[] = bienes
      .filter((b) => b.identificador.trim() || b.descripcion.trim() || b.detalle_dano.trim())
      .map((b) => {
        const atributos: Record<string, string> = {};
        if (tieneAtributosDeVehiculo(b.tipo)) {
          if (b.motor.trim()) atributos.motor = b.motor.trim();
          if (b.chasis.trim()) atributos.chasis = b.chasis.trim();
        }
        return {
          tipo: b.tipo,
          identificador: b.identificador.trim(),
          descripcion: b.descripcion.trim(),
          detalle_dano: b.detalle_dano.trim(),
          atributos,
        };
      });
    return {
      poliza: {
        numero: numeroPoliza.trim(),
        compania: compania.trim(),
        cobertura: cobertura.trim(),
        inicio_vigencia: inicioVigencia || null,
        primer_pago: primerPago || null,
      },
      tipo: tipo.trim(),
      ...(fechaHecho ? { fecha_hecho: fechaHecho } : {}),
      fecha_denuncia: fechaDenuncia || null,
      lugar: lugar.trim(),
      relato: relato.trim(),
      personas: personasEnviadas,
      bienes: bienesEnviados,
    };
  }

  async function guardar(confirmar: boolean) {
    setError(null);
    setEnviando(confirmar ? "confirmar" : "borrador");
    try {
      const cuerpo = armarCuerpo();
      let id: number;
      if (idBorrador) {
        await api<Siniestro>(`/siniestros/${idBorrador}`, { metodo: "PATCH", cuerpo });
        id = idBorrador;
        if (confirmar) await api<Siniestro>(`/siniestros/${id}/confirmar`, { metodo: "POST", cuerpo: {} });
      } else {
        const creado = await api<Siniestro>("/siniestros", { cuerpo: { ...cuerpo, confirmar } });
        id = creado.id;
      }
      router.push(`/expedientes/${id}?tab=${confirmar ? "analisis" : "datos"}`);
    } catch (e) {
      setError(e);
      setEnviando(null);
    }
  }

  function actualizarPersona(clave: number, cambios: Partial<FilaPersona>) {
    setPersonas((filas) => filas.map((f) => (f.clave === clave ? { ...f, ...cambios } : f)));
  }

  function alternarRol(clave: number, rol: RolPersona) {
    setPersonas((filas) =>
      filas.map((f) =>
        f.clave === clave
          ? { ...f, roles: f.roles.includes(rol) ? f.roles.filter((r) => r !== rol) : [...f.roles, rol] }
          : f,
      ),
    );
  }

  function actualizarBien(clave: number, cambios: Partial<FilaBien>) {
    setBienes((filas) => filas.map((f) => (f.clave === clave ? { ...f, ...cambios } : f)));
  }

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

  return (
    <Vista migas={migas}>
      <EncabezadoPagina
        titulo={titulo}
        subtitulo="Los datos quedan en borrador hasta que confirmes. Solo un siniestro confirmado se analiza."
      />
      <div className="rejilla rejilla-principal">
        <div className="columna">
          <section className="tarjeta">
            <div className="tarjeta-cabecera">
              <h2>Póliza</h2>
            </div>
            <div className="tarjeta-cuerpo">
              <div className="rejilla-campos rejilla-auto">
                <Campo etiqueta="Compañía" id="compania" errores={erroresDeCampo(error, "poliza.compania")}>
                  <input id="compania" value={compania} onChange={(e) => setCompania(e.target.value)} />
                </Campo>
                <Campo etiqueta="Número de póliza" id="numero-poliza" errores={erroresDeCampo(error, "poliza.numero")}>
                  <input id="numero-poliza" value={numeroPoliza} onChange={(e) => setNumeroPoliza(e.target.value)} />
                </Campo>
                <Campo etiqueta="Cobertura" id="cobertura" errores={erroresDeCampo(error, "poliza.cobertura")}>
                  <input id="cobertura" value={cobertura} onChange={(e) => setCobertura(e.target.value)} />
                </Campo>
                <Campo etiqueta="Inicio de vigencia" id="inicio-vigencia" errores={erroresDeCampo(error, "poliza.inicio_vigencia")}>
                  <input id="inicio-vigencia" type="date" value={inicioVigencia} onChange={(e) => setInicioVigencia(e.target.value)} />
                </Campo>
                <Campo etiqueta="Primer pago" id="primer-pago" errores={erroresDeCampo(error, "poliza.primer_pago")}>
                  <input id="primer-pago" type="date" value={primerPago} onChange={(e) => setPrimerPago(e.target.value)} />
                </Campo>
              </div>
            </div>
          </section>

          <section className="tarjeta">
            <div className="tarjeta-cabecera">
              <h2>Hecho</h2>
            </div>
            <div className="tarjeta-cuerpo">
              <div className="rejilla-campos col-3">
                <Campo etiqueta="Tipo de siniestro" id="tipo" errores={erroresDeCampo(error, "tipo")}>
                  <input id="tipo" list="tipos-siniestro" value={tipo} onChange={(e) => setTipo(e.target.value)} />
                  <datalist id="tipos-siniestro">
                    {TIPOS_SINIESTRO_SUGERIDOS.map((t) => (
                      <option key={t} value={t} />
                    ))}
                  </datalist>
                </Campo>
                <Campo etiqueta="Fecha y hora del hecho" id="fecha-hecho" errores={erroresDeCampo(error, "fecha_hecho")}>
                  <input id="fecha-hecho" type="datetime-local" value={fechaHecho} onChange={(e) => setFechaHecho(e.target.value)} />
                </Campo>
                <Campo etiqueta="Fecha de denuncia" id="fecha-denuncia" errores={erroresDeCampo(error, "fecha_denuncia")}>
                  <input id="fecha-denuncia" type="date" value={fechaDenuncia} onChange={(e) => setFechaDenuncia(e.target.value)} />
                </Campo>
              </div>
              <Campo etiqueta="Lugar" id="lugar" errores={erroresDeCampo(error, "lugar")}>
                <input id="lugar" value={lugar} onChange={(e) => setLugar(e.target.value)} />
              </Campo>
              <Campo etiqueta="Relato" id="relato" errores={erroresDeCampo(error, "relato")}>
                <textarea id="relato" value={relato} onChange={(e) => setRelato(e.target.value)} />
              </Campo>
            </div>
          </section>

          <section className="tarjeta">
            <div className="tarjeta-cabecera">
              <h2>Personas</h2>
              <button type="button" className="boton boton-chico" onClick={() => setPersonas((f) => [...f, personaVacia()])}>
                Agregar
              </button>
            </div>
            {personas.length === 0 ? <p className="vacio">Todavía no agregaste personas.</p> : null}
            {personas.map((p, indice) => (
              <div className="fila-persona" key={p.clave}>
                <div className="rejilla-campos col-3">
                  <Campo etiqueta="Tipo de identificador" id={`p-tipo-${p.clave}`}>
                    <select
                      id={`p-tipo-${p.clave}`}
                      value={p.tipo_identificador}
                      onChange={(e) => actualizarPersona(p.clave, { tipo_identificador: e.target.value as TipoIdentificador })}
                    >
                      {TIPOS_IDENTIFICADOR.map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </Campo>
                  <Campo etiqueta="Identificador" id={`p-id-${p.clave}`} errores={erroresDeCampo(error, `personas.${indice}.identificador`)}>
                    <input
                      id={`p-id-${p.clave}`}
                      className="mono"
                      value={p.identificador}
                      onChange={(e) => actualizarPersona(p.clave, { identificador: e.target.value })}
                    />
                  </Campo>
                  <Campo etiqueta="Nombre" id={`p-nombre-${p.clave}`} errores={erroresDeCampo(error, `personas.${indice}.nombre`)}>
                    <input
                      id={`p-nombre-${p.clave}`}
                      value={p.nombre}
                      onChange={(e) => actualizarPersona(p.clave, { nombre: e.target.value })}
                    />
                  </Campo>
                </div>
                <div className="campo">
                  <label>Rol</label>
                  <div className="grupo-casillas">
                    {ROLES_PERSONA.map((rol) => (
                      <label className="casilla" key={rol}>
                        <input type="checkbox" checked={p.roles.includes(rol)} onChange={() => alternarRol(p.clave, rol)} />
                        {ETIQUETA_ROL_PERSONA[rol]}
                      </label>
                    ))}
                  </div>
                  {erroresDeCampo(error, `personas.${indice}.roles`).length > 0 ? (
                    <small className="error-campo">{erroresDeCampo(error, `personas.${indice}.roles`).join(" ")}</small>
                  ) : null}
                </div>
                <div className="acciones-fila">
                  <button
                    type="button"
                    className="boton boton-chico boton-peligro"
                    onClick={() => setPersonas((f) => f.filter((x) => x.clave !== p.clave))}
                  >
                    Quitar persona
                  </button>
                </div>
              </div>
            ))}
          </section>

          <section className="tarjeta">
            <div className="tarjeta-cabecera">
              <h2>Bienes</h2>
              <button type="button" className="boton boton-chico" onClick={() => setBienes((f) => [...f, bienVacio()])}>
                Agregar
              </button>
            </div>
            {bienes.length === 0 ? <p className="vacio">Todavía no agregaste bienes.</p> : null}
            {bienes.map((b, indice) => (
              <div className="fila-persona" key={b.clave}>
                <div className="rejilla-campos col-3">
                  <Campo etiqueta="Tipo" id={`b-tipo-${b.clave}`}>
                    <select id={`b-tipo-${b.clave}`} value={b.tipo} onChange={(e) => actualizarBien(b.clave, { tipo: e.target.value as TipoBien })}>
                      {TIPOS_BIEN.map((t) => (
                        <option key={t} value={t}>
                          {ETIQUETA_TIPO_BIEN[t]}
                        </option>
                      ))}
                    </select>
                  </Campo>
                  <Campo
                    etiqueta="Identificador"
                    id={`b-id-${b.clave}`}
                    ayuda="Dominio, IMEI o número de serie. Se normaliza sin espacios ni guiones."
                    errores={erroresDeCampo(error, `bienes.${indice}.identificador`)}
                  >
                    <input
                      id={`b-id-${b.clave}`}
                      className="mono"
                      value={b.identificador}
                      onChange={(e) => actualizarBien(b.clave, { identificador: e.target.value })}
                    />
                  </Campo>
                  <Campo etiqueta="Descripción" id={`b-desc-${b.clave}`} errores={erroresDeCampo(error, `bienes.${indice}.descripcion`)}>
                    <input
                      id={`b-desc-${b.clave}`}
                      value={b.descripcion}
                      onChange={(e) => actualizarBien(b.clave, { descripcion: e.target.value })}
                    />
                  </Campo>
                </div>
                {tieneAtributosDeVehiculo(b.tipo) ? (
                  <div className="rejilla-campos col-2">
                    <Campo etiqueta="Motor (opcional)" id={`b-motor-${b.clave}`}>
                      <input
                        id={`b-motor-${b.clave}`}
                        className="mono"
                        value={b.motor}
                        onChange={(e) => actualizarBien(b.clave, { motor: e.target.value })}
                      />
                    </Campo>
                    <Campo etiqueta="Chasis (opcional)" id={`b-chasis-${b.clave}`}>
                      <input
                        id={`b-chasis-${b.clave}`}
                        className="mono"
                        value={b.chasis}
                        onChange={(e) => actualizarBien(b.clave, { chasis: e.target.value })}
                      />
                    </Campo>
                  </div>
                ) : null}
                <Campo etiqueta="Detalle del daño" id={`b-dano-${b.clave}`} errores={erroresDeCampo(error, `bienes.${indice}.detalle_dano`)}>
                  <input
                    id={`b-dano-${b.clave}`}
                    value={b.detalle_dano}
                    onChange={(e) => actualizarBien(b.clave, { detalle_dano: e.target.value })}
                  />
                </Campo>
                <div className="acciones-fila">
                  <button
                    type="button"
                    className="boton boton-chico boton-peligro"
                    onClick={() => setBienes((f) => f.filter((x) => x.clave !== b.clave))}
                  >
                    Quitar bien
                  </button>
                </div>
              </div>
            ))}
          </section>
        </div>

        <div className="columna">
          <section className="tarjeta">
            <div className="tarjeta-cuerpo">
              <h3>Antes de confirmar</h3>
              <p className="subtitulo">
                Revisá que el identificador de cada persona y bien sea exacto. Un nombre parecido no alcanza para encontrar
                antecedentes.
              </p>
              <ErrorFormulario error={error} />
              <button type="button" className="boton boton-ancho" disabled={enviando !== null} onClick={() => void guardar(false)}>
                {enviando === "borrador" ? "Guardando…" : "Guardar borrador"}
              </button>
              <button
                type="button"
                className="boton boton-principal boton-ancho"
                disabled={enviando !== null}
                onClick={() => void guardar(true)}
              >
                {enviando === "confirmar" ? "Confirmando…" : "Confirmar siniestro"}
              </button>
            </div>
          </section>
          <AvisoVerde>Al confirmar, el sistema busca coincidencias y calcula el indicador con las reglas vigentes.</AvisoVerde>
        </div>
      </div>
    </Vista>
  );
}
