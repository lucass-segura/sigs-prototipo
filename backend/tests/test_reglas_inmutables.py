"""F4 · Los puntos de una regla no superan `puntos_max` y las reglas publicadas no se pueden tocar en la base (§7, HU-12)."""
import copy

import pytest
from django.db import DatabaseError, connection, transaction

from nucleo.models import ConjuntoReglas, Regla
from nucleo.motor import conjunto_a_dict, evaluar
from tests.conftest import cliente_de
from tests.test_motor import entradas

pytestmark = pytest.mark.django_db


def sql(consulta, params=None):
    with connection.cursor() as cursor:
        cursor.execute(consulta, params)
        return cursor.fetchall() if cursor.description else None


def publicar(superadmin, version, reglas):
    return cliente_de(superadmin).post(
        "/api/reglas/versiones", {"version": version, "vigente_desde": "2026-12-01", "reglas": reglas}, format="json"
    )


# --- Motor: tope por regla ----------------------------------------------------------
def test_f4_el_motor_nunca_otorga_mas_que_puntos_max():
    conjunto = copy.deepcopy(conjunto_a_dict(ConjuntoReglas.objects.get(version="RS-1.0")))
    for regla in conjunto["reglas"]:
        if regla["codigo"] == "R08":
            regla["parametros"]["puntos"] = 40  # puntos_max sigue en 10
        if regla["codigo"] == "R01":
            regla["parametros"] = {"niveles": [{"max_dias": 400, "puntos": 90}]}  # puntos_max sigue en 25
    resultado = evaluar(entradas(denuncia="2026-06-25"), conjunto)
    por_codigo = {s["codigo"]: s for s in resultado["senales"]}
    assert por_codigo["R08"]["estado"] == "activada" and por_codigo["R08"]["puntos"] == 10
    assert por_codigo["R01"]["estado"] == "activada" and por_codigo["R01"]["puntos"] == 25
    assert all(s["puntos"] <= s["puntos_max"] for s in resultado["senales"])


# --- Publicación: validación --------------------------------------------------------
@pytest.mark.parametrize(
    "cambio",
    [
        {"R02": {"parametros": {"min_dias": 0, "max_dias": 15, "puntos": 21}}},  # puntos_max 20
        {"R01": {"parametros": {"niveles": [{"max_dias": 30, "puntos": 26}, {"max_dias": 60, "puntos": 12}]}}},  # un nivel pasa 25
        {"R03": {"parametros": {"ventana_meses": 12, "niveles": [{"min_antecedentes": 2, "puntos": 20}, {"min_antecedentes": 1, "puntos": 8}]},
                 "puntos_max": 15}},  # baja el máximo por debajo de un nivel
        {"R08": {"puntos_max": 5}},  # baja el máximo por debajo de los puntos actuales (10)
    ],
)
def test_f4_no_se_publica_una_regla_con_puntos_mayores_al_maximo(superadmin, cambio):
    respuesta = publicar(superadmin, "RS-9.0", cambio)
    assert respuesta.status_code == 400, respuesta.content
    mensajes = respuesta.json()["reglas"]
    assert any("no pueden superar" in m and "máximo" in m for m in mensajes)
    assert not ConjuntoReglas.objects.filter(version="RS-9.0").exists()
    assert ConjuntoReglas.objects.get(activo=True).version == "RS-1.0"


def test_f4_subir_el_maximo_junto_con_los_puntos_si_se_publica(superadmin):
    respuesta = publicar(superadmin, "RS-9.1", {"R02": {"parametros": {"min_dias": 0, "max_dias": 15, "puntos": 28}, "puntos_max": 30}})
    assert respuesta.status_code == 201, respuesta.content
    regla = next(r for r in respuesta.json()["reglas"] if r["codigo"] == "R02")
    assert regla["puntos_max"] == 30 and regla["parametros"]["puntos"] == 28


def test_f4_los_puntos_iguales_al_maximo_se_aceptan(superadmin):
    assert publicar(superadmin, "RS-9.2", {"R08": {"parametros": {"plazo_dias": 3, "puntos": 10}}}).status_code == 201


# --- Base: triggers ------------------------------------------------------------------
@pytest.mark.parametrize(
    "sentencia",
    [
        "UPDATE regla SET puntos_max = 1",
        "UPDATE regla SET parametros = '{}'::jsonb",
        "UPDATE regla SET nombre = 'otro'",
        "DELETE FROM regla",
        "UPDATE conjunto_reglas SET version = 'otra'",
        "UPDATE conjunto_reglas SET topes = '{}'::jsonb",
        "UPDATE conjunto_reglas SET vigente_desde = '2000-01-01'",
        "UPDATE conjunto_reglas SET activo = false, version = 'otra'",
        "DELETE FROM conjunto_reglas",
    ],
)
def test_f4_las_reglas_y_los_conjuntos_no_se_modifican_ni_se_borran_con_sql_directo(sentencia):
    with pytest.raises(DatabaseError, match="no se pueden modificar ni borrar|solo puede cambiar"), transaction.atomic():
        sql(sentencia)
    assert Regla.objects.count() == 8 and ConjuntoReglas.objects.count() == 1


def test_f4_un_conjunto_sin_reglas_tampoco_se_puede_borrar():
    conjunto = ConjuntoReglas.objects.create(version="RS-0.1", vigente_desde="2026-01-01", topes={})
    with pytest.raises(DatabaseError), transaction.atomic():
        sql("DELETE FROM conjunto_reglas WHERE id = %s", [conjunto.pk])
    assert ConjuntoReglas.objects.filter(pk=conjunto.pk).exists()


def test_f4_el_campo_activo_si_se_puede_cambiar(superadmin):
    assert publicar(superadmin, "RS-9.3", {}).status_code == 201
    activos = list(ConjuntoReglas.objects.filter(activo=True).values_list("version", flat=True))
    assert activos == ["RS-9.3"]
    sql("UPDATE conjunto_reglas SET activo = true WHERE version = 'RS-1.0' AND NOT EXISTS (SELECT 1 FROM conjunto_reglas WHERE activo AND version <> 'RS-1.0') ")
    assert ConjuntoReglas.objects.get(version="RS-1.0").activo is False
    sql("UPDATE conjunto_reglas SET activo = false WHERE version = 'RS-9.3'")
    sql("UPDATE conjunto_reglas SET activo = true WHERE version = 'RS-1.0'")
    assert ConjuntoReglas.objects.get(activo=True).version == "RS-1.0"


def test_f4_se_puede_publicar_un_cambio_en_los_niveles_de_r01(superadmin):
    niveles = {"niveles": [{"max_dias": 20, "puntos": 25}, {"max_dias": 60, "puntos": 10}]}
    respuesta = publicar(superadmin, "RS-9.4", {"R01": {"parametros": niveles}})
    assert respuesta.status_code == 201, respuesta.content
    assert next(r for r in respuesta.json()["reglas"] if r["codigo"] == "R01")["parametros"] == niveles
