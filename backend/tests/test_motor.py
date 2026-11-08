"""T08 · Motor de reglas RS-1.0 (función pura `evaluar`): reglas, topes, prioridad y reproducibilidad."""
import copy
import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from nucleo.motor import conjunto_a_dict, evaluar
from nucleo.models import ConjuntoReglas

pytestmark = pytest.mark.django_db


@pytest.fixture
def rs10():
    return conjunto_a_dict(ConjuntoReglas.objects.get(version="RS-1.0"))


def persona(identificador="30111017", nombre="P-17", roles=("asegurado",)):
    return {"tipo_identificador": "DNI", "identificador": identificador, "nombre": nombre, "roles": list(roles)}


def antecedente(id, fecha, personas=(), bienes=(), estado="cerrado", irregularidad=False, numero=None):
    return {
        "id": id, "numero_expediente": numero or f"S-{id}", "fecha_hecho": fecha, "estado": estado,
        "irregularidad": irregularidad, "resultado_reclamo": "aprobado" if estado in ("cerrado", "archivado") else None,
        "personas": list(personas), "bienes": list(bienes),
    }


def entradas(hecho="2026-06-15", vigencia="2025-05-11", pago="2025-05-11", denuncia="2026-06-16", antecedentes=(), roles=("asegurado",)):
    return {
        "siniestro": {"id": 1, "numero_expediente": "EXP-1", "fecha_hecho": hecho, "fecha_denuncia": denuncia,
                      "inicio_vigencia": vigencia, "primer_pago": pago},
        "personas": [persona(roles=roles)],
        "bienes": [{"tipo": "vehiculo", "identificador_norm": "AB123CD"}],
        "antecedentes": list(antecedentes),
    }


def activadas(resultado):
    return {s["codigo"]: s["puntos"] for s in resultado["senales"] if s["estado"] == "activada"}


def senal(resultado, codigo):
    return next(s for s in resultado["senales"] if s["codigo"] == codigo)


def test_evaluar_es_pura_y_no_lee_la_base(rs10):
    with CaptureQueriesContext(connection) as consultas:
        evaluar(entradas(), rs10)
    assert len(consultas) == 0


def test_ejemplo_de_control_tabla_9_da_53_alta(rs10):
    # vigencia 20 días antes, pago 10 días antes, un previo de la persona hace 60 días
    caso = entradas(vigencia="2026-05-26", pago="2026-06-05", antecedentes=[antecedente(1, "2026-04-16", personas=[persona()])])
    resultado = evaluar(caso, rs10)
    assert activadas(resultado) == {"R01": 25, "R02": 20, "R03": 8, "R04": 15}
    assert resultado["grupos"]["Cobertura"] == {"bruto": 45, "tope": 30, "puntos": 30}
    assert resultado["grupos"]["Persona"] == {"bruto": 23, "tope": 35, "puntos": 23}
    assert resultado["puntaje"] == 53 and resultado["prioridad"] == "alta"
    assert resultado["version"] == "RS-1.0"


@pytest.mark.parametrize(
    "dias, puntos",
    [(0, 25), (20, 25), (30, 25), (31, 12), (40, 12), (60, 12), (61, None), (75, None)],
)
def test_r01_cobertura_reciente_por_niveles(rs10, dias, puntos):
    from datetime import date, timedelta

    hecho = date(2026, 6, 15)
    resultado = evaluar(entradas(vigencia=(hecho - timedelta(days=dias)).isoformat(), pago="2025-01-01"), rs10)
    r01 = senal(resultado, "R01")
    if puntos is None:
        assert r01["estado"] == "no_activada" and r01["puntos"] == 0
    else:
        assert r01["estado"] == "activada" and r01["puntos"] == puntos


def test_r01_el_texto_sale_de_la_misma_senal(rs10):
    caso = entradas(hecho="2026-08-12", vigencia="2026-07-20", pago="2026-08-04")
    resultado = evaluar(caso, rs10)
    assert senal(resultado, "R01")["texto"] == "El hecho ocurrió 23 días después del inicio de vigencia. Umbral 30 días."
    assert senal(resultado, "R02")["texto"] == "El primer pago se registró 8 días antes del hecho. Umbral 15 días."
    caso40 = entradas(vigencia="2026-05-06", pago="2025-01-01")
    assert senal(evaluar(caso40, rs10), "R01")["texto"] == "El hecho ocurrió 40 días después del inicio de vigencia. Umbral 60 días."


@pytest.mark.parametrize("dias, activa", [(0, True), (10, True), (15, True), (16, False), (40, False), (-3, False)])
def test_r02_pago_reciente_y_pago_posterior_al_hecho(rs10, dias, activa):
    from datetime import date, timedelta

    pago = (date(2026, 6, 15) - timedelta(days=dias)).isoformat()
    resultado = evaluar(entradas(pago=pago), rs10)
    assert (senal(resultado, "R02")["estado"] == "activada") is activa


