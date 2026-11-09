// Pruebas de lib/asistenteSiniestro.ts (asistente de «Registrar siniestro», S33).
// Se corren con `npm test` (Node 22.18 o más nuevo, que ejecuta TypeScript sin dependencias).
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  PASOS,
  PREFIJO_ALMACEN,
  armarCuerpo,
  borrarGuardados,
  claveAlmacen,
  datosIniciales,
  deserializar,
  estadoDePaso,
  idControlDeRuta,
  indiceEnviado,
  pasoDeRuta,
  pasosConError,
  numeroDePolizaCargado,
  primerPasoConError,
  reducirDatos,
  requisitosParaConfirmar,
  serializar,
  textoCompactoDePaso,
  validarPaso,
} from "../lib/asistenteSiniestro.ts";

const campo = (datos, nombre, valor) => reducirDatos(datos, { tipo: "campo", campo: nombre, valor });

function completo() {
  let d = datosIniciales();
  d = campo(d, "numeroPoliza", " POL-1 ");
  d = campo(d, "compania", "Sur");
  d = campo(d, "inicioVigencia", "2026-01-01");
  d = campo(d, "tipo", "Incendio");
  d = campo(d, "fechaHecho", "2026-08-12");
  d = campo(d, "horaHecho", "23:40");
  d = campo(d, "horaDenuncia", "10:20");
  const p = d.personas[0].clave;
  d = reducirDatos(d, { tipo: "persona/actualizar", clave: p, cambios: { identificador: " 123 ", nombre: "Ana" } });
  d = reducirDatos(d, { tipo: "persona/alternarRol", clave: p, rol: "asegurado" });
  const b = d.bienes[0].clave;
  d = reducirDatos(d, { tipo: "bien/actualizar", clave: b, cambios: { identificador: "AB123CD", motor: "M1", chasis: "" } });
  return d;
}

test("pasos: los cinco, en orden, con el texto compacto del teléfono", () => {
  assert.deepEqual(
    PASOS.map((p) => p.id),
    ["poliza", "hecho", "personas", "bienes", "revision"],
  );
  assert.equal(textoCompactoDePaso("hecho"), "Paso 2 de 5 · Hecho y denuncia");
  assert.equal(textoCompactoDePaso("revision"), "Paso 5 de 5 · Revisar y confirmar");
});

test("estado de cada paso: actual, completo y con errores", () => {
  const conError = new Set(["personas"]);
  const e = (id) => estadoDePaso(id, "hecho", ["poliza", "hecho", "personas"], conError);
  assert.deepEqual(e("poliza"), { actual: false, completo: true, error: false });
  assert.deepEqual(e("hecho"), { actual: true, completo: false, error: false });
  assert.deepEqual(e("personas"), { actual: false, completo: false, error: true });
  assert.deepEqual(e("bienes"), { actual: false, completo: false, error: false });
  assert.equal(estadoDePaso("revision", "hecho", ["revision"], new Set()).completo, false);
});

test("reductor: cambia un campo, agrega, edita y quita filas sin tocar el resto", () => {
  const d0 = datosIniciales();
  assert.equal(campo(d0, "tipo", "Robo").tipo, "Robo");
  assert.equal(campo(d0, "tipo", ""), d0, "sin cambios devuelve el mismo objeto");
  const d1 = reducirDatos(d0, { tipo: "persona/agregar", clave: 900 });
  assert.equal(d1.personas.length, 2);
  assert.equal(d1.personas[1].clave, 900);
  const d2 = reducirDatos(d1, { tipo: "persona/alternarRol", clave: 900, rol: "testigo" });
  assert.deepEqual(d2.personas[1].roles, ["testigo"]);
  const d3 = reducirDatos(d2, { tipo: "persona/alternarRol", clave: 900, rol: "testigo" });
  assert.deepEqual(d3.personas[1].roles, []);
  const d4 = reducirDatos(d3, { tipo: "persona/quitar", clave: 900 });
  assert.equal(d4.personas.length, 1);
  const d5 = reducirDatos(d4, { tipo: "bien/agregar", clave: 901 });
  assert.equal(d5.bienes.length, 2);
  assert.equal(reducirDatos(d5, { tipo: "bien/quitar", clave: 901 }).bienes.length, 1);
  const d6 = completo();
  assert.equal(reducirDatos(d0, { tipo: "reemplazar", datos: d6 }), d6);
});

