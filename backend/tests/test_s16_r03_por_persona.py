"""S16 · R03 cuenta por persona y toma el nivel más alto entre las personas del caso (E4:411)."""
import pytest

from nucleo.fabrica import crear_siniestro
from nucleo.models import ConjuntoReglas
from nucleo.motor import conjunto_a_dict, evaluar
from tests.conftest import cliente_de

pytestmark = pytest.mark.django_db

P17 = {"tipo_identificador": "DNI", "identificador": "30111017", "nombre": "P-17", "roles": ["asegurado"]}
P31 = {"tipo_identificador": "DNI", "identificador": "27333031", "nombre": "P-31", "roles": ["conductor"]}


@pytest.fixture
def rs10():
    return conjunto_a_dict(ConjuntoReglas.objects.get(version="RS-1.0"))


def entradas(antecedentes):
    return {
        "siniestro": {"id": 1, "numero_expediente": "EXP-1", "fecha_hecho": "2026-06-15", "fecha_denuncia": "2026-06-16",
                      "inicio_vigencia": "2025-01-01", "primer_pago": "2025-01-05"},
        "personas": [P17, P31], "bienes": [], "antecedentes": antecedentes,
    }


def antecedente(id, fecha, *personas):
    return {"id": id, "numero_expediente": f"S-{id}", "fecha_hecho": fecha, "estado": "cerrado", "irregularidad": False,
            "resultado_reclamo": "aprobado", "personas": list(personas), "bienes": []}


def r03(resultado):
    return next(s for s in resultado["senales"] if s["codigo"] == "R03")


def test_s16_dos_personas_con_un_antecedente_cada_una_dan_8_y_no_20(rs10):
    resultado = evaluar(entradas([antecedente(1, "2026-01-10", P17), antecedente(2, "2025-11-20", P31)]), rs10)
    senal = r03(resultado)
    assert senal["estado"] == "activada" and senal["puntos"] == 8
    assert resultado["puntaje"] == 8
    # nombra a las dos personas usadas y lista los dos antecedentes
    assert senal["texto"] == (
        "P-17 figura en 1 siniestro válido de los últimos 12 meses: S-1. "
        "P-31 figura en 1 siniestro válido de los últimos 12 meses: S-2."
    )
    assert [a["numero_expediente"] for a in senal["antecedentes"]] == ["S-1", "S-2"]


def test_s16_gana_el_nivel_mas_alto_y_el_texto_nombra_solo_a_la_persona_que_lo_alcanza(rs10):
    resultado = evaluar(entradas([
        antecedente(1, "2026-01-10", P17), antecedente(2, "2025-11-20", P17), antecedente(3, "2026-02-01", P31),
    ]), rs10)
    senal = r03(resultado)
    assert senal["puntos"] == 20
    assert senal["texto"] == "P-17 figura en 2 siniestros válidos de los últimos 12 meses: S-1, S-2."
    assert "P-31" not in senal["texto"]
    assert [a["numero_expediente"] for a in senal["antecedentes"]] == ["S-1", "S-2"]


def test_s16_si_las_dos_personas_alcanzan_el_nivel_mas_alto_se_nombran_las_dos(rs10):
    resultado = evaluar(entradas([
        antecedente(1, "2026-01-10", P17), antecedente(2, "2025-11-20", P17),
        antecedente(3, "2026-02-01", P31), antecedente(4, "2025-12-01", P31),
    ]), rs10)
    senal = r03(resultado)
    assert senal["puntos"] == 20
    assert "P-17 figura en 2 siniestros" in senal["texto"] and "P-31 figura en 2 siniestros" in senal["texto"]


def test_s16_un_mismo_antecedente_compartido_por_dos_personas_cuenta_uno_por_persona(rs10):
    resultado = evaluar(entradas([antecedente(1, "2026-01-10", P17, P31)]), rs10)
    senal = r03(resultado)
    assert senal["puntos"] == 8
    assert [a["numero_expediente"] for a in senal["antecedentes"]] == ["S-1"]
    assert "P-17" in senal["texto"] and "P-31" in senal["texto"]


def test_s16_una_sola_persona_conserva_el_texto_y_los_puntos_de_siempre(rs10):
    solo = dict(entradas([antecedente(1, "2026-01-10", P17), antecedente(2, "2025-11-20", P17)]), personas=[P17])
    senal = r03(evaluar(solo, rs10))
    assert senal["puntos"] == 20
    assert senal["texto"] == "P-17 figura en 2 siniestros válidos de los últimos 12 meses: S-1, S-2."


def test_s16_por_la_api_dos_personas_con_un_antecedente_cada_una_suman_8(perito08, perito15):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    zona = ZoneInfo("America/Argentina/Buenos_Aires")
    caso = crear_siniestro(perito08, "EXP-CASO", fecha_hecho=datetime(2026, 6, 15, 12, tzinfo=zona),
                           poliza={"numero": "AUT-1", "inicio_vigencia": "2025-01-01", "primer_pago": "2025-01-05"},
                           personas=[P17, P31])
    crear_siniestro(perito15, "S-DE-P17", fecha_hecho=datetime(2026, 1, 10, 12, tzinfo=zona), personas=[P17])
    crear_siniestro(perito15, "S-DE-P31", fecha_hecho=datetime(2025, 11, 20, 12, tzinfo=zona), personas=[P31])
    cliente = cliente_de(perito08)
    assert cliente.post(f"/api/siniestros/{caso.id}/recalcular").status_code == 200
    cuerpo = cliente.get(f"/api/siniestros/{caso.id}/evaluacion").json()
    senal = next(s for s in cuerpo["senales"] if s["codigo"] == "R03")
    assert senal["puntos"] == 8 and cuerpo["puntaje"] == 8
    assert "P-17" in senal["texto"] and "P-31" in senal["texto"]
