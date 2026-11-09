"""S23 · Solo los bienes de tipo `vehiculo` y `motocicleta` son identificables y cruzan entre casos.

Los demás tipos (teléfono, computadora, otro) se registran en el caso con su identificador y su descripción, pero
nunca cruzan: ni en la lista de coincidencias, ni en el promedio, ni en el resumen, ni en R06 y R07, ni en el
recálculo automático.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from nucleo.fabrica import crear_siniestro
from nucleo.models import Bien, BienAfectado, Evaluacion
from nucleo.motor import guardar_evaluacion
from tests.conftest import cliente_de, cuerpo_siniestro

pytestmark = pytest.mark.django_db

ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
POLIZA = {"numero": "AUT-1", "compania": "Aseguradora Ejemplo S. A.", "cobertura": "Todo riesgo",
          "inicio_vigencia": date(2025, 1, 1), "primer_pago": date(2025, 1, 5)}
IRREGULAR = {"resultado_reclamo": "rechazado", "irregularidad": True, "valoracion": 2, "justificacion": "Adulteración confirmada.",
             "observacion_respaldo": "Constatado en la inspección."}
APROBADO = {"resultado_reclamo": "aprobado", "valoracion": 8, "justificacion": "Sin observaciones."}
IMEI = "357000000004471"


def local(anio, mes, dia, hora=12):
    return datetime(anio, mes, dia, hora, tzinfo=ZONA)


def bien(tipo, identificador, **extra):
    return {"tipo": tipo, "identificador": identificador, **extra}


def coincidencias(usuario, siniestro):
    return cliente_de(usuario).get(f"/api/siniestros/{siniestro.id}/coincidencias").json()


def evaluacion(usuario, siniestro):
    cliente = cliente_de(usuario)
    assert cliente.post(f"/api/siniestros/{siniestro.id}/recalcular").status_code == 200
    return cliente.get(f"/api/siniestros/{siniestro.id}/evaluacion").json()


def senales(cuerpo):
    return {s["codigo"]: s for s in cuerpo["senales"]}


# --- Coincidencias ---------------------------------------------------------------------------
def test_s23_dos_casos_con_el_mismo_imei_de_telefono_no_coinciden(perito08, perito15):
    caso = crear_siniestro(perito08, "EXP-CEL", fecha_hecho=local(2026, 8, 1), poliza=POLIZA, bienes=[bien("telefono", IMEI)])
    crear_siniestro(perito15, "S-CEL", fecha_hecho=local(2026, 3, 1), poliza=POLIZA, bienes=[bien("telefono", IMEI)], estado="cerrado",
                    cierre=APROBADO)
    cuerpo = coincidencias(perito08, caso)
    assert cuerpo["resultados"] == [] and cuerpo["total"] == 0
    assert cuerpo["promedio_valoracion"] == {"promedio": None, "cantidad": 0}


@pytest.mark.parametrize("tipo, identificador", [("computadora", "SN-8F09X2"), ("otro", "Local 12"), ("telefono", IMEI)])
def test_s23_los_bienes_que_no_son_vehiculos_nunca_cruzan(perito08, perito15, tipo, identificador):
    caso = crear_siniestro(perito08, "EXP-X", fecha_hecho=local(2026, 8, 1), poliza=POLIZA, bienes=[bien(tipo, identificador)])
    crear_siniestro(perito15, "S-X", fecha_hecho=local(2026, 3, 1), poliza=POLIZA, bienes=[bien(tipo, identificador)])
    assert coincidencias(perito08, caso)["resultados"] == []


def test_s23_dos_casos_con_la_misma_patente_de_motocicleta_coinciden(perito08, perito15):
    caso = crear_siniestro(perito08, "EXP-MOTO", fecha_hecho=local(2026, 8, 1), poliza=POLIZA, bienes=[bien("motocicleta", "123-ABC")])
    crear_siniestro(perito15, "S-MOTO", fecha_hecho=local(2026, 3, 1), poliza=POLIZA, bienes=[bien("motocicleta", "123 abc")])
    cuerpo = coincidencias(perito08, caso)
    assert [r["numero_expediente"] for r in cuerpo["resultados"]] == ["S-MOTO"]
    assert cuerpo["resultados"][0]["vinculos"][0]["etiqueta"] == "123ABC"


def test_s23_dos_casos_con_la_misma_patente_de_vehiculo_coinciden(perito08, perito15):
    caso = crear_siniestro(perito08, "EXP-VEH", fecha_hecho=local(2026, 8, 1), poliza=POLIZA, bienes=[bien("vehiculo", "AB-123-CD")])
    crear_siniestro(perito15, "S-VEH", fecha_hecho=local(2026, 3, 1), poliza=POLIZA, bienes=[bien("vehiculo", "AB123CD")])
    assert [r["numero_expediente"] for r in coincidencias(perito08, caso)["resultados"]] == ["S-VEH"]


def test_s23_el_telefono_se_registra_en_el_caso_con_su_identificador_y_su_descripcion(perito08):
    cuerpo = cuerpo_siniestro(bienes=[bien("telefono", IMEI, descripcion="Teléfono ficticio", detalle_dano="Robo")])
    cliente = cliente_de(perito08)
    creado = cliente.post("/api/siniestros", cuerpo, format="json")
    assert creado.status_code == 201
    registrado = cliente.get(f"/api/siniestros/{creado.json()['id']}").json()["bienes"]
    assert [(b["tipo"], b["identificador_norm"], b["descripcion"], b["detalle_dano"]) for b in registrado] == [
        ("telefono", IMEI, "Teléfono ficticio", "Robo")
    ]
    assert Bien.objects.filter(identificador_norm=IMEI, tipo="telefono").exists()


def test_s23_un_caso_con_vehiculo_y_telefono_cruza_solo_por_el_vehiculo(perito08, perito15):
    caso = crear_siniestro(perito08, "EXP-MIXTO", fecha_hecho=local(2026, 8, 1), poliza=POLIZA,
                           bienes=[bien("vehiculo", "AB123CD"), bien("telefono", IMEI)])
    crear_siniestro(perito15, "S-SOLO-TEL", fecha_hecho=local(2026, 3, 1), poliza=POLIZA, bienes=[bien("telefono", IMEI)])
    veh = crear_siniestro(perito15, "S-VEH", fecha_hecho=local(2026, 4, 1), poliza=POLIZA,
                          bienes=[bien("vehiculo", "AB123CD"), bien("telefono", IMEI)])
    cuerpo = coincidencias(perito08, caso)
    assert [r["numero_expediente"] for r in cuerpo["resultados"]] == ["S-VEH"]
    assert [v["etiqueta"] for v in cuerpo["resultados"][0]["vinculos"]] == ["AB123CD"]
    # el resumen del que solo comparte el IMEI se rechaza
    assert cliente_de(perito08).get(f"/api/siniestros/{caso.id}/antecedentes/{veh.id}/resumen").status_code == 200
    solo_tel = crear_siniestro(perito15, "S-SOLO-TEL-2", fecha_hecho=local(2026, 2, 1), poliza=POLIZA, bienes=[bien("telefono", IMEI)])
    assert cliente_de(perito08).get(f"/api/siniestros/{caso.id}/antecedentes/{solo_tel.id}/resumen").status_code == 404


# --- Reglas ----------------------------------------------------------------------------------
def test_s23_r06_no_se_activa_con_un_telefono_repetido(perito08, perito15):
    caso = crear_siniestro(perito08, "EXP-CEL", fecha_hecho=local(2026, 8, 1), poliza=POLIZA, bienes=[bien("telefono", IMEI)])
    crear_siniestro(perito15, "S-CEL", fecha_hecho=local(2026, 3, 1), poliza=POLIZA, bienes=[bien("telefono", IMEI)])
    cuerpo = evaluacion(perito08, caso)
    assert senales(cuerpo)["R06"]["estado"] == "no_activada"
    assert cuerpo["puntaje"] == 0 and cuerpo["entradas"]["antecedentes"] == []


def test_s23_r06_se_activa_con_una_motocicleta_repetida(perito08, perito15):
    caso = crear_siniestro(perito08, "EXP-MOTO", fecha_hecho=local(2026, 8, 1), poliza=POLIZA, bienes=[bien("motocicleta", "123ABC")])
    crear_siniestro(perito15, "S-MOTO", fecha_hecho=local(2026, 3, 1), poliza=POLIZA, bienes=[bien("motocicleta", "123ABC")])
    cuerpo = evaluacion(perito08, caso)
    assert senales(cuerpo)["R06"]["estado"] == "activada"
    assert "motocicleta 123ABC" in senales(cuerpo)["R06"]["texto"]


def test_s23_r07_no_se_activa_por_un_telefono_de_un_antecedente_con_irregularidad(perito08, perito15):
    caso = crear_siniestro(perito08, "EXP-CEL", fecha_hecho=local(2026, 8, 1), poliza=POLIZA, bienes=[bien("telefono", IMEI)])
    crear_siniestro(perito15, "S-CEL", fecha_hecho=local(2024, 3, 1), poliza=POLIZA, bienes=[bien("telefono", IMEI)], estado="cerrado",
                    cierre=IRREGULAR)
    assert senales(evaluacion(perito08, caso))["R07"]["estado"] == "no_activada"


def test_s23_r07_se_activa_por_una_motocicleta_de_un_antecedente_con_irregularidad(perito08, perito15):
    caso = crear_siniestro(perito08, "EXP-MOTO", fecha_hecho=local(2026, 8, 1), poliza=POLIZA, bienes=[bien("motocicleta", "123ABC")])
    crear_siniestro(perito15, "S-MOTO", fecha_hecho=local(2024, 3, 1), poliza=POLIZA, bienes=[bien("motocicleta", "123ABC")],
                    estado="cerrado", cierre=IRREGULAR)
    assert senales(evaluacion(perito08, caso))["R07"]["estado"] == "activada"


# --- Recálculo automático --------------------------------------------------------------------
def test_s23_anular_un_caso_con_el_mismo_telefono_no_recalcula_al_posterior(perito08, perito15):
    anterior = crear_siniestro(perito15, "S-ANTERIOR", fecha_hecho=local(2026, 3, 1), poliza=POLIZA, bienes=[bien("telefono", IMEI)])
    posterior = crear_siniestro(perito08, "EXP-POSTERIOR", fecha_hecho=local(2026, 8, 1), poliza=POLIZA, bienes=[bien("telefono", IMEI)])
    guardar_evaluacion(posterior, "confirmacion")
    antes = Evaluacion.objects.filter(siniestro=posterior).count()
    assert cliente_de(perito15).post(f"/api/siniestros/{anterior.id}/anular", {"motivo": "Carga errónea."}, format="json").status_code == 200
    assert Evaluacion.objects.filter(siniestro=posterior).count() == antes


def test_s23_anular_un_caso_con_la_misma_motocicleta_recalcula_al_posterior(perito08, perito15):
    anterior = crear_siniestro(perito15, "S-ANTERIOR", fecha_hecho=local(2026, 3, 1), poliza=POLIZA, bienes=[bien("motocicleta", "123ABC")])
    posterior = crear_siniestro(perito08, "EXP-POSTERIOR", fecha_hecho=local(2026, 8, 1), poliza=POLIZA, bienes=[bien("motocicleta", "123ABC")])
    guardar_evaluacion(posterior, "confirmacion")
    antes = Evaluacion.objects.filter(siniestro=posterior).count()
    assert cliente_de(perito15).post(f"/api/siniestros/{anterior.id}/anular", {"motivo": "Carga errónea."}, format="json").status_code == 200
    assert Evaluacion.objects.filter(siniestro=posterior).count() == antes + 1


def test_s23_el_telefono_sigue_en_bien_afectado_aunque_no_cruce(perito08):
    caso = crear_siniestro(perito08, "EXP-CEL", fecha_hecho=local(2026, 8, 1), poliza=POLIZA, bienes=[bien("telefono", IMEI)])
    assert BienAfectado.objects.filter(siniestro=caso, bien__identificador_norm=IMEI).count() == 1
