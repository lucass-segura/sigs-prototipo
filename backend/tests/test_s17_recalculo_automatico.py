"""S17 · Recálculo automático (E4:474).

Se crea una evaluación nueva de cada caso `en_analisis` afectado cuando se confirma, cierra (o cambia el cierre),
archiva o anula un siniestro que comparte una persona o un bien, y de todos los casos `en_analisis` al publicar
una versión nueva de reglas. Las evaluaciones viejas no se tocan.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from nucleo.fabrica import crear_siniestro
from nucleo.models import Evaluacion
from nucleo.motor import guardar_evaluacion
from tests.conftest import cliente_de, cuerpo_siniestro

pytestmark = pytest.mark.django_db

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
POLIZA = {"numero": "AUT-1", "compania": "Aseguradora Ejemplo S. A.", "cobertura": "Todo riesgo",
          "inicio_vigencia": date(2025, 1, 1), "primer_pago": date(2025, 1, 5)}
P17 = {"tipo_identificador": "DNI", "identificador": "30111017", "nombre": "P-17", "roles": ["asegurado"]}
CIERRE = {"resultado_reclamo": "aprobado", "valoracion": 7, "conclusion": "Hecho verificado con observaciones menores.",
          "justificacion": "Faltó la denuncia policial original."}


def local(anio, mes, dia, hora=12):
    return datetime(anio, mes, dia, hora, tzinfo=ZONA)


@pytest.fixture
def red(perito08, perito11, perito15):
    """C (Norte, PE-08) en análisis con una evaluación; X (Sur, PE-15) en análisis, anterior a C y con el mismo vehículo."""
    r = type("Red", (), {})()
    r.c = crear_siniestro(perito08, "EXP-C", fecha_hecho=local(2026, 8, 12), poliza=POLIZA, personas=[P17], bienes=["AB123CD"])
    r.x = crear_siniestro(perito15, "S-X", fecha_hecho=local(2026, 3, 10), poliza=POLIZA, personas=[], bienes=["AB123CD"])
    r.sin_vinculo = crear_siniestro(perito11, "EXP-SIN-VINCULO", fecha_hecho=local(2026, 8, 1), poliza=POLIZA, bienes=["ZZ999ZZ"])
    r.cerrado = crear_siniestro(perito11, "EXP-CERRADO", fecha_hecho=local(2026, 8, 5), poliza=POLIZA, bienes=["AB123CD"],
                                estado="cerrado", cierre=dict(CIERRE))
    r.borrador = crear_siniestro(perito11, "EXP-BORRADOR", fecha_hecho=local(2026, 8, 6), poliza=POLIZA, bienes=["AB123CD"],
                                 estado="borrador")
    for caso in (r.c, r.sin_vinculo, r.cerrado):
        guardar_evaluacion(caso, "confirmacion")
    return r


def evaluaciones(caso):
    return list(Evaluacion.objects.filter(siniestro=caso).order_by("id"))


def cantidades(red):
    return {s.numero_expediente: Evaluacion.objects.filter(siniestro=s).count() for s in (red.c, red.sin_vinculo, red.cerrado, red.borrador)}


def senales(evaluacion):
    return {s.regla.codigo: s for s in evaluacion.senales.select_related("regla")}


def solo_cambio_c(antes, despues):
    """Solo EXP-C ganó una evaluación; el resto quedó igual."""
    assert despues["EXP-C"] == antes["EXP-C"] + 1
    assert {k: v for k, v in despues.items() if k != "EXP-C"} == {k: v for k, v in antes.items() if k != "EXP-C"}


# --- Confirmación ---------------------------------------------------------------------------
def test_s17_al_confirmar_un_antecedente_se_recalcula_el_caso_afectado(red, perito15):
    nuevo = cliente_de(perito15).post("/api/siniestros", cuerpo_siniestro(
        numero_expediente="S-NUEVO", fecha_hecho="2026-02-01T10:00:00", personas=[],
        poliza=dict(cuerpo_siniestro()["poliza"], inicio_vigencia="2025-01-01", primer_pago="2025-01-05"),
        bienes=[{"tipo": "vehiculo", "identificador": "AB-123-CD"}]), format="json")
    assert nuevo.status_code == 201
    antes = cantidades(red)
    assert cliente_de(perito15).post(f"/api/siniestros/{nuevo.json()['id']}/confirmar").status_code == 200
    despues = cantidades(red)
    solo_cambio_c(antes, despues)
    ultima = evaluaciones(red.c)[-1]
    assert ultima.motivo == "antecedente_confirmado" and "S-NUEVO" in str(senales(ultima)["R06"].antecedentes)


def test_s17_confirmar_un_caso_posterior_no_recalcula_porque_no_es_su_antecedente(red, perito15):
    posterior = crear_siniestro(perito15, "S-POSTERIOR", fecha_hecho=local(2026, 9, 1), poliza=POLIZA, bienes=["AB123CD"], estado="borrador")
    antes = cantidades(red)
    assert cliente_de(perito15).post(f"/api/siniestros/{posterior.id}/confirmar").status_code == 200
    assert cantidades(red) == antes


# --- Cierre y cambio de cierre ----------------------------------------------------------------
def test_s17_al_cerrar_un_antecedente_con_irregularidad_se_recalcula_y_activa_r07(red, perito15):
    antes = cantidades(red)
    vieja = evaluaciones(red.c)[-1]
    respuesta = cliente_de(perito15).post(
        f"/api/siniestros/{red.x.id}/cierre",
        dict(CIERRE, resultado_reclamo="rechazado", irregularidad=True, observacion_respaldo="Adulteración comprobada en la inspección."),
        format="json",
    )
    assert respuesta.status_code == 201, respuesta.content
    solo_cambio_c(antes, cantidades(red))
    nueva = evaluaciones(red.c)[-1]
    assert nueva.motivo == "antecedente_cerrado" and nueva.pk != vieja.pk
    assert senales(nueva)["R07"].estado == "activada" and nueva.puntaje == vieja.puntaje + 30
    # la evaluación vieja no se tocó
    vieja_despues = Evaluacion.objects.get(pk=vieja.pk)
    assert (vieja_despues.puntaje, vieja_despues.motivo, vieja_despues.entradas) == (vieja.puntaje, vieja.motivo, vieja.entradas)


def test_s17_al_cambiar_el_cierre_se_vuelve_a_recalcular(red, perito15):
    cliente = cliente_de(perito15)
    assert cliente.post(f"/api/siniestros/{red.x.id}/cierre", dict(CIERRE, resultado_reclamo="rechazado", irregularidad=True,
                                                                     observacion_respaldo="Documentación adulterada."), format="json").status_code == 201
    assert evaluaciones(red.c)[-1].puntaje == 55
    antes = cantidades(red)
    respuesta = cliente.post(f"/api/siniestros/{red.x.id}/cierre",
                             dict(CIERRE, motivo_cambio="La irregularidad no se pudo sostener."), format="json")
    assert respuesta.status_code == 201, respuesta.content
    solo_cambio_c(antes, cantidades(red))
    ultima = evaluaciones(red.c)[-1]
    assert ultima.motivo == "antecedente_cerrado" and ultima.puntaje == 25 and senales(ultima)["R07"].estado == "no_activada"


# --- Archivo y anulación ----------------------------------------------------------------------
def test_s17_al_archivar_un_antecedente_se_recalcula_y_sigue_contando(red, perito15):
    cliente = cliente_de(perito15)
    cliente.post(f"/api/siniestros/{red.x.id}/cierre", CIERRE, format="json")
    antes = cantidades(red)
    assert cliente.post(f"/api/siniestros/{red.x.id}/archivar").status_code == 200
    solo_cambio_c(antes, cantidades(red))
    ultima = evaluaciones(red.c)[-1]
    assert ultima.motivo == "antecedente_archivado" and senales(ultima)["R06"].estado == "activada"


def test_s17_al_anular_un_antecedente_se_recalcula_y_deja_de_contar(red, perito15):
    assert evaluaciones(red.c)[-1].puntaje == 25  # R06 por el mismo vehículo en S-X y en EXP-CERRADO
    antes = cantidades(red)
    respuesta = cliente_de(perito15).post(f"/api/siniestros/{red.x.id}/anular", {"motivo": "Carga errónea"}, format="json")
    assert respuesta.status_code == 200
    solo_cambio_c(antes, cantidades(red))
    ultima = evaluaciones(red.c)[-1]
    assert ultima.motivo == "antecedente_anulado"
    assert [a["numero_expediente"] for a in senales(ultima)["R06"].antecedentes] == ["EXP-CERRADO"]
    assert "S-X" not in str(ultima.entradas["antecedentes"])


def test_s17_anular_un_borrador_nunca_confirmado_no_recalcula_nada(red, perito11):
    antes = cantidades(red)
    assert cliente_de(perito11).post(f"/api/siniestros/{red.borrador.id}/anular", {"motivo": "Carga errónea"}, format="json").status_code == 200
    assert cantidades(red) == antes


def test_s17_un_caso_cerrado_o_sin_vinculo_no_se_recalcula(red, perito15):
    cliente_de(perito15).post(f"/api/siniestros/{red.x.id}/cierre", CIERRE, format="json")
    assert Evaluacion.objects.filter(siniestro=red.cerrado).count() == 1
    assert Evaluacion.objects.filter(siniestro=red.sin_vinculo).count() == 1


def test_s17_el_boton_recalcular_se_mantiene(red, perito08):
    antes = cantidades(red)
    assert cliente_de(perito08).post(f"/api/siniestros/{red.c.id}/recalcular").status_code == 200
    solo_cambio_c(antes, cantidades(red))
    assert evaluaciones(red.c)[-1].motivo == "recalculo"


# --- Versión nueva de reglas ----------------------------------------------------------------
def test_s17_publicar_una_version_recalcula_todos_los_casos_en_analisis_con_la_version_nueva(red, superadmin):
    antes = cantidades(red)
    viejas = {e.pk: (e.puntaje, e.conjunto.version) for s in (red.c, red.sin_vinculo, red.cerrado) for e in evaluaciones(s)}
    respuesta = cliente_de(superadmin).post("/api/reglas/versiones", {
        "version": "RS-1.1", "vigente_desde": "2026-12-01",
        "reglas": {"R06": {"parametros": {"ventana_meses": 24, "puntos": 10}, "puntos_max": 25}},
    }, format="json")
    assert respuesta.status_code == 201, respuesta.content
    despues = cantidades(red)
    assert despues["EXP-C"] == antes["EXP-C"] + 1 and despues["EXP-SIN-VINCULO"] == antes["EXP-SIN-VINCULO"] + 1
    assert despues["EXP-CERRADO"] == antes["EXP-CERRADO"] and despues["EXP-BORRADOR"] == antes["EXP-BORRADOR"]
    for caso in (red.c, red.sin_vinculo):
        ultima = evaluaciones(caso)[-1]
        assert ultima.motivo == "nueva_version" and ultima.conjunto.version == "RS-1.1"
    assert senales(evaluaciones(red.c)[-1])["R06"].puntos == 10
    # las evaluaciones viejas conservan su versión y su puntaje
    for pk, (puntaje, version) in viejas.items():
        e = Evaluacion.objects.get(pk=pk)
        assert (e.puntaje, e.conjunto.version) == (puntaje, version) and version == "RS-1.0"
    historial = cliente_de(red.c.perito).get(f"/api/siniestros/{red.c.id}/evaluaciones").json()
    assert [h["version"] for h in historial] == ["RS-1.1", "RS-1.0"]


def test_s17_una_version_rechazada_no_recalcula_nada(red, superadmin):
    antes = cantidades(red)
    respuesta = cliente_de(superadmin).post("/api/reglas/versiones", {"version": "RS-1.0", "vigente_desde": "2026-12-01", "reglas": {}}, format="json")
    assert respuesta.status_code == 400
    assert cantidades(red) == antes
