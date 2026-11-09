"""S18 · Un cierre con `irregularidad = true` exige respaldo (E4:1553): un documento del expediente o una observación."""
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from django.utils import timezone

from nucleo.fabrica import crear_siniestro
from nucleo.models import Auditoria, Cierre, Evaluacion, RegistroInmutable, Siniestro
from tests.conftest import cliente_de, cuerpo_siniestro

pytestmark = pytest.mark.django_db

CIERRE = {
    "resultado_reclamo": "rechazado",
    "irregularidad": True,
    "conclusion": "Se confirmó la adulteración de la documentación.",
    "valoracion": 2,
    "justificacion": "La cédula presentada no coincide con el registro.",
}
MENSAJE = "Una irregularidad confirmada necesita respaldo: adjuntá al menos un documento del expediente o escribí una observación."


@pytest.fixture
def caso(perito08):
    cliente = cliente_de(perito08)
    id_ = cliente.post("/api/siniestros", cuerpo_siniestro(confirmar=True), format="json").json()["id"]
    return cliente, id_


def subir(cliente, id_, nombre="foto-cedula.jpg"):
    respuesta = cliente.post(
        f"/api/siniestros/{id_}/documentos",
        {"archivo": SimpleUploadedFile(nombre, b"contenido-ficticio", content_type="image/jpeg"), "tipo": "Fotografía"},
        format="multipart",
    )
    assert respuesta.status_code == 201, respuesta.content
    return respuesta.json()["id"]


def cerrar(cliente, id_, **cambios):
    return cliente.post(f"/api/siniestros/{id_}/cierre", dict(CIERRE, **cambios), format="json")


def sin_cambios(id_):
    assert Cierre.objects.filter(siniestro_id=id_).count() == 0
    assert Siniestro.objects.get(pk=id_).estado == "en_analisis"


# --- Rechazos ------------------------------------------------------------------------------------
@pytest.mark.parametrize("respaldo", [{}, {"observacion_respaldo": ""}, {"observacion_respaldo": "   \n "}, {"documentos_respaldo": []}])
def test_s18_una_irregularidad_sin_respaldo_se_rechaza_y_no_cambia_nada(caso, respaldo):
    cliente, id_ = caso
    antes = Evaluacion.objects.count()
    respuesta = cerrar(cliente, id_, **respaldo)
    assert respuesta.status_code == 400
    assert respuesta.json() == {"respaldo": [MENSAJE]}
    sin_cambios(id_)
    assert Evaluacion.objects.count() == antes


def test_s18_un_documento_de_otro_expediente_no_vale_como_respaldo(caso, perito08):
    cliente, id_ = caso
    otro = cliente.post("/api/siniestros", cuerpo_siniestro(numero_expediente="EXP-OTRO", confirmar=True), format="json").json()["id"]
    ajeno = subir(cliente, otro)
    respuesta = cerrar(cliente, id_, documentos_respaldo=[ajeno])
    assert respuesta.status_code == 400
    assert respuesta.json() == {"documentos_respaldo": ["Algún documento no pertenece a este expediente."]}
    sin_cambios(id_)


def test_s18_un_documento_inexistente_se_rechaza_aunque_haya_observacion(caso):
    cliente, id_ = caso
    respuesta = cerrar(cliente, id_, documentos_respaldo=[999999], observacion_respaldo="Hay observación")
    assert respuesta.status_code == 400
    assert respuesta.json() == {"documentos_respaldo": ["Algún documento no pertenece a este expediente."]}
    sin_cambios(id_)


def test_s18_la_observacion_tiene_un_maximo_de_500_caracteres(caso):
    cliente, id_ = caso
    respuesta = cerrar(cliente, id_, observacion_respaldo="x" * 501)
    assert respuesta.status_code == 400
    assert respuesta.json() == {"observacion_respaldo": ["La observación no puede superar los 500 caracteres."]}
    sin_cambios(id_)
    assert cerrar(cliente, id_, observacion_respaldo="x" * 500).status_code == 201


# --- Aceptación ----------------------------------------------------------------------------------
def test_s18_con_una_observacion_el_cierre_se_guarda_y_queda_en_el_historial(caso):
    cliente, id_ = caso
    respuesta = cerrar(cliente, id_, observacion_respaldo="  Lo constaté en la inspección del 19/08.  ")
    assert respuesta.status_code == 201, respuesta.content
    cierre = respuesta.json()
    assert cierre["observacion_respaldo"] == "Lo constaté en la inspección del 19/08."
    assert cierre["documentos_respaldo"] == []
    historial = cliente.get(f"/api/siniestros/{id_}/cierre").json()
    assert historial["vigente"]["observacion_respaldo"] == "Lo constaté en la inspección del 19/08."
    assert historial["historial"][0]["irregularidad"] is True
    assert cliente.get(f"/api/siniestros/{id_}").json()["cierre_vigente"]["observacion_respaldo"].startswith("Lo constaté")


