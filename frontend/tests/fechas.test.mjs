// Pruebas de lib/fechas.ts (lectura y formato de fechas y horas de los selectores).
// Se corren con `npm test` (Node 22.18 o más nuevo, que ejecuta TypeScript sin dependencias).
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  ahoraLocal,
  analizarFecha,
  analizarHora,
  armarISO,
  compararISO,
  diaDeSemana,
  evaluarFecha,
  evaluarHora,
  finDeMesISO,
  formatearFecha,
  inicioDeSemanaISO,
  mascaraFecha,
  mascaraHora,
  matrizDelMes,
  minutosDeColumna,
  nombreLargoFecha,
  resolverAtajo,
  separarFechaHora,
  sumarDiasISO,
  sumarMesesISO,
  unirFechaHora,
} from "../lib/fechas.ts";

const HOY = "2026-08-12";
const ok = (texto) => {
  const r = analizarFecha(texto, HOY);
  assert.ok(r.ok, `«${texto}» debería ser válida: ${r.mensaje}`);
  return r.valor;
};

test("fecha: formas de escribirla", () => {
  assert.equal(ok("12/08/2026"), "2026-08-12");
  assert.equal(ok("12/8/26"), "2026-08-12");
  assert.equal(ok("120826"), "2026-08-12");
  assert.equal(ok("12082026"), "2026-08-12");
  assert.equal(ok("12-8-2026"), "2026-08-12");
  assert.equal(ok("1.9.26"), "2026-09-01");
  assert.equal(ok("  05/01/2025 "), "2025-01-05");
});

test("fecha: sin año se usa el de hoy", () => {
  assert.equal(ok("1208"), "2026-08-12");
  assert.equal(ok("3/11"), "2026-11-03");
});

test("fecha: días que no existen", () => {
  const r = analizarFecha("31/02/2026", HOY);
  assert.equal(r.ok, false);
  assert.equal(r.incompleta, false);
  assert.match(r.mensaje, /Febrero de 2026 tiene 28 días/);
  assert.equal(analizarFecha("29/02/2025", HOY).ok, false);
  assert.equal(ok("29/02/2028"), "2028-02-29");
});

test("fecha: mes, año y caracteres inválidos", () => {
  assert.match(analizarFecha("10/13/2026", HOY).mensaje, /mes 13 no existe/);
  assert.match(analizarFecha("10/12/1800", HOY).mensaje, /entre 1900 y 2100/);
  assert.match(analizarFecha("ab/cd", HOY).mensaje, /solo números/);
  assert.equal(analizarFecha("10/12/202", HOY).incompleta, true);
});

test("fecha: incompleta mientras se escribe", () => {
  for (const t of ["", "1", "12/", "12/0", "12/08/", "12345", "1234567"]) {
    const r = analizarFecha(t, HOY);
    assert.equal(r.ok, false, t);
  }
  assert.equal(analizarFecha("12/", HOY).incompleta, true);
  assert.equal(analizarFecha("12/08/", HOY).incompleta, true);
});

test("fecha: máscara al escribir", () => {
  assert.equal(mascaraFecha("1"), "1");
  assert.equal(mascaraFecha("120"), "12/0");
  assert.equal(mascaraFecha("1208"), "12/08");
  assert.equal(mascaraFecha("120826"), "12/08/26");
  assert.equal(mascaraFecha("12082026"), "12/08/2026");
  assert.equal(mascaraFecha("120820269999"), "12/08/2026");
  // Escribir letra por letra, con las barras que agregó la máscara en el medio.
  let escrito = "";
  for (const c of "12082026") escrito = mascaraFecha(escrito + c);
  assert.equal(escrito, "12/08/2026");
  escrito = "";
  for (const c of "010126") escrito = mascaraFecha(escrito + c);
  assert.equal(escrito, "01/01/26");
  // Con las barras escritas a mano y un solo dígito en algún tramo no se toca; las letras se descartan.
  escrito = "";
  for (const c of "12/8/26") escrito = mascaraFecha(escrito + c);
  assert.equal(escrito, "12/8/26");
  assert.equal(mascaraFecha("1/"), "1/");
  assert.equal(mascaraFecha("12a/8"), "12/8");
  // Borrar un dígito deja la barra de más afuera.
  assert.equal(mascaraFecha("12/08/"), "12/08");
  assert.equal(mascaraFecha("12/"), "12");
});