test("cuerpo: la misma forma que enviaba el formulario de una sola página", () => {
  assert.deepEqual(armarCuerpo(completo()), {
    poliza: { numero: "POL-1", compania: "Sur", cobertura: "", inicio_vigencia: "2026-01-01", primer_pago: null },
    tipo: "Incendio",
    fecha_hecho: "2026-08-12T23:40",
    fecha_denuncia: null,
    hora_denuncia: "10:20",
    numero_denuncia: "",
    asesor: "",
    intervenciones: "",
    documentacion_adjunta: "",
    lugar: "",
    relato: "",
    personas: [{ tipo_identificador: "DNI", identificador: "123", nombre: "Ana", roles: ["asegurado"] }],
    bienes: [{ tipo: "vehiculo", identificador: "AB123CD", descripcion: "", detalle_dano: "", atributos: { motor: "M1" } }],
  });
});

test("cuerpo: sin fecha u hora del hecho no se envía fecha_hecho; las filas en blanco se ignoran", () => {
  const d = campo(completo(), "horaHecho", "");
  assert.equal("fecha_hecho" in armarCuerpo(d), false);
  const vacio = armarCuerpo(datosIniciales());
  assert.deepEqual(vacio.personas, []);
  assert.deepEqual(vacio.bienes, []);
  assert.equal("fecha_hecho" in vacio, false);
});

test("cuerpo: motor y chasis solo viajan en vehículos y motos", () => {
  let d = completo();
  d = reducirDatos(d, { tipo: "bien/actualizar", clave: d.bienes[0].clave, cambios: { tipo: "telefono", motor: "M1", chasis: "C1" } });
  assert.deepEqual(armarCuerpo(d).bienes[0].atributos, {});
  d = reducirDatos(d, { tipo: "bien/actualizar", clave: d.bienes[0].clave, cambios: { tipo: "motocicleta" } });
  assert.deepEqual(armarCuerpo(d).bienes[0].atributos, { motor: "M1", chasis: "C1" });
});

test("errores de la API: cada campo va al paso que lo tiene", () => {
  assert.equal(pasoDeRuta("poliza.numero"), "poliza");
  assert.equal(pasoDeRuta("poliza.inicio_vigencia"), "poliza");
  assert.equal(pasoDeRuta("fecha_hecho"), "hecho");
  assert.equal(pasoDeRuta("numero_denuncia"), "hecho");
  assert.equal(pasoDeRuta("hora_denuncia"), "hecho");
  assert.equal(pasoDeRuta("personas.0.identificador"), "personas");
  assert.equal(pasoDeRuta("personas.1.roles"), "personas");
  assert.equal(pasoDeRuta("bienes.2.detalle_dano"), "bienes");
  assert.equal(pasoDeRuta("detalle"), null);
  assert.equal(pasoDeRuta("non_field_errors"), null);
  assert.equal(pasoDeRuta("numero_expediente"), null);
});

test("errores de la API: pasos con error en orden y primer paso al que saltar", () => {
  const rutas = ["bienes.0.identificador", "poliza.numero", "personas.0.identificador", "poliza.compania"];
  assert.deepEqual(pasosConError(rutas), ["poliza", "personas", "bienes"]);
  assert.equal(primerPasoConError(rutas), "poliza");
  assert.equal(primerPasoConError(["fecha_hecho", "bienes.0.tipo"]), "hecho");
  assert.equal(primerPasoConError(["detalle"]), null);
  assert.equal(primerPasoConError([]), null);
});

