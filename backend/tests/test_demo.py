"""T14 · seed_demo: la narrativa del TFG (EXP-2026-0147 = 55, alta) y los datos de demostración."""
import io

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from nucleo.constantes import CLAVE_DEMO
from nucleo.models import Siniestro, Usuario
from tests.conftest import cliente_de

pytestmark = pytest.mark.django_db


@pytest.fixture
def demo():
    call_command("seed_demo", stdout=io.StringIO())


def siniestro(numero):
    return Siniestro.objects.get(numero_expediente=numero)


def usuario(email):
    return Usuario.objects.get(email=email)


def evaluacion(numero, email="perito08@sigs.test"):
    return cliente_de(usuario(email)).get(f"/api/siniestros/{siniestro(numero).id}/evaluacion").json()


def activadas(ev):
    return {s["codigo"]: s["puntos"] for s in ev["senales"] if s["estado"] == "activada"}


def test_exp_2026_0147_da_55_alta_con_r01_25_r02_20_y_r06_25(demo):
    ev = evaluacion("EXP-2026-0147")
    assert activadas(ev) == {"R01": 25, "R02": 20, "R06": 25}
    assert ev["puntaje"] == 55 and ev["prioridad"] == "alta" and ev["version"] == "RS-1.0"
    assert ev["grupos"]["Cobertura"] == {"bruto": 45, "tope": 30, "puntos": 30}
    assert ev["grupos"]["Bien"] == {"bruto": 25, "tope": 25, "puntos": 25}
    textos = {s["codigo"]: s["texto"] for s in ev["senales"]}
    assert textos["R01"] == "El hecho ocurrió 23 días después del inicio de vigencia. Umbral 30 días."
    assert textos["R02"] == "El primer pago se registró 8 días antes del hecho. Umbral 15 días."
    assert textos["R06"] == "El vehículo AB123CD figura en el antecedente S-2025-0381 de hace 13 meses."
    assert textos["R03"] == "P-17 no tiene otros siniestros válidos en los últimos 12 meses."
    assert textos["R08"] == "La denuncia se hizo 2 días después del hecho. Plazo 3 días."


def test_exp_2026_0147_tiene_su_antecedente_del_otro_espacio_con_promedio_7(demo):
    cliente = cliente_de(usuario("perito08@sigs.test"))
    cuerpo = cliente.get(f"/api/siniestros/{siniestro('EXP-2026-0147').id}/coincidencias").json()
    assert [r["numero_expediente"] for r in cuerpo["resultados"]] == ["S-2025-0381"]
    assert cuerpo["promedio_valoracion"] == {"promedio": 7.0, "cantidad": 1}
    resumen = cliente.get(f"/api/siniestros/{siniestro('EXP-2026-0147').id}/antecedentes/{siniestro('S-2025-0381').id}/resumen").json()
    assert resumen["resultado_reclamo"] == "aprobado" and resumen["irregularidad"] is False and resumen["valoracion"] == 7
    assert resumen["justificacion"] == "Faltó la denuncia policial original. El resto de la documentación coincide."
    assert resumen["perito_responsable"] == {"nombre": "PE-15"} and resumen["contacto_perito"] == {"email": "pe15@correo.test"}
    assert resumen["vinculos"] == [{"tipo": "bien", "etiqueta": "AB123CD", "rol_en_antecedente": "Bien afectado"}]


def test_el_caso_anulado_exp_2026_0120_nunca_aparece_como_antecedente(demo):
    anulado = siniestro("EXP-2026-0120")
    assert anulado.estado == "anulado" and anulado.motivo_anulacion
    for caso in Siniestro.objects.exclude(estado__in=["borrador", "anulado"]):
        cliente = cliente_de(caso.perito)
        cuerpo = cliente.get(f"/api/siniestros/{caso.id}/coincidencias").json()
        assert "EXP-2026-0120" not in [r["numero_expediente"] for r in cuerpo["resultados"]], caso.numero_expediente
    origen = siniestro("EXP-2026-0139")
    assert cliente_de(origen.perito).get(f"/api/siniestros/{origen.id}/antecedentes/{anulado.id}/resumen").status_code == 404


def test_el_caso_con_irregularidad_confirmada_activa_r07(demo):
    ev = evaluacion("EXP-2026-0139")
    assert activadas(ev) == {"R07": 30} and ev["prioridad"] == "media"
    r07 = next(s for s in ev["senales"] if s["codigo"] == "R07")
    assert [a["numero_expediente"] for a in r07["antecedentes"]] == ["S-2024-0207"]
    cierre = cliente_de(usuario("perito15@sigs.test")).get(f"/api/siniestros/{siniestro('S-2024-0207').id}/cierre").json()["vigente"]
    assert cierre["resultado_reclamo"] == "rechazado" and cierre["irregularidad"] is True


