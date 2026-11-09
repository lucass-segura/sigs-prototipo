"""S20 · Conclusión del cierre obligatoria, escala de valoración con el texto completo de la tabla 2 del E4 y
correo de contacto del perito solo en los resúmenes de casos cerrados o archivados (HU-17, criterio 1)."""
from datetime import timedelta

import pytest
from django.utils import timezone

from nucleo.fabrica import crear_siniestro
from nucleo.models import Cierre, Siniestro
from tests.conftest import cliente_de, cuerpo_siniestro

pytestmark = pytest.mark.django_db

CIERRE = {
    "resultado_reclamo": "aprobado",
    "irregularidad": False,
    "conclusion": "Hecho verificado con observaciones. No encuentro elementos que contradigan el relato.",
    "valoracion": 8,
    "justificacion": "Póliza reciente, pero la inspección coincide con el relato.",
}
ESCALA = {
    1: "El hecho no pudo verificarse y hay elementos que lo contradicen.",
    2: "El hecho no pudo verificarse y hay elementos que lo contradicen.",
    3: "Hay inconsistencias relevantes que no se pudieron aclarar.",
    4: "Hay inconsistencias relevantes que no se pudieron aclarar.",
    5: "Hay dudas concretas sin elementos suficientes para confirmarlas ni descartarlas.",
    6: "Hay dudas concretas sin elementos suficientes para confirmarlas ni descartarlas.",
    7: "El hecho se verificó con observaciones menores o documentación incompleta.",
    8: "El hecho se verificó con observaciones menores o documentación incompleta.",
    9: "El hecho se verificó sin observaciones.",
    10: "El hecho se verificó sin observaciones.",
}


@pytest.fixture
def caso(perito08):
    cliente = cliente_de(perito08)
    id_ = cliente.post("/api/siniestros", cuerpo_siniestro(confirmar=True), format="json").json()["id"]
    return cliente, id_


# --- Conclusión obligatoria ----------------------------------------------------------------------
@pytest.mark.parametrize("conclusion", ["", "   ", "\n\t", None, "falta"])
def test_s20_el_cierre_no_se_guarda_sin_conclusion(caso, conclusion):
    cliente, id_ = caso
    cuerpo = dict(CIERRE, conclusion=conclusion)
    if conclusion == "falta":
        del cuerpo["conclusion"]
    respuesta = cliente.post(f"/api/siniestros/{id_}/cierre", cuerpo, format="json")
    assert respuesta.status_code == 400
    assert respuesta.json() == {"conclusion": ["La conclusión es obligatoria."]}
    assert Cierre.objects.count() == 0 and Siniestro.objects.get(pk=id_).estado == "en_analisis"


def test_s20_con_conclusion_el_cierre_se_guarda_recortada(caso):
    cliente, id_ = caso
    respuesta = cliente.post(f"/api/siniestros/{id_}/cierre", dict(CIERRE, conclusion="  Hecho verificado.  "), format="json")
    assert respuesta.status_code == 201
    assert respuesta.json()["conclusion"] == "Hecho verificado."


def test_s20_al_cambiar_el_cierre_la_conclusion_tambien_es_obligatoria(caso):
    cliente, id_ = caso
    assert cliente.post(f"/api/siniestros/{id_}/cierre", CIERRE, format="json").status_code == 201
    respuesta = cliente.post(f"/api/siniestros/{id_}/cierre", dict(CIERRE, conclusion="", motivo_cambio="Revisión"), format="json")
    assert respuesta.status_code == 400 and respuesta.json() == {"conclusion": ["La conclusión es obligatoria."]}
    assert Cierre.objects.count() == 1


# --- Escala de la tabla 2 -------------------------------------------------------------------------
@pytest.mark.parametrize("valoracion", range(1, 11))
def test_s20_la_escala_usa_el_texto_completo_de_la_tabla_2(perito08, valoracion):
    cliente = cliente_de(perito08)
    id_ = cliente.post("/api/siniestros", cuerpo_siniestro(confirmar=True), format="json").json()["id"]
    respuesta = cliente.post(f"/api/siniestros/{id_}/cierre", dict(CIERRE, valoracion=valoracion), format="json")
    assert respuesta.status_code == 201, respuesta.content
    assert respuesta.json()["valoracion_texto"] == ESCALA[valoracion]
    assert cliente.get(f"/api/siniestros/{id_}/cierre").json()["vigente"]["valoracion_texto"] == ESCALA[valoracion]


def test_s20_el_resumen_del_antecedente_trae_el_texto_de_la_escala(perito08, perito15):
    antecedente = crear_siniestro(
        perito15, "S-CERRADO", fecha_hecho=timezone.now() - timedelta(days=100), bienes=["AB123CD"], estado="cerrado",
        cierre={"resultado_reclamo": "aprobado", "valoracion": 5, "conclusion": "Dudas.", "justificacion": "Dudas concretas."},
    )
    origen = crear_siniestro(perito08, "EXP-ORIGEN", fecha_hecho=timezone.now(), bienes=["AB123CD"])
    resumen = cliente_de(perito08).get(f"/api/siniestros/{origen.pk}/antecedentes/{antecedente.pk}/resumen").json()
    assert resumen["valoracion"] == 5 and resumen["valoracion_texto"] == ESCALA[5]


# --- HU-17 criterio 1: el correo solo aparece en los resúmenes de casos cerrados -----------------------
@pytest.mark.parametrize("estado, aparece", [("en_analisis", False), ("cerrado", True), ("archivado", True)])
def test_s20_el_correo_de_contacto_solo_aparece_si_el_antecedente_esta_cerrado_o_archivado(perito08, perito15, estado, aparece):
    cierre = {"resultado_reclamo": "aprobado", "valoracion": 7, "conclusion": "Verificado.", "justificacion": "Sin observaciones."}
    antecedente = crear_siniestro(
        perito15, "S-ANT", fecha_hecho=timezone.now() - timedelta(days=100), bienes=["AB123CD"], estado=estado,
        cierre=None if estado == "en_analisis" else cierre,
    )
    origen = crear_siniestro(perito08, "EXP-ORIGEN", fecha_hecho=timezone.now(), bienes=["AB123CD"])
    resumen = cliente_de(perito08).get(f"/api/siniestros/{origen.pk}/antecedentes/{antecedente.pk}/resumen").json()
    assert resumen["contacto_perito"] == ({"email": "pe15@correo.test"} if aparece else None)
    assert ("pe15@correo.test" in str(resumen)) is aparece


def test_s20_un_contacto_no_visible_nunca_aparece_aunque_el_caso_este_cerrado(perito08, perito11):
    antecedente = crear_siniestro(
        perito11, "S-ANT", fecha_hecho=timezone.now() - timedelta(days=100), bienes=["AB123CD"], estado="cerrado",
        cierre={"resultado_reclamo": "aprobado", "valoracion": 7, "conclusion": "Verificado.", "justificacion": "Sin observaciones."},
    )
    origen = crear_siniestro(perito08, "EXP-ORIGEN", fecha_hecho=timezone.now(), bienes=["AB123CD"])
    resumen = cliente_de(perito08).get(f"/api/siniestros/{origen.pk}/antecedentes/{antecedente.pk}/resumen").json()
    assert resumen["contacto_perito"] is None and "pe11@correo.test" not in str(resumen)
