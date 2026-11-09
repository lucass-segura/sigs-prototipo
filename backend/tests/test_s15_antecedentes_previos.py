"""S15 · Un antecedente solo cuenta si su fecha del hecho (fecha local) es estrictamente anterior a la del caso analizado.

Vale para la lista de coincidencias, el promedio, el resumen y todas las reglas, incluida R07.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from nucleo.fabrica import crear_siniestro
from nucleo.models import Auditoria, ConjuntoReglas
from nucleo.motor import conjunto_a_dict, evaluar
from tests.conftest import cliente_de

pytestmark = pytest.mark.django_db

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
P17 = {"tipo_identificador": "DNI", "identificador": "30111017", "nombre": "P-17", "roles": ["asegurado"]}
POLIZA = {"numero": "AUT-1", "compania": "Aseguradora Ejemplo S. A.", "cobertura": "Todo riesgo",
          "inicio_vigencia": "2025-01-01", "primer_pago": "2025-01-05"}
IRREGULAR = {"resultado_reclamo": "rechazado", "irregularidad": True, "valoracion": 2, "justificacion": "Adulteración confirmada."}
APROBADO = {"resultado_reclamo": "aprobado", "valoracion": 8, "justificacion": "Sin observaciones."}


def local(anio, mes, dia, hora=12, minuto=0):
    return datetime(anio, mes, dia, hora, minuto, tzinfo=ZONA)


@pytest.fixture
def caso(perito08):
    """Caso analizado: hecho el 15/06/2026 a las 12:00 locales, con P-17 y el vehículo AB123CD."""
    return crear_siniestro(perito08, "EXP-CASO", fecha_hecho=local(2026, 6, 15), poliza=POLIZA, personas=[P17], bienes=["AB123CD"])


def coincidencias(usuario, siniestro):
    return cliente_de(usuario).get(f"/api/siniestros/{siniestro.id}/coincidencias").json()


def evaluacion(usuario, siniestro):
    cliente = cliente_de(usuario)
    assert cliente.post(f"/api/siniestros/{siniestro.id}/recalcular").status_code == 200
    return cliente.get(f"/api/siniestros/{siniestro.id}/evaluacion").json()


def senales(cuerpo):
    return {s["codigo"]: s for s in cuerpo["senales"]}


# --- Coincidencias y promedio ----------------------------------------------------------
def test_s15_la_lista_y_el_promedio_solo_incluyen_antecedentes_anteriores(caso, perito08, perito15):
    crear_siniestro(perito15, "S-ANTERIOR", fecha_hecho=local(2026, 3, 1), personas=[P17], estado="cerrado", cierre=APROBADO)
    crear_siniestro(perito15, "S-POSTERIOR", fecha_hecho=local(2026, 8, 1), personas=[P17], estado="cerrado",
                    cierre=dict(APROBADO, valoracion=2))
    cuerpo = coincidencias(perito08, caso)
    assert [r["numero_expediente"] for r in cuerpo["resultados"]] == ["S-ANTERIOR"]
    assert cuerpo["total"] == 1
    assert cuerpo["promedio_valoracion"] == {"promedio": 8.0, "cantidad": 1}


def test_s15_un_caso_con_solo_antecedentes_posteriores_informa_que_no_hay_antecedentes(caso, perito08, perito15):
    crear_siniestro(perito15, "S-POSTERIOR", fecha_hecho=local(2026, 7, 1), bienes=["AB123CD"])
    cuerpo = coincidencias(perito08, caso)
    assert cuerpo["resultados"] == [] and cuerpo["mensaje_vacio"] == "No hay antecedentes accesibles en la red"


def test_s15_el_mismo_dia_local_no_es_anterior_aunque_la_hora_sea_menor(caso, perito08, perito15):
    crear_siniestro(perito15, "S-MISMO-DIA-ANTES", fecha_hecho=local(2026, 6, 15, 8, 0), bienes=["AB123CD"])
    crear_siniestro(perito15, "S-MISMO-DIA-DESPUES", fecha_hecho=local(2026, 6, 15, 23, 30), bienes=["AB123CD"])
    assert coincidencias(perito08, caso)["resultados"] == []


def test_s15_se_compara_la_fecha_local_y_no_la_de_utc(caso, perito08, perito15):
    # 14/06 22:00 locales = 15/06 01:00 UTC: por la fecha local es del día anterior al hecho
    crear_siniestro(perito15, "S-NOCHE-ANTERIOR", fecha_hecho=local(2026, 6, 14, 22, 0), bienes=["AB123CD"])
    assert [r["numero_expediente"] for r in coincidencias(perito08, caso)["resultados"]] == ["S-NOCHE-ANTERIOR"]


# --- Resumen (A6 sigue rechazando lo que no coincide) --------------------------------------
def test_s15_el_resumen_de_un_posterior_se_rechaza_y_se_audita(caso, perito08, perito15):
    anterior = crear_siniestro(perito15, "S-ANTERIOR", fecha_hecho=local(2026, 3, 1), bienes=["AB123CD"])
    posterior = crear_siniestro(perito15, "S-POSTERIOR", fecha_hecho=local(2026, 8, 1), bienes=["AB123CD"])
    cliente = cliente_de(perito08)
    assert cliente.get(f"/api/siniestros/{caso.id}/antecedentes/{anterior.id}/resumen").status_code == 200
    antes = Auditoria.objects.filter(resultado="rechazado").count()
    respuesta = cliente.get(f"/api/siniestros/{caso.id}/antecedentes/{posterior.id}/resumen")
    assert respuesta.status_code == 404
    assert respuesta.json() == {"detalle": "El antecedente no coincide con el siniestro de origen."}
    assert Auditoria.objects.filter(resultado="rechazado").count() == antes + 1
    registro = Auditoria.objects.filter(resultado="rechazado").latest("id")
    assert registro.accion == "ver_resumen_antecedente" and registro.siniestro_origen_id == caso.id
    assert registro.objeto == f"siniestro:{posterior.id}"


# --- Reglas ---------------------------------------------------------------------------------
def test_s15_r03_r04_y_r05_ignoran_a_la_misma_persona_en_un_caso_posterior(caso, perito08, perito15):
    crear_siniestro(perito15, "S-POSTERIOR", fecha_hecho=local(2026, 6, 25), personas=[dict(P17, roles=["testigo"])])
    cuerpo = evaluacion(perito08, caso)
    for codigo in ("R03", "R04", "R05"):
        assert senales(cuerpo)[codigo]["estado"] == "no_activada", codigo
    assert cuerpo["entradas"]["antecedentes"] == []


def test_s15_r06_ignora_el_mismo_bien_en_un_caso_posterior(caso, perito08, perito15):
    crear_siniestro(perito15, "S-POSTERIOR", fecha_hecho=local(2026, 7, 10), bienes=["AB123CD"])
    assert senales(evaluacion(perito08, caso))["R06"]["estado"] == "no_activada"


def test_s15_r07_ignora_un_posterior_cerrado_con_irregularidad_aunque_no_tenga_limite_de_tiempo(caso, perito08, perito15):
    crear_siniestro(perito15, "S-POSTERIOR-IRREGULAR", fecha_hecho=local(2026, 9, 1), personas=[P17], bienes=["AB123CD"],
                    estado="cerrado", cierre=IRREGULAR)
    cuerpo = evaluacion(perito08, caso)
    assert senales(cuerpo)["R07"]["estado"] == "no_activada"
    assert cuerpo["puntaje"] == 0


def test_s15_r07_sigue_activandose_con_un_anterior_irregular(caso, perito08, perito15):
    crear_siniestro(perito15, "S-ANTERIOR-IRREGULAR", fecha_hecho=local(2024, 1, 10), personas=[P17], estado="cerrado", cierre=IRREGULAR)
    assert senales(evaluacion(perito08, caso))["R07"]["estado"] == "activada"


def test_s15_el_motor_puro_tambien_descarta_antecedentes_que_no_son_anteriores():
    """Aunque las entradas traigan un posterior o uno del mismo día, ninguna regla (R07 incluida) lo cuenta."""
    rs10 = conjunto_a_dict(ConjuntoReglas.objects.get(version="RS-1.0"))
    persona = {"tipo_identificador": "DNI", "identificador": "30111017", "nombre": "P-17", "roles": ["asegurado"]}

    def antecedente(id, fecha):
        return {"id": id, "numero_expediente": f"S-{id}", "fecha_hecho": fecha, "estado": "cerrado", "irregularidad": True,
                "resultado_reclamo": "rechazado", "personas": [persona], "bienes": ["AB123CD"]}

    entradas = {
        "siniestro": {"id": 1, "numero_expediente": "EXP-1", "fecha_hecho": "2026-06-15", "fecha_denuncia": "2026-06-16",
                      "inicio_vigencia": "2025-01-01", "primer_pago": "2025-01-05"},
        "personas": [persona], "bienes": [{"tipo": "vehiculo", "identificador_norm": "AB123CD"}],
        "antecedentes": [antecedente(2, "2026-06-15"), antecedente(3, "2026-06-20"), antecedente(4, "2030-01-01")],
    }
    resultado = evaluar(entradas, rs10)
    assert resultado["puntaje"] == 0
    assert all(s["estado"] != "activada" for s in resultado["senales"])
    entradas["antecedentes"].append(antecedente(5, "2026-06-14"))
    assert {s["codigo"] for s in evaluar(entradas, rs10)["senales"] if s["estado"] == "activada"} == {"R03", "R04", "R06", "R07"}