@pytest.mark.parametrize("dato, regla, fragmento", [("vigencia", "R01", "inicio de vigencia"), ("pago", "R02", "primer pago"), ("denuncia", "R08", "denuncia")])
def test_las_reglas_sin_fecha_son_no_evaluables_suman_cero_e_indican_el_dato(rs10, dato, regla, fragmento):
    resultado = evaluar(entradas(**{dato: None}), rs10)
    s = senal(resultado, regla)
    assert s["estado"] == "no_evaluable" and s["puntos"] == 0
    assert s["texto"].startswith("No se pudo evaluar: falta la fecha") and fragmento in s["texto"]


def test_r03_cuenta_antecedentes_distintos_con_cualquier_rol_en_12_meses(rs10):
    p_testigo = persona(roles=("testigo",))
    uno = evaluar(entradas(antecedentes=[antecedente(1, "2026-01-15", personas=[p_testigo])]), rs10)
    assert senal(uno, "R03")["puntos"] == 8
    dos = evaluar(entradas(antecedentes=[antecedente(1, "2026-01-15", personas=[p_testigo]), antecedente(2, "2025-11-20", personas=[persona()])]), rs10)
    r03 = senal(dos, "R03")
    assert r03["puntos"] == 20 and [a["id"] for a in r03["antecedentes"]] == [1, 2]
    assert "2 siniestros válidos de los últimos 12 meses" in r03["texto"]
    fuera = evaluar(entradas(antecedentes=[antecedente(1, "2025-06-15", personas=[persona()])]), rs10)  # justo 12 meses
    assert senal(fuera, "R03")["puntos"] == 8
    mas_viejo = evaluar(entradas(antecedentes=[antecedente(1, "2025-06-14", personas=[persona()])]), rs10)
    assert senal(mas_viejo, "R03")["estado"] == "no_activada"
    assert "no tiene otros siniestros válidos" in senal(mas_viejo, "R03")["texto"]


def test_r04_limite_de_90_dias_y_el_mismo_dia_no_cuenta(rs10):
    from datetime import date, timedelta

    hecho = date(2026, 6, 15)
    for dias, activa in ((45, True), (90, True), (91, False), (150, False), (0, False)):
        previo = antecedente(1, (hecho - timedelta(days=dias)).isoformat(), personas=[persona()])
        assert (senal(evaluar(entradas(antecedentes=[previo]), rs10), "R04")["estado"] == "activada") is activa, dias


def test_r05_rol_cruzado_dentro_de_24_meses(rs10):
    testigo = persona(roles=("testigo",))
    activa = evaluar(entradas(antecedentes=[antecedente(1, "2025-08-15", personas=[testigo])]), rs10)
    assert senal(activa, "R05")["puntos"] == 15
    assert "P-17 figura como testigo en S-1 de hace 10 meses. En este caso es asegurado." == senal(activa, "R05")["texto"]
    mismo_rol = evaluar(entradas(antecedentes=[antecedente(1, "2024-12-15", personas=[persona()])]), rs10)
    assert senal(mismo_rol, "R05")["estado"] == "no_activada"
    muy_viejo = evaluar(entradas(antecedentes=[antecedente(1, "2024-05-15", personas=[testigo])]), rs10)
    assert senal(muy_viejo, "R05")["estado"] == "no_activada"


def test_r06_bien_repetido_en_24_meses_por_identificador_normalizado(rs10):
    previo = antecedente(2381, "2025-07-10", bienes=["AB123CD"], numero="S-2025-0381")
    resultado = evaluar(entradas(hecho="2026-08-12", vigencia="2025-01-01", pago="2025-01-01", denuncia="2026-08-13", antecedentes=[previo]), rs10)
    r06 = senal(resultado, "R06")
    assert r06["puntos"] == 25
    assert r06["texto"] == "El vehículo AB123CD figura en el antecedente S-2025-0381 de hace 13 meses."
    otro = evaluar(entradas(antecedentes=[antecedente(2, "2025-08-15", bienes=["ZZ999ZZ"])]), rs10)
    assert senal(otro, "R06")["estado"] == "no_activada"


def test_r07_solo_con_cierre_irregular_y_sin_limite_de_tiempo(rs10):
    irregular = antecedente(1, "2023-01-10", bienes=["AB123CD"], irregularidad=True)
    resultado = evaluar(entradas(antecedentes=[irregular]), rs10)
    r07 = senal(resultado, "R07")
    assert r07["puntos"] == 30 and "cerrado con irregularidad confirmada" in r07["texto"]
    sin_irregularidad = evaluar(entradas(antecedentes=[antecedente(1, "2023-01-10", bienes=["AB123CD"])]), rs10)
    assert senal(sin_irregularidad, "R07")["estado"] == "no_activada"
    en_analisis = antecedente(1, "2026-01-10", bienes=["AB123CD"], estado="en_analisis", irregularidad=True)
    assert senal(evaluar(entradas(antecedentes=[en_analisis]), rs10), "R07")["estado"] == "no_activada"
    archivado = antecedente(1, "2023-01-10", bienes=["AB123CD"], estado="archivado", irregularidad=True)
    assert senal(evaluar(entradas(antecedentes=[archivado]), rs10), "R07")["puntos"] == 30


