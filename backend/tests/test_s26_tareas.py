"""S26 · Tareas: `GET /api/tareas` con filtro opcional por estado (sin parámetro, solo las no hechas)."""
from datetime import date, timedelta

import pytest

from nucleo.fabrica import crear_siniestro
from nucleo.models import Tarea
from tests.conftest import cliente_de

pytestmark = pytest.mark.django_db


def _tarea(siniestro, titulo, estado, vence=None):
    return Tarea.objects.create(siniestro=siniestro, titulo=titulo, estado=estado, vence_en=vence)


@pytest.fixture
def caso(perito08):
    return crear_siniestro(perito08, "EXP-T-1")


@pytest.fixture
def tareas(caso):
    hoy = date.today()
    _tarea(caso, "Pendiente sin fecha", Tarea.PENDIENTE)
    _tarea(caso, "Pendiente mañana", Tarea.PENDIENTE, hoy + timedelta(days=1))
    _tarea(caso, "En curso vencida", Tarea.EN_CURSO, hoy - timedelta(days=3))
    _tarea(caso, "Hecha", Tarea.HECHA, hoy - timedelta(days=10))


def titulos(respuesta):
    assert respuesta.status_code == 200, respuesta.content
    return [t["titulo"] for t in respuesta.json()]


def test_s26_sin_parametros_devuelve_solo_las_no_hechas_ordenadas_por_vencimiento(perito08, tareas):
    assert titulos(cliente_de(perito08).get("/api/tareas")) == ["En curso vencida", "Pendiente mañana", "Pendiente sin fecha"]


@pytest.mark.parametrize(
    "estado, esperado",
    [
        ("pendiente", ["Pendiente mañana", "Pendiente sin fecha"]),
        ("en_curso", ["En curso vencida"]),
        ("hecha", ["Hecha"]),
        ("todas", ["Hecha", "En curso vencida", "Pendiente mañana", "Pendiente sin fecha"]),
    ],
)
def test_s26_el_parametro_estado_filtra_las_tareas(perito08, tareas, estado, esperado):
    assert titulos(cliente_de(perito08).get("/api/tareas", {"estado": estado})) == esperado


def test_s26_un_estado_invalido_se_rechaza_con_400(perito08, tareas):
    respuesta = cliente_de(perito08).get("/api/tareas", {"estado": "cualquiera"})
    assert respuesta.status_code == 400 and "estado" in respuesta.json()


def test_s26_con_el_filtro_siguen_apareciendo_solo_las_tareas_de_expedientes_propios(perito08, perito11, tareas):
    ajeno = crear_siniestro(perito11, "EXP-T-2")
    _tarea(ajeno, "De otro perito", Tarea.PENDIENTE)
    assert "De otro perito" not in titulos(cliente_de(perito08).get("/api/tareas", {"estado": "todas"}))
    assert titulos(cliente_de(perito11).get("/api/tareas", {"estado": "todas"})) == ["De otro perito"]


def test_s26_cada_tarea_trae_su_expediente_para_enlazarlo(perito08, tareas):
    primera = cliente_de(perito08).get("/api/tareas", {"estado": "hecha"}).json()[0]
    assert primera["siniestro"]["numero_expediente"] == "EXP-T-1" and "tipo" in primera["siniestro"]
