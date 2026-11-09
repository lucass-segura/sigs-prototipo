"""S34 · Confirmar exige el número de póliza y la fecha del hecho no puede ser futura.

- Confirmar (POST /siniestros/<id>/confirmar y POST /siniestros con `confirmar: true`) sin número de póliza → 400
  con el mensaje de confirmación de siempre. Un borrador sí puede guardarse sin número.
- La fecha del hecho (fecha y hora locales) no puede ser posterior al momento actual, con una tolerancia de 5 minutos
  por diferencias de reloj: 400 `{"fecha_hecho": [...]}` al crear, editar y confirmar. Un pedido rechazado no guarda nada.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone

from nucleo.models import Auditoria, Evaluacion, Persona, Poliza, Siniestro
from tests.conftest import cliente_de, cuerpo_siniestro

pytestmark = pytest.mark.django_db

MENSAJE_CONFIRMAR = {"detalle": "Para confirmar hacen falta la póliza, la fecha del hecho y al menos una persona o un bien."}
MENSAJE_FUTURA = {"fecha_hecho": ["La fecha del hecho no puede ser futura."]}


@pytest.fixture
def ahora(monkeypatch):
    """Congela el reloj en el instante actual: así los límites de 5 minutos se prueban sin margen de azar."""
    instante = timezone.now()
    monkeypatch.setattr(timezone, "now", lambda: instante)
    return instante


def poliza_con(**cambios):
    return dict(cuerpo_siniestro()["poliza"], **cambios)


def hecho_en(ahora, **desfase):
    return (ahora + timedelta(**desfase)).isoformat()


def sin_cambios_en_la_base():
    return (Siniestro.objects.count(), Poliza.objects.count(), Persona.objects.count(), Evaluacion.objects.count(),
            Auditoria.objects.filter(accion__in=["crear_siniestro", "confirmar_siniestro"]).count())


# --- Número de póliza al confirmar ---------------------------------------------------------------
@pytest.mark.parametrize("poliza", [
    poliza_con(numero=""),
    poliza_con(numero="   "),
    {"compania": "Aseguradora Ejemplo S. A.", "cobertura": "Todo riesgo"},  # sin la clave `numero`
])
def test_s34_confirmar_un_borrador_sin_numero_de_poliza_se_rechaza_y_no_cambia_nada(perito08, poliza):
    cliente = cliente_de(perito08)
    creado = cliente.post("/api/siniestros", cuerpo_siniestro(poliza=poliza), format="json")
    assert creado.status_code == 201, creado.content  # un borrador puede guardarse sin número
    antes = sin_cambios_en_la_base()
    respuesta = cliente.post(f"/api/siniestros/{creado.json()['id']}/confirmar")
    assert respuesta.status_code == 400
    assert respuesta.json() == MENSAJE_CONFIRMAR
    assert sin_cambios_en_la_base() == antes
    siniestro = Siniestro.objects.get(pk=creado.json()["id"])
    assert siniestro.estado == "borrador" and siniestro.confirmado_en is None


@pytest.mark.parametrize("poliza", [poliza_con(numero=""), poliza_con(numero="  ")])
def test_s34_crear_con_confirmar_y_sin_numero_de_poliza_se_rechaza_y_no_deja_basura(perito08, poliza):
    respuesta = cliente_de(perito08).post("/api/siniestros", cuerpo_siniestro(poliza=poliza, confirmar=True), format="json")
    assert respuesta.status_code == 400
    assert respuesta.json() == MENSAJE_CONFIRMAR
    assert Siniestro.objects.count() == 0 and Poliza.objects.count() == 0 and Persona.objects.count() == 0
    assert not Auditoria.objects.filter(accion="crear_siniestro").exists()


def test_s34_cargar_el_numero_de_poliza_habilita_la_confirmacion(perito08):
    cliente = cliente_de(perito08)
    id_ = cliente.post("/api/siniestros", cuerpo_siniestro(poliza=poliza_con(numero="")), format="json").json()["id"]
    assert cliente.post(f"/api/siniestros/{id_}/confirmar").status_code == 400
    editado = cliente.patch(f"/api/siniestros/{id_}", {"poliza": poliza_con(numero="AUT-000123")}, format="json")
    assert editado.status_code == 200, editado.content
    confirmado = cliente.post(f"/api/siniestros/{id_}/confirmar")
    assert confirmado.status_code == 200, confirmado.content
    assert confirmado.json()["estado"] == "en_analisis"


# --- Fecha del hecho no futura -------------------------------------------------------------------
def test_s34_crear_con_una_fecha_futura_se_rechaza_y_no_guarda_nada(perito08, ahora):
    antes = sin_cambios_en_la_base()
    respuesta = cliente_de(perito08).post("/api/siniestros", cuerpo_siniestro(fecha_hecho=hecho_en(ahora, days=1)), format="json")
    assert respuesta.status_code == 400
    assert respuesta.json() == MENSAJE_FUTURA
    assert sin_cambios_en_la_base() == antes


def test_s34_crear_con_confirmar_y_fecha_futura_se_rechaza_y_no_deja_basura(perito08, ahora):
    respuesta = cliente_de(perito08).post(
        "/api/siniestros", cuerpo_siniestro(fecha_hecho=hecho_en(ahora, hours=3), confirmar=True), format="json")
    assert respuesta.status_code == 400 and respuesta.json() == MENSAJE_FUTURA
    assert Siniestro.objects.count() == 0 and Evaluacion.objects.count() == 0


def test_s34_la_tolerancia_de_reloj_es_de_cinco_minutos(perito08, ahora):
    cliente = cliente_de(perito08)
    assert cliente.post("/api/siniestros", cuerpo_siniestro(fecha_hecho=hecho_en(ahora, minutes=5)), format="json").status_code == 201
    rechazada = cliente.post(
        "/api/siniestros", cuerpo_siniestro(numero_expediente="EXP-LIMITE", fecha_hecho=hecho_en(ahora, minutes=5, seconds=1)), format="json")
    assert rechazada.status_code == 400 and rechazada.json() == MENSAJE_FUTURA
    assert not Siniestro.objects.filter(numero_expediente="EXP-LIMITE").exists()


def test_s34_el_momento_actual_y_el_pasado_se_aceptan(perito08, ahora):
    cliente = cliente_de(perito08)
    assert cliente.post("/api/siniestros", cuerpo_siniestro(numero_expediente="EXP-A", fecha_hecho=hecho_en(ahora)), format="json").status_code == 201
    assert cliente.post("/api/siniestros", cuerpo_siniestro(numero_expediente="EXP-B", fecha_hecho=hecho_en(ahora, days=-3)), format="json").status_code == 201


def test_s34_se_compara_un_instante_y_no_la_hora_del_reloj_de_pared(perito08, ahora):
    # el mismo instante expresado con otro desfase (Tokio, +09:00): 4 min después se acepta; 10 min después no
    cliente = cliente_de(perito08)

    def en_tokio(minutos):
        return (ahora + timedelta(minutes=minutos)).astimezone(ZoneInfo("Asia/Tokyo")).isoformat()

    assert cliente.post("/api/siniestros", cuerpo_siniestro(numero_expediente="EXP-TK", fecha_hecho=en_tokio(4)), format="json").status_code == 201
    assert cliente.post("/api/siniestros", cuerpo_siniestro(numero_expediente="EXP-TK2", fecha_hecho=en_tokio(10)), format="json").status_code == 400


def test_s34_editar_con_una_fecha_futura_se_rechaza_y_el_borrador_no_cambia(perito08, ahora):
    cliente = cliente_de(perito08)
    id_ = cliente.post("/api/siniestros", cuerpo_siniestro(fecha_hecho=hecho_en(ahora, days=-2)), format="json").json()["id"]
    original = Siniestro.objects.get(pk=id_)
    respuesta = cliente.patch(f"/api/siniestros/{id_}", {"fecha_hecho": hecho_en(ahora, days=2), "lugar": "Otro lugar"}, format="json")
    assert respuesta.status_code == 400
    assert respuesta.json() == MENSAJE_FUTURA
    siniestro = Siniestro.objects.get(pk=id_)
    assert siniestro.fecha_hecho == original.fecha_hecho and siniestro.lugar == original.lugar
    assert not Auditoria.objects.filter(accion="modificar_siniestro").exists()


def test_s34_editar_con_una_fecha_pasada_se_acepta(perito08, ahora):
    cliente = cliente_de(perito08)
    id_ = cliente.post("/api/siniestros", cuerpo_siniestro(fecha_hecho=hecho_en(ahora, days=-2)), format="json").json()["id"]
    assert cliente.patch(f"/api/siniestros/{id_}", {"fecha_hecho": hecho_en(ahora, days=-1)}, format="json").status_code == 200


def test_s34_confirmar_un_borrador_con_fecha_futura_se_rechaza_y_no_cambia_nada(perito08, ahora):
    cliente = cliente_de(perito08)
    id_ = cliente.post("/api/siniestros", cuerpo_siniestro(fecha_hecho=hecho_en(ahora, days=-1)), format="json").json()["id"]
    # un borrador con fecha futura no se puede armar por la API; se simula uno viejo o con el reloj corrido
    Siniestro.objects.filter(pk=id_).update(fecha_hecho=ahora + timedelta(days=1))
    antes = sin_cambios_en_la_base()
    respuesta = cliente.post(f"/api/siniestros/{id_}/confirmar")
    assert respuesta.status_code == 400
    assert respuesta.json() == MENSAJE_FUTURA
    assert sin_cambios_en_la_base() == antes
    assert Siniestro.objects.get(pk=id_).estado == "borrador"


def test_s34_confirmar_un_borrador_con_fecha_pasada_sigue_funcionando(perito08, ahora):
    cliente = cliente_de(perito08)
    id_ = cliente.post("/api/siniestros", cuerpo_siniestro(fecha_hecho=hecho_en(ahora, days=-1)), format="json").json()["id"]
    assert cliente.post(f"/api/siniestros/{id_}/confirmar").status_code == 200