def test_s18_con_un_documento_del_expediente_el_cierre_se_guarda_y_lo_muestra(caso):
    cliente, id_ = caso
    documento = subir(cliente, id_)
    respuesta = cerrar(cliente, id_, documentos_respaldo=[documento])
    assert respuesta.status_code == 201, respuesta.content
    assert respuesta.json()["documentos_respaldo"] == [{"id": documento, "tipo": "Fotografía", "nombre_original": "foto-cedula.jpg"}]
    assert respuesta.json()["observacion_respaldo"] == ""
    historial = cliente.get(f"/api/siniestros/{id_}/cierre").json()["historial"]
    assert historial[0]["documentos_respaldo"][0]["nombre_original"] == "foto-cedula.jpg"


def test_s18_sin_irregularidad_no_hace_falta_respaldo(caso):
    cliente, id_ = caso
    respuesta = cerrar(cliente, id_, irregularidad=False)
    assert respuesta.status_code == 201
    assert respuesta.json()["documentos_respaldo"] == [] and respuesta.json()["observacion_respaldo"] == ""


def test_s18_al_cambiar_el_cierre_a_irregularidad_tambien_exige_respaldo(caso):
    cliente, id_ = caso
    assert cerrar(cliente, id_, irregularidad=False).status_code == 201
    sin_respaldo = cerrar(cliente, id_, motivo_cambio="Apareció una adulteración.")
    assert sin_respaldo.status_code == 400 and sin_respaldo.json() == {"respaldo": [MENSAJE]}
    assert Cierre.objects.filter(siniestro_id=id_).count() == 1
    con_respaldo = cerrar(cliente, id_, motivo_cambio="Apareció una adulteración.", observacion_respaldo="Cédula adulterada.")
    assert con_respaldo.status_code == 201
    assert [c["irregularidad"] for c in cliente.get(f"/api/siniestros/{id_}/cierre").json()["historial"]] == [False, True]


# --- El resumen no expone el respaldo --------------------------------------------------------------
def test_s18_el_resumen_del_antecedente_solo_muestra_la_marca_de_irregularidad(caso, perito15):
    cliente, id_ = caso
    documento = subir(cliente, id_, nombre="prueba-secreta.jpg")
    assert cerrar(cliente, id_, documentos_respaldo=[documento], observacion_respaldo="Observación reservada del perito.").status_code == 201
    propio = crear_siniestro(perito15, "S-PROPIO", fecha_hecho=timezone.now() + timedelta(days=60), bienes=["AB123CD"])
    resumen = cliente_de(perito15).get(f"/api/siniestros/{propio.pk}/antecedentes/{id_}/resumen")
    assert resumen.status_code == 200, resumen.content
    cuerpo = resumen.json()
    assert cuerpo["irregularidad"] is True
    texto = resumen.content.decode()
    for secreto in ("Observación reservada", "prueba-secreta.jpg", "respaldo"):
        assert secreto not in texto
    assert not any("respaldo" in clave or "documento" in clave for clave in cuerpo)


# --- Inmutabilidad -------------------------------------------------------------------------------
def test_s18_el_cierre_con_respaldo_sigue_siendo_inmutable_en_el_modelo_y_en_la_base(caso):
    cliente, id_ = caso
    cierre = Cierre.objects.get(pk=cerrar(cliente, id_, observacion_respaldo="Constatado.").json()["id"])
    cierre.observacion_respaldo = "Cambiada"
    with pytest.raises(RegistroInmutable):
        cierre.save()
    for sentencia in (
        "UPDATE cierre SET observacion_respaldo = 'cambiada' WHERE id = %s",
        "UPDATE cierre SET documentos_respaldo = '[1]' WHERE id = %s",
        "DELETE FROM cierre WHERE id = %s",
    ):
        with pytest.raises(Exception) as error:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(sentencia, [cierre.pk])
        assert "no se pueden modificar ni borrar" in str(error.value)
    assert Cierre.objects.get(pk=cierre.pk).observacion_respaldo == "Constatado."


def test_s18_el_rechazo_por_falta_de_respaldo_no_deja_filas_de_cierre_ni_auditoria_de_cierre(caso):
    cliente, id_ = caso
    cerrar(cliente, id_)
    assert not Auditoria.objects.filter(accion="cierre").exists()
