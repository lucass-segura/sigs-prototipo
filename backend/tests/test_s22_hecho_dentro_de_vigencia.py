"""S22 · Un hecho anterior al inicio de vigencia de la póliza no es un siniestro: no se acepta esa fecha.

Se rechaza con 400 al crear (también con `confirmar: true`), al editar y al confirmar. Compara la fecha local del
hecho con el inicio de vigencia: el mismo día se acepta. Sin inicio de vigencia no se controla nada.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from nucleo.fabrica import crear_siniestro
from nucleo.models import Auditoria, Evaluacion, Persona, Siniestro
from tests.conftest import cliente_de, cuerpo_siniestro

pytestmark = pytest.mark.django_db

MENSAJE = {"fecha_hecho": ["La fecha del hecho no puede ser anterior al inicio de vigencia de la póliza."]}
ZONA = ZoneInfo("America/Argentina/Buenos_Aires")


def crear(cliente, hecho="2026-08-12T23:40:00", vigencia="2026-07-20", **cambios):
    cuerpo = cuerpo_siniestro(fecha_hecho=hecho, **cambios)
    if "poliza" not in cambios:
        cuerpo["poliza"] = dict(cuerpo["poliza"], inicio_vigencia=vigencia)
    return cliente.post("/api/siniestros", cuerpo, format="json")


# --- Crear ---------------------------------------------------------------------------------------
def test_s22_un_hecho_anterior_a_la_vigencia_se_rechaza_y_no_se_guarda_nada(perito08):
    respuesta = crear(cliente_de(perito08), hecho="2026-07-19T23:59:00")
    assert respuesta.status_code == 400
    assert respuesta.json() == MENSAJE
    assert Siniestro.objects.count() == 0 and Persona.objects.count() == 0
    assert not Auditoria.objects.filter(accion="crear_siniestro").exists()


def test_s22_el_mismo_dia_de_la_vigencia_se_acepta(perito08):
    assert crear(cliente_de(perito08), hecho="2026-07-20T00:30:00").status_code == 201


def test_s22_se_compara_la_fecha_local_y_no_la_de_utc(perito08):
    # 01:00 UTC del 20/07 son las 22:00 del 19/07 en Argentina: es anterior a la vigencia
    assert crear(cliente_de(perito08), hecho="2026-07-20T01:00:00Z").status_code == 400
    # 03:00 UTC del 20/07 son las 00:00 del 20/07 locales: es el primer día de la vigencia
    assert crear(cliente_de(perito08), hecho="2026-07-20T03:00:00Z").status_code == 201


def test_s22_con_confirmar_verdadero_tambien_se_rechaza_y_no_deja_basura(perito08):
    respuesta = crear(cliente_de(perito08), hecho="2026-07-01T10:00:00", confirmar=True)
    assert respuesta.status_code == 400 and respuesta.json() == MENSAJE
    assert Siniestro.objects.count() == 0 and Evaluacion.objects.count() == 0


def test_s22_sin_inicio_de_vigencia_no_se_controla_nada(perito08):
    poliza = {"numero": "AUT-1", "compania": "Aseguradora Ejemplo S. A.", "cobertura": "Todo riesgo", "inicio_vigencia": None, "primer_pago": None}
    respuesta = crear(cliente_de(perito08), hecho="2020-01-01T10:00:00", poliza=poliza, confirmar=True)
    assert respuesta.status_code == 201, respuesta.content
    r01 = next(s for s in cliente_de(perito08).get(f"/api/siniestros/{respuesta.json()['id']}/evaluacion").json()["senales"] if s["codigo"] == "R01")
    assert r01["estado"] == "no_evaluable"


def test_s22_sin_poliza_se_guarda_el_borrador(perito08):
    assert crear(cliente_de(perito08), hecho="2020-01-01T10:00:00", poliza=None).status_code == 201


# --- Editar --------------------------------------------------------------------------------------
def test_s22_editar_la_fecha_del_hecho_a_antes_de_la_vigencia_se_rechaza_sin_cambiar_nada(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    antes = Siniestro.objects.get(pk=id_)
    respuesta = cliente.patch(f"/api/siniestros/{id_}", {"fecha_hecho": "2026-07-19T10:00:00", "tipo": "Cambiado"}, format="json")
    assert respuesta.status_code == 400 and respuesta.json() == MENSAJE
    despues = Siniestro.objects.get(pk=id_)
    assert (despues.fecha_hecho, despues.tipo) == (antes.fecha_hecho, antes.tipo)


def test_s22_editar_la_vigencia_a_despues_del_hecho_se_rechaza_sin_cambiar_nada(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    poliza = dict(cuerpo_siniestro()["poliza"], inicio_vigencia="2026-08-13")
    respuesta = cliente.patch(f"/api/siniestros/{id_}", {"poliza": poliza}, format="json")
    assert respuesta.status_code == 400 and respuesta.json() == MENSAJE
    assert Siniestro.objects.get(pk=id_).poliza.inicio_vigencia == date(2026, 7, 20)


def test_s22_una_edicion_valida_sigue_funcionando(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    respuesta = cliente.patch(f"/api/siniestros/{id_}", {"fecha_hecho": "2026-07-20T08:00:00", "tipo": "Cambiado"}, format="json")
    assert respuesta.status_code == 200 and respuesta.json()["tipo"] == "Cambiado"


# --- Confirmar -------------------------------------------------------------------------------------
def test_s22_confirmar_un_borrador_con_hecho_anterior_a_la_vigencia_se_rechaza(perito08):
    borrador = crear_siniestro(
        perito08, "EXP-VIEJO", estado="borrador", fecha_hecho=datetime(2026, 7, 1, 10, tzinfo=ZONA),
        poliza={"numero": "AUT-1", "inicio_vigencia": date(2026, 7, 20), "primer_pago": date(2026, 7, 21)}, personas=[],
        bienes=["AB123CD"],
    )
    respuesta = cliente_de(perito08).post(f"/api/siniestros/{borrador.id}/confirmar")
    assert respuesta.status_code == 400 and respuesta.json() == MENSAJE
    borrador.refresh_from_db()
    assert borrador.estado == "borrador" and borrador.confirmado_en is None
    assert Evaluacion.objects.count() == 0


def test_s22_confirmar_un_borrador_valido_sigue_funcionando(perito08):
    cliente = cliente_de(perito08)
    id_ = crear(cliente).json()["id"]
    assert cliente.post(f"/api/siniestros/{id_}/confirmar").status_code == 200