def test_el_robo_de_rueda_repite_el_dominio_en_los_dos_espacios(demo):
    cliente = cliente_de(usuario("perito08@sigs.test"))
    cuerpo = cliente.get(f"/api/siniestros/{siniestro('EXP-2026-0160').id}/coincidencias").json()
    assert {r["numero_expediente"] for r in cuerpo["resultados"]} == {"S-2025-0410", "S-2026-0030", "EXP-2026-0098"}
    assert cuerpo["promedio_valoracion"]["cantidad"] >= 1
    assert "R06" in activadas(evaluacion("EXP-2026-0160"))
    assert {siniestro(n).espacio.nombre for n in ("S-2025-0410", "S-2026-0030", "EXP-2026-0098")} == {"Perito Independiente Sur", "Estudio Pericial Norte"}


@pytest.mark.parametrize("numero", ["EXP-2026-0151", "EXP-2026-0122"])
def test_los_casos_sin_coincidencias_informan_que_no_hay_antecedentes_accesibles(demo, numero):
    caso = siniestro(numero)
    cuerpo = cliente_de(caso.perito).get(f"/api/siniestros/{caso.id}/coincidencias").json()
    assert cuerpo["total"] == 0 and cuerpo["mensaje_vacio"] == "No hay antecedentes accesibles en la red"


def test_hay_un_borrador_y_un_perito_con_contacto_visible_y_otro_sin_verlo(demo):
    assert siniestro("EXP-2026-0158").estado == "borrador"
    assert usuario("perito08@sigs.test").contacto_visible and usuario("perito08@sigs.test").contacto_email == "pe08@correo.test"
    assert not usuario("perito11@sigs.test").contacto_visible
    assert usuario("perito15@sigs.test").contacto_visible


@pytest.mark.parametrize("email, rol", [
    ("superadmin@sigs.test", "superadministrador"), ("admin.norte@sigs.test", "administrador"),
    ("admin.sur@sigs.test", "administrador"), ("perito08@sigs.test", "perito"),
    ("perito11@sigs.test", "perito"), ("perito15@sigs.test", "perito"),
])
def test_todos_los_usuarios_de_demo_ingresan_con_la_contrasena_documentada(demo, email, rol):
    respuesta = APIClient().post("/api/auth/ingresar", {"email": email, "password": CLAVE_DEMO}, format="json")
    assert respuesta.status_code == 200 and respuesta.json()["usuario"]["rol"] == rol


def test_el_panel_de_pe_08_trae_primero_el_de_prioridad_alta(demo):
    cuerpo = cliente_de(usuario("perito08@sigs.test")).get("/api/siniestros").json()
    primero = cuerpo["resultados"][0]
    assert (primero["numero_expediente"], primero["prioridad"], primero["puntaje"], primero["bien_principal"]) == ("EXP-2026-0147", "alta", 55, "AB123CD")
    assert primero["tareas_pendientes"] == 3  # 2 pendientes + 1 en curso
    assert "EXP-2026-0098" not in [i["numero_expediente"] for i in cuerpo["resultados"]]  # es de PE-11


def test_exp_2026_0147_trae_el_seguimiento_y_un_documento_descargable(demo):
    caso = siniestro("EXP-2026-0147")
    cliente = cliente_de(caso.perito)
    tareas = cliente.get(f"/api/siniestros/{caso.id}/tareas").json()
    assert {t["estado"] for t in tareas} == {"pendiente", "en_curso", "hecha"} and len(tareas) == 5
    assert len(cliente.get(f"/api/siniestros/{caso.id}/notas").json()) == 3
    documentos = cliente.get(f"/api/siniestros/{caso.id}/documentos").json()
    assert len(documentos) == 1
    descarga = cliente.get(f"/api/documentos/{documentos[0]['id']}/descargar")
    assert descarga.status_code == 200 and b"ficticio" in b"".join(descarga.streaming_content).lower()


def test_seed_demo_si_vacia_no_duplica_y_sin_el_indicador_avisa(demo):
    cantidad = Siniestro.objects.count()
    salida = io.StringIO()
    call_command("seed_demo", "--si-vacia", stdout=salida)
    assert Siniestro.objects.count() == cantidad and "ya está cargada" in salida.getvalue()
    with pytest.raises(Exception):
        call_command("seed_demo", stdout=io.StringIO())
    assert Siniestro.objects.count() == cantidad


def test_la_demo_y_los_escenarios_conviven_y_evaluar_escenarios_da_100_por_ciento(demo):
    call_command("seed_escenarios", "--si-vacia", stdout=io.StringIO())
    salida = io.StringIO()
    call_command("evaluar_escenarios", stdout=salida)  # sale con código 0: no lanza SystemExit
    assert "Precisión: 100 %" in salida.getvalue() and "Sensibilidad: 100 %" in salida.getvalue()
    # la demo no se contaminó con los escenarios y sigue dando 55
    assert evaluacion("EXP-2026-0147")["puntaje"] == 55


def test_la_demo_cumple_la_politica_de_contrasena():
    from django.contrib.auth.password_validation import validate_password

    validate_password(CLAVE_DEMO)