test("errores de la API: el índice de personas.N es el de lo enviado, no el de la fila en pantalla", () => {
  let d = datosIniciales(); // fila 0 en blanco: no se envía
  d = reducirDatos(d, { tipo: "persona/agregar", clave: 700 });
  d = reducirDatos(d, { tipo: "persona/actualizar", clave: 700, cambios: { nombre: "Luis" } });
  assert.equal(idControlDeRuta("personas.0.identificador", d), "p-id-700");
  assert.equal(idControlDeRuta("personas.0.roles", d), "p-roles-700");
  assert.equal(idControlDeRuta("personas.1.identificador", d), null);
  assert.equal(indiceEnviado(d.personas.filter((p) => p.nombre), 700), 0);
  assert.equal(indiceEnviado(d.personas.filter((p) => p.nombre), d.personas[0].clave), null);
  assert.equal(idControlDeRuta("fecha_hecho", d), "fecha-hecho");
  assert.equal(idControlDeRuta("poliza.numero", d), "numero-poliza");
  assert.equal(idControlDeRuta("detalle", d), null);
  const b = reducirDatos(d, { tipo: "bien/actualizar", clave: d.bienes[0].clave, cambios: { descripcion: "Auto" } });
  assert.equal(idControlDeRuta("bienes.0.identificador", b), `b-id-${b.bienes[0].clave}`);
});

test("validación suave: avisa por paso con los mismos textos de la API", () => {
  let d = datosIniciales();
  assert.deepEqual(validarPaso(d, "personas"), {}, "una fila en blanco no es un error");
  d = reducirDatos(d, { tipo: "persona/actualizar", clave: d.personas[0].clave, cambios: { nombre: "Ana" } });
  const m = validarPaso(d, "personas");
  assert.equal(m[`p-id-${d.personas[0].clave}`], "El identificador de la persona es obligatorio.");
  assert.equal(m[`p-roles-${d.personas[0].clave}`], "Indicá al menos un rol para la persona.");
  d = reducirDatos(d, { tipo: "bien/actualizar", clave: d.bienes[0].clave, cambios: { descripcion: "Auto" } });
  assert.equal(validarPaso(d, "bienes")[`b-id-${d.bienes[0].clave}`], "El identificador del bien es obligatorio.");
  assert.deepEqual(validarPaso(d, "poliza"), {});
  assert.deepEqual(validarPaso(completo(), "personas"), {});
});

test("para confirmar: número de póliza, fecha del hecho y al menos una persona o un bien", () => {
  const faltan = (d) => requisitosParaConfirmar(d).filter((r) => !r.cumplido).map((r) => r.id);
  assert.deepEqual(faltan(datosIniciales()), ["poliza", "fecha-hecho", "vinculo"]);
  assert.deepEqual(faltan(completo()), []);
  assert.deepEqual(faltan(campo(completo(), "fechaHecho", "")), ["fecha-hecho"]);
  assert.deepEqual(faltan(campo(completo(), "horaHecho", "")), ["fecha-hecho"]);
  // Basta una persona o un bien
  let soloBien = completo();
  soloBien = reducirDatos(soloBien, { tipo: "persona/quitar", clave: soloBien.personas[0].clave });
  assert.deepEqual(faltan(soloBien), []);
  const sinVinculos = reducirDatos(soloBien, { tipo: "bien/quitar", clave: soloBien.bienes[0].clave });
  assert.deepEqual(faltan(sinVinculos), ["vinculo"]);
  assert.deepEqual(requisitosParaConfirmar(sinVinculos).find((r) => r.id === "vinculo").pasos, ["personas", "bienes"]);
});

test("para confirmar: el número de póliza es lo que cuenta (S34), no cualquier dato de la póliza", () => {
  const faltan = (d) => requisitosParaConfirmar(d).filter((r) => !r.cumplido).map((r) => r.id);
  const sinNumero = (d) => campo(d, "numeroPoliza", "");
  // Compañía, cobertura y fechas de la póliza cargadas, pero sin número: sigue faltando
  let d = sinNumero(completo());
  d = campo(d, "cobertura", "Todo riesgo");
  d = campo(d, "primerPago", "2026-02-01");
  assert.deepEqual(faltan(d), ["poliza"]);
  assert.deepEqual(faltan(campo(completo(), "numeroPoliza", "   ")), ["poliza"]);
  assert.deepEqual(faltan(campo(completo(), "numeroPoliza", "POL-1")), []);
  const requisito = requisitosParaConfirmar(sinNumero(completo())).find((r) => r.id === "poliza");
  assert.equal(requisito.texto, "Póliza: cargá el número de póliza.");
  assert.deepEqual(requisito.pasos, ["poliza"]);
  assert.equal(numeroDePolizaCargado(datosIniciales()), false);
  assert.equal(numeroDePolizaCargado(campo(datosIniciales(), "compania", "Sur")), false);
  assert.equal(numeroDePolizaCargado(campo(datosIniciales(), "numeroPoliza", "  ")), false);
  assert.equal(numeroDePolizaCargado(campo(datosIniciales(), "numeroPoliza", "POL-1")), true);
});

