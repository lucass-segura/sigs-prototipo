"""S24 · Campos técnicos extra de `siniestro` para los datos del Anexo 1 del Entregable 4 que el modelo no tenía.

`numero_denuncia`, `hora_denuncia` (con `fecha_denuncia` como fecha, así que R08 no cambia), `asesor`,
`intervenciones` y `documentacion_adjunta`. Se exponen al crear, al modificar un borrador y en el detalle, y
EXP-2026-0147 se carga con los valores exactos del Anexo 1.
"""
import io
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest
from django.core.management import call_command

from nucleo.fabrica import crear_siniestro
from nucleo.models import Siniestro
from tests.conftest import cliente_de, cuerpo_siniestro

pytestmark = pytest.mark.django_db

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")

ANEXO = {
    "numero_denuncia": "DEN-2026-0147",
    "hora_denuncia": "10:20",
    "asesor": "Código PA-031",
    "intervenciones": "Bomberos y policía",
    "documentacion_adjunta": "DNI, cédula del vehículo, 6 fotografías y constancia de bomberos. Acta policial pendiente",
}


def detalle(usuario, id):
    return cliente_de(usuario).get(f"/api/siniestros/{id}").json()


def test_s24_al_crear_se_guardan_y_se_devuelven_los_datos_de_la_denuncia(perito08):
    creado = cliente_de(perito08).post("/api/siniestros", cuerpo_siniestro(**ANEXO), format="json")
    assert creado.status_code == 201
    cuerpo = detalle(perito08, creado.json()["id"])
    assert cuerpo["numero_denuncia"] == "DEN-2026-0147"
    assert cuerpo["hora_denuncia"] == "10:20:00"
    assert cuerpo["asesor"] == "Código PA-031"
    assert cuerpo["intervenciones"] == "Bomberos y policía"
    assert cuerpo["documentacion_adjunta"] == ANEXO["documentacion_adjunta"]
    siniestro = Siniestro.objects.get(pk=creado.json()["id"])
    assert siniestro.hora_denuncia == time(10, 20)


def test_s24_sin_los_datos_nuevos_el_caso_se_crea_igual_con_valores_vacios(perito08):
    creado = cliente_de(perito08).post("/api/siniestros", cuerpo_siniestro(), format="json")
    assert creado.status_code == 201
    cuerpo = detalle(perito08, creado.json()["id"])
    assert (cuerpo["numero_denuncia"], cuerpo["asesor"], cuerpo["intervenciones"], cuerpo["documentacion_adjunta"]) == ("", "", "", "")
    assert cuerpo["hora_denuncia"] is None


def test_s24_un_borrador_se_puede_modificar_y_la_hora_se_puede_borrar(perito08):
    cliente = cliente_de(perito08)
    id = cliente.post("/api/siniestros", cuerpo_siniestro(**ANEXO), format="json").json()["id"]
    respuesta = cliente.patch(f"/api/siniestros/{id}", {"asesor": "Código PA-032", "hora_denuncia": "", "intervenciones": ""}, format="json")
    assert respuesta.status_code == 200
    cuerpo = detalle(perito08, id)
    assert cuerpo["asesor"] == "Código PA-032" and cuerpo["hora_denuncia"] is None and cuerpo["intervenciones"] == ""
    assert cuerpo["numero_denuncia"] == "DEN-2026-0147"  # lo que no llega no se toca


def test_s24_una_hora_con_formato_invalido_se_rechaza(perito08):
    respuesta = cliente_de(perito08).post("/api/siniestros", cuerpo_siniestro(hora_denuncia="25:99"), format="json")
    assert respuesta.status_code == 400 and "hora_denuncia" in respuesta.json()


def test_s24_la_hora_de_la_denuncia_no_cambia_r08(perito08):
    """R08 sigue usando `fecha_denuncia` (fecha): la hora no mueve el plazo de 3 días."""
    cliente = cliente_de(perito08)
    cuerpo = cuerpo_siniestro(hora_denuncia="23:59", fecha_denuncia="2026-08-15", confirmar=True)
    id = cliente.post("/api/siniestros", cuerpo, format="json").json()["id"]
    r08 = next(s for s in cliente.get(f"/api/siniestros/{id}/evaluacion").json()["senales"] if s["codigo"] == "R08")
    assert r08["estado"] == "no_activada" and r08["dato"]["dias"] == 3
    assert detalle(perito08, id)["fecha_denuncia"] == "2026-08-15"


def test_s24_exp_2026_0147_de_la_demo_trae_los_valores_exactos_del_anexo_1():
    call_command("seed_demo", stdout=io.StringIO())
    caso = Siniestro.objects.get(numero_expediente="EXP-2026-0147")
    cuerpo = detalle(caso.perito, caso.id)
    for campo, valor in ANEXO.items():
        esperado = f"{valor}:00" if campo == "hora_denuncia" else valor
        assert cuerpo[campo] == esperado, campo
    assert cuerpo["fecha_denuncia"] == "2026-08-14"
    assert cuerpo["estado"] == "en_analisis"
    evaluacion = cliente_de(caso.perito).get(f"/api/siniestros/{caso.id}/evaluacion").json()
    assert (evaluacion["puntaje"], evaluacion["prioridad"]) == (55, "alta")


def test_s24_el_resumen_del_antecedente_no_muestra_los_datos_de_la_denuncia(perito08, perito15):
    caso = crear_siniestro(perito08, "EXP-CASO", fecha_hecho=datetime(2026, 8, 1, 12, tzinfo=ZONA), bienes=["AB123CD"])
    anterior = crear_siniestro(perito15, "S-ANT", fecha_hecho=datetime(2026, 3, 1, 12, tzinfo=ZONA), bienes=["AB123CD"])
    Siniestro.objects.filter(pk=anterior.pk).update(**{**ANEXO, "hora_denuncia": time(10, 20)})
    resumen = cliente_de(perito08).get(f"/api/siniestros/{caso.id}/antecedentes/{anterior.id}/resumen")
    assert resumen.status_code == 200
    texto = resumen.content.decode()
    assert not any(clave in resumen.json() for clave in ANEXO)
    assert "DEN-2026-0147" not in texto and "PA-031" not in texto and "Bomberos" not in texto


def test_s24_otro_perito_no_ve_los_datos_de_la_denuncia(perito08, perito11):
    id = cliente_de(perito08).post("/api/siniestros", cuerpo_siniestro(**ANEXO), format="json").json()["id"]
    assert cliente_de(perito11).get(f"/api/siniestros/{id}").status_code in (403, 404)