test("fecha: formato y nombre largo", () => {
  assert.equal(formatearFecha("2026-08-12"), "12/08/2026");
  assert.equal(formatearFecha(""), "");
  assert.equal(formatearFecha("2026-02-30"), "");
  assert.equal(nombreLargoFecha("2026-08-12"), "miércoles 12 de agosto de 2026");
  assert.equal(nombreLargoFecha("2026-08-10"), "lunes 10 de agosto de 2026");
});

test("calendario: la semana empieza el lunes", () => {
  assert.equal(diaDeSemana("2026-08-10"), 0);
  assert.equal(diaDeSemana("2026-08-16"), 6);
  assert.equal(inicioDeSemanaISO("2026-08-12"), "2026-08-10");
  const m = matrizDelMes("2026-08-12");
  assert.equal(m.length, 6);
  assert.ok(m.every((semana) => semana.length === 7));
  assert.equal(m[0][0], "2026-07-27");
  assert.equal(m[0][5], "2026-08-01");
  assert.equal(m[5][6], "2026-09-06");
});

test("calendario: sumar días y meses", () => {
  assert.equal(sumarDiasISO("2026-12-31", 1), "2027-01-01");
  assert.equal(sumarDiasISO("2026-03-01", -1), "2026-02-28");
  assert.equal(sumarMesesISO("2026-01-31", 1), "2026-02-28");
  assert.equal(sumarMesesISO("2026-01-15", -1), "2025-12-15");
  assert.equal(sumarMesesISO("2026-08-12", 12), "2027-08-12");
  assert.equal(finDeMesISO("2028-02-10"), "2028-02-29");
  assert.equal(armarISO(2026, 3, 5), "2026-03-05");
  assert.equal(compararISO("2026-01-01", "2026-01-02"), -1);
});

test("atajos", () => {
  assert.equal(resolverAtajo("hoy", HOY), "2026-08-12");
  assert.equal(resolverAtajo("ayer", HOY), "2026-08-11");
  assert.equal(resolverAtajo("manana", HOY), "2026-08-13");
  assert.equal(resolverAtajo("en7dias", HOY), "2026-08-19");
  assert.equal(resolverAtajo("finDeMes", HOY), "2026-08-31");
  assert.equal(resolverAtajo("sinFecha", HOY), "");
});

test("hora: formas de escribirla", () => {
  const h = (t) => {
    const r = analizarHora(t);
    assert.ok(r.ok, `«${t}» debería ser válida: ${r.mensaje}`);
    return r.valor;
  };
  assert.equal(h("2340"), "23:40");
  assert.equal(h("23:40"), "23:40");
  assert.equal(h("930"), "09:30");
  assert.equal(h("9:30"), "09:30");
  assert.equal(h("9.30"), "09:30");
  assert.equal(h("9"), "09:00");
  assert.equal(h("21"), "21:00");
  assert.equal(h("0005"), "00:05");
});

test("hora: inválidas e incompletas", () => {
  assert.match(analizarHora("24:00").mensaje, /hora 24 no existe/);
  assert.match(analizarHora("12:60").mensaje, /minutos 60 no existen/);
  assert.equal(analizarHora("9:3").incompleta, true);
  assert.equal(analizarHora("9:").incompleta, true);
  assert.equal(analizarHora("233").ok, false);
  assert.equal(analizarHora("12345").ok, false);
  assert.match(analizarHora("ab").mensaje, /solo números/);
});