test("sessionStorage: una clave por usuario y por borrador (o «nuevo»)", () => {
  assert.equal(claveAlmacen(8, null), "sigs:siniestro:8:nuevo");
  assert.equal(claveAlmacen(8, 41), "sigs:siniestro:8:41");
  assert.notEqual(claveAlmacen(8, null), claveAlmacen(9, null));
  assert.ok(claveAlmacen(8, 41).startsWith(PREFIJO_ALMACEN));
});

test("sessionStorage: ida y vuelta conserva datos, paso y pasos visitados", () => {
  const datos = completo();
  const leido = deserializar(serializar({ datos, paso: "personas", visitados: ["poliza", "hecho"] }));
  assert.ok(leido);
  assert.equal(leido.paso, "personas");
  assert.deepEqual(leido.visitados, ["poliza", "hecho"]);
  // Las claves de fila son nuevas; lo demás es igual.
  const sinClave = (fila) => Object.fromEntries(Object.entries(fila).filter(([k]) => k !== "clave"));
  const sinClaves = (d) => ({ ...d, personas: d.personas.map(sinClave), bienes: d.bienes.map(sinClave) });
  assert.deepEqual(sinClaves(leido.datos), sinClaves(datos));
  assert.deepEqual(armarCuerpo(leido.datos), armarCuerpo(datos), "el cuerpo que se envía no cambia");
  const claves = [...leido.datos.personas, ...leido.datos.bienes].map((f) => f.clave);
  assert.equal(new Set(claves).size, claves.length);
});

test("sessionStorage: lo dañado o de otra versión se descarta y lo incompleto se rellena", () => {
  assert.equal(deserializar(null), null);
  assert.equal(deserializar(""), null);
  assert.equal(deserializar("{no es json"), null);
  assert.equal(deserializar("[]"), null);
  assert.equal(deserializar(JSON.stringify({ version: 99, datos: {} })), null);
  assert.equal(deserializar(JSON.stringify({ version: 1 })), null);
  const parcial = deserializar(
    JSON.stringify({
      version: 1,
      paso: "inexistente",
      visitados: ["hecho", "otro", 3],
      datos: {
        tipo: "Robo",
        compania: 5,
        personas: [{ tipo_identificador: "RARO", identificador: "1", roles: ["asegurado", "capitan"] }, "basura"],
        bienes: "no es una lista",
      },
    }),
  );
  assert.ok(parcial);
  assert.equal(parcial.paso, "poliza");
  assert.deepEqual(parcial.visitados, ["hecho"]);
  assert.equal(parcial.datos.tipo, "Robo");
  assert.equal(parcial.datos.compania, "");
  assert.equal(parcial.datos.personas.length, 1);
  assert.equal(parcial.datos.personas[0].tipo_identificador, "DNI");
  assert.deepEqual(parcial.datos.personas[0].roles, ["asegurado"]);
  assert.equal(parcial.datos.bienes.length, 1, "sin lista válida queda la fila vacía de siempre");
});

test("sessionStorage: al salir se borran todos los borradores y nada más", () => {
  const datos = new Map([
    ["sigs:siniestro:8:nuevo", "a"],
    ["sigs:siniestro:8:41", "b"],
    ["sigs:siniestro:9:nuevo", "c"],
    ["otra-cosa", "d"],
  ]);
  const almacen = {
    get length() {
      return datos.size;
    },
    key: (i) => [...datos.keys()][i] ?? null,
    removeItem: (k) => datos.delete(k),
  };
  borrarGuardados(almacen);
  assert.deepEqual([...datos.keys()], ["otra-cosa"]);
});