@pytest.mark.parametrize("dias, activa", [(1, False), (3, False), (4, True), (5, True)])
def test_r08_denuncia_tardia(rs10, dias, activa):
    from datetime import date, timedelta

    denuncia = (date(2026, 6, 15) + timedelta(days=dias)).isoformat()
    s = senal(evaluar(entradas(denuncia=denuncia), rs10), "R08")
    assert (s["estado"] == "activada") is activa


def test_cada_regla_se_activa_una_sola_vez_y_lista_todos_los_antecedentes(rs10):
    previos = [antecedente(i, f"2026-0{i}-10", personas=[persona()]) for i in (1, 2, 3)]
    r03 = senal(evaluar(entradas(antecedentes=previos), rs10), "R03")
    assert r03["puntos"] == 20
    assert [a["numero_expediente"] for a in r03["antecedentes"]] == ["S-1", "S-2", "S-3"]
    assert set(r03["antecedentes"][0]) == {"id", "numero_expediente", "fecha_hecho", "vinculo"}


def test_un_mismo_antecedente_activa_reglas_de_grupos_distintos(rs10):
    previo = antecedente(1, "2025-10-10", bienes=["AB123CD"], irregularidad=True)
    resultado = evaluar(entradas(antecedentes=[previo]), rs10)
    assert activadas(resultado) == {"R06": 25, "R07": 30}
    assert resultado["puntaje"] == 55 and resultado["prioridad"] == "alta"


def test_los_topes_por_grupo_y_el_total_de_100(rs10):
    # C5: cumple las 8 reglas
    a1 = antecedente(1, "2026-05-16", personas=[persona()])
    a2 = antecedente(2, "2025-11-27", personas=[persona(roles=("testigo",))], bienes=["AB123CD"])
    a3 = antecedente(3, "2025-05-11", bienes=["AB123CD"], irregularidad=True)
    caso = entradas(vigencia="2026-06-05", pago="2026-06-10", denuncia="2026-06-25", antecedentes=[a1, a2, a3])
    resultado = evaluar(caso, rs10)
    assert set(activadas(resultado)) == {f"R0{i}" for i in range(1, 9)}
    assert sum(activadas(resultado).values()) == 160
    assert {g: v["puntos"] for g, v in resultado["grupos"].items()} == {
        "Cobertura": 30, "Persona": 35, "Bien": 25, "Antecedente": 30, "Denuncia": 10,
    }
    assert resultado["puntaje"] == 100 and resultado["prioridad"] == "alta"


@pytest.mark.parametrize("puntaje_objetivo, prioridad", [(0, "baja"), (24, "baja"), (25, "media"), (49, "media"), (50, "alta")])
def test_la_prioridad_se_toma_de_los_umbrales_del_conjunto(rs10, puntaje_objetivo, prioridad):
    # se reutiliza R08 con puntos ajustados para cubrir los bordes 24/25 y 49/50
    conjunto = copy.deepcopy(rs10)
    conjunto["topes"]["grupos"]["Denuncia"] = 100
    for regla in conjunto["reglas"]:
        if regla["codigo"] == "R08":
            regla["parametros"]["puntos"] = puntaje_objetivo
    resultado = evaluar(entradas(denuncia="2026-06-25"), conjunto)
    assert resultado["puntaje"] == puntaje_objetivo and resultado["prioridad"] == prioridad


def test_los_umbrales_y_puntos_salen_de_los_parametros_no_del_codigo(rs10):
    nuevo = copy.deepcopy(rs10)
    for regla in nuevo["reglas"]:
        if regla["codigo"] == "R08":
            regla["parametros"] = {"plazo_dias": 10, "puntos": 7}
        if regla["codigo"] == "R01":
            regla["parametros"] = {"niveles": [{"max_dias": 400, "puntos": 3}]}
    caso = entradas(denuncia="2026-06-25")  # 10 días: ya no es tardía con plazo de 10
    resultado = evaluar(caso, nuevo)
    assert senal(resultado, "R08")["estado"] == "no_activada"
    assert senal(resultado, "R01")["puntos"] == 3  # vigencia a 400 días
    assert senal(evaluar(caso, rs10), "R08")["puntos"] == 10


def test_reproducibilidad_mismas_entradas_y_misma_version_dan_el_mismo_resultado(rs10):
    a1 = antecedente(1, "2026-05-16", personas=[persona()], bienes=["AB123CD"])
    caso = entradas(vigencia="2026-06-05", pago="2026-06-10", antecedentes=[a1])
    primero = evaluar(caso, rs10)
    # incluso después de pasar las entradas por JSON, como cuando se guardan en la base
    segundo = evaluar(json.loads(json.dumps(caso)), copy.deepcopy(rs10))
    assert primero == segundo
    assert json.dumps(primero, sort_keys=True) == json.dumps(segundo, sort_keys=True)