test("hora: máscara al escribir", () => {
  assert.equal(mascaraHora("2"), "2");
  assert.equal(mascaraHora("23"), "23");
  assert.equal(mascaraHora("234"), "23:4");
  assert.equal(mascaraHora("2340"), "23:40");
  assert.equal(mascaraHora("93"), "9:3");
  assert.equal(mascaraHora("930"), "9:30");
  assert.equal(mascaraHora("27"), "2:7");
  assert.equal(mascaraHora("23:4"), "23:4");
  assert.equal(mascaraHora("9:30"), "9:30");
  assert.equal(mascaraHora("1:30"), "1:30");
  assert.equal(mascaraHora("9.30"), "9:30");
  let escrito = "";
  for (const c of "2340") escrito = mascaraHora(escrito + c);
  assert.equal(escrito, "23:40");
  escrito = "";
  for (const c of "930") escrito = mascaraHora(escrito + c);
  assert.equal(escrito, "9:30");
  assert.equal(mascaraHora("23400"), "23:40");
});

test("evaluar fecha contra los límites", () => {
  const limites = {
    minimo: "2026-03-01",
    maximo: "2026-08-12",
    motivoMinimo: "Antes de la vigencia.",
    motivoMaximo: "Es futura.",
  };
  assert.deepEqual(evaluarFecha("", HOY, limites), { estado: "vacio", valor: "", mensaje: "" });
  assert.deepEqual(evaluarFecha("12/08/2026", HOY, limites), { estado: "ok", valor: "2026-08-12", mensaje: "" });
  assert.deepEqual(evaluarFecha("01/03/2026", HOY, limites), { estado: "ok", valor: "2026-03-01", mensaje: "" });
  assert.deepEqual(evaluarFecha("13/08/2026", HOY, limites), { estado: "error", valor: "", mensaje: "Es futura." });
  assert.deepEqual(evaluarFecha("28/02/2026", HOY, limites), { estado: "error", valor: "", mensaje: "Antes de la vigencia." });
  assert.equal(evaluarFecha("12/0", HOY, limites).estado, "incompleto");
  assert.equal(evaluarFecha("31/04/2026", HOY, limites).estado, "error");
  // Sin límites propios hay un mensaje por defecto con la fecha.
  assert.match(evaluarFecha("01/01/2020", HOY, { minimo: "2026-01-01" }).mensaje, /anterior al 01\/01\/2026/);
});

test("evaluar hora contra los límites", () => {
  const limites = { maxima: "14:37", motivoMaxima: "Todavía no pasó." };
  assert.equal(evaluarHora("14:37", limites).valor, "14:37");
  assert.deepEqual(evaluarHora("14:38", limites), { estado: "error", valor: "", mensaje: "Todavía no pasó." });
  assert.equal(evaluarHora("", limites).estado, "vacio");
});

test("columna de minutos: de a 5 y el minuto escrito", () => {
  assert.deepEqual(minutosDeColumna("").length, 12);
  assert.equal(minutosDeColumna("40").length, 12);
  const con = minutosDeColumna("42");
  assert.equal(con.length, 13);
  assert.ok(con.indexOf("42") === con.indexOf("40") + 1);
});

test("fecha con hora: el mismo formato que antes enviaba datetime-local", () => {
  assert.equal(unirFechaHora("2026-08-12", "23:40"), "2026-08-12T23:40");
  assert.equal(unirFechaHora("2026-08-12", ""), "");
  assert.deepEqual(separarFechaHora("2026-08-12T23:40"), { fecha: "2026-08-12", hora: "23:40" });
  assert.deepEqual(separarFechaHora(""), { fecha: "", hora: "" });
});

test("ahora en Buenos Aires (UTC-3, sin horario de verano)", () => {
  assert.deepEqual(ahoraLocal(new Date("2026-08-13T02:30:00Z")), { fecha: "2026-08-12", hora: "23:30" });
  assert.deepEqual(ahoraLocal(new Date("2026-01-01T03:00:00Z")), { fecha: "2026-01-01", hora: "00:00" });
});
