"""T10 · HU-13, HU-14 y pruebas funcionales F1–F4: cierre con valoración, archivo y anulación."""
import pytest

from nucleo.fabrica import crear_siniestro
from nucleo.models import Auditoria, Cierre, Siniestro
from tests.conftest import cliente_de, cuerpo_siniestro

pytestmark = pytest.mark.django_db

CIERRE = {
    "resultado_reclamo": "aprobado",
    "irregularidad": False,
    "conclusion": "Hecho verificado con observaciones.",
    "valoracion": 8,
    "justificacion": "Póliza reciente, pero la inspección coincide con el relato.",
}


@pytest.fixture
def caso(perito08):
    cliente = cliente_de(perito08)
    respuesta = cliente.post("/api/siniestros", cuerpo_siniestro(confirmar=True), format="json")
    assert respuesta.status_code == 201
    return cliente, respuesta.json()["id"]


def cerrar(cliente, id_, **cambios):
    return cliente.post(f"/api/siniestros/{id_}/cierre", dict(CIERRE, **cambios), format="json")


# --- HU-13 -------------------------------------------------------------------------
def test_hu13_cerrar_guarda_el_cierre_y_pasa_el_caso_a_cerrado(caso):
    cliente, id_ = caso
    respuesta = cerrar(cliente, id_)
    assert respuesta.status_code == 201, respuesta.content
    cierre = respuesta.json()
    assert cierre["valoracion"] == 8 and cierre["valoracion_texto"] == "Verificado con observaciones menores"
    assert cierre["perito"]["nombre"] == "PE-08"
    assert cliente.get(f"/api/siniestros/{id_}").json()["estado"] == "cerrado"
    assert cliente.get(f"/api/siniestros/{id_}").json()["cierre_vigente"]["id"] == cierre["id"]


def test_hu13_el_resultado_del_reclamo_y_la_irregularidad_son_datos_separados(caso):
    cliente, id_ = caso
    cierre = cerrar(cliente, id_, resultado_reclamo="rechazado", irregularidad=True).json()
    assert cierre["resultado_reclamo"] == "rechazado" and cierre["irregularidad"] is True
    otro = Cierre.objects.get(pk=cierre["id"])
    assert (otro.resultado_reclamo, otro.irregularidad) == ("rechazado", True)


@pytest.mark.parametrize("resultado", ["aprobado", "rechazado", "desistido", "otra_finalizacion"])
def test_hu13_acepta_los_cuatro_resultados_del_reclamo(perito08, resultado):
    cliente = cliente_de(perito08)
    id_ = cliente.post("/api/siniestros", cuerpo_siniestro(confirmar=True), format="json").json()["id"]
    assert cerrar(cliente, id_, resultado_reclamo=resultado).status_code == 201


def test_hu13_un_resultado_invalido_se_rechaza(caso):
    cliente, id_ = caso
    assert cerrar(cliente, id_, resultado_reclamo="inventado").status_code == 400
    assert Cierre.objects.count() == 0


def test_hu13_cambiar_la_valoracion_crea_un_registro_nuevo_con_motivo_y_conserva_el_anterior(caso):
    cliente, id_ = caso
    primero = cerrar(cliente, id_).json()
    sin_motivo = cerrar(cliente, id_, valoracion=4)
    assert sin_motivo.status_code == 400 and "motivo_cambio" in sin_motivo.json()
    segundo = cerrar(cliente, id_, valoracion=4, motivo_cambio="Apareció una inconsistencia en el acta.")
    assert segundo.status_code == 201
    historial = cliente.get(f"/api/siniestros/{id_}/cierre").json()
    assert historial["vigente"]["id"] == segundo.json()["id"] and historial["vigente"]["valoracion"] == 4
    assert historial["vigente"]["motivo_cambio"].startswith("Apareció")
    assert [c["valoracion"] for c in historial["historial"]] == [8, 4]  # cronológico: el vigente es el último
    assert {c["id"] for c in historial["historial"]} == {primero["id"], segundo.json()["id"]}
    assert Cierre.objects.get(pk=primero["id"]).valoracion == 8  # el anterior no se tocó
    assert Auditoria.objects.filter(accion="cambio_valoracion", resultado="permitido").count() == 1
    assert Auditoria.objects.filter(accion="cierre", resultado="permitido").count() == 1


def test_hu13_el_cierre_sin_cerrar_el_caso_no_existe(caso):
    cliente, id_ = caso
    assert cliente.get(f"/api/siniestros/{id_}/cierre").json() == {"vigente": None, "historial": []}


def test_hu13_no_se_cierra_un_borrador(perito08):
    cliente = cliente_de(perito08)
    id_ = cliente.post("/api/siniestros", cuerpo_siniestro(), format="json").json()["id"]
    assert cerrar(cliente, id_).status_code == 400
    assert Cierre.objects.count() == 0


# --- F3 / F4 ------------------------------------------------------------------------
@pytest.mark.parametrize("valor", [0, 11, -3, 100])
def test_f3_la_valoracion_rechaza_valores_fuera_de_1_a_10(caso, valor):
    cliente, id_ = caso
    respuesta = cerrar(cliente, id_, valoracion=valor)
    assert respuesta.status_code == 400
    assert respuesta.json() == {"valoracion": ["La valoración tiene que estar entre 1 y 10."]}
    assert Cierre.objects.count() == 0 and Siniestro.objects.get(pk=id_).estado == "en_analisis"


@pytest.mark.parametrize("valor", [1, 10])
def test_f3_los_bordes_1_y_10_se_aceptan(perito08, valor):
    cliente = cliente_de(perito08)
    id_ = cliente.post("/api/siniestros", cuerpo_siniestro(confirmar=True), format="json").json()["id"]
    assert cerrar(cliente, id_, valoracion=valor).status_code == 201


@pytest.mark.parametrize("justificacion", ["", "   ", None])
def test_f4_el_cierre_no_se_guarda_sin_justificacion(caso, justificacion):
    cliente, id_ = caso
    cuerpo = dict(CIERRE, justificacion=justificacion)
    if justificacion is None:
        del cuerpo["justificacion"]
    respuesta = cliente.post(f"/api/siniestros/{id_}/cierre", cuerpo, format="json")
    assert respuesta.status_code == 400
    assert respuesta.json() == {"justificacion": ["La justificación es obligatoria."]}
    assert Cierre.objects.count() == 0 and Siniestro.objects.get(pk=id_).estado == "en_analisis"


def test_f4_la_justificacion_tiene_un_maximo_de_500_caracteres(caso):
    cliente, id_ = caso
    assert cerrar(cliente, id_, justificacion="x" * 501).status_code == 400
    assert cerrar(cliente, id_, justificacion="x" * 500).status_code == 201


# --- HU-14 y F1/F2 -------------------------------------------------------------------
def test_hu14_archivar_conserva_todo_y_el_caso_sigue_contando_como_antecedente(perito08, perito15):
    c08 = cliente_de(perito08)
    id_ = c08.post("/api/siniestros", cuerpo_siniestro(confirmar=True), format="json").json()["id"]
    cerrar(c08, id_)
    assert c08.post(f"/api/siniestros/{id_}/archivar").status_code == 200
    assert c08.get(f"/api/siniestros/{id_}").json()["estado"] == "archivado"
    assert c08.get(f"/api/siniestros/{id_}").json()["cierre_vigente"]["valoracion"] == 8
    # otro perito (otro espacio) lo sigue viendo como antecedente
    c15 = cliente_de(perito15)
    mio = crear_siniestro(perito15, "S-MIO", personas=[], bienes=["AB123CD"])
    coincidencias = c15.get(f"/api/siniestros/{mio.pk}/coincidencias").json()
    assert [c["antecedente_id"] for c in coincidencias["resultados"]] == [id_]
    assert coincidencias["resultados"][0]["estado"] == "archivado"


def test_hu14_solo_un_cerrado_se_archiva(caso):
    cliente, id_ = caso
    assert cliente.post(f"/api/siniestros/{id_}/archivar").status_code == 400


def test_hu14_anular_requiere_motivo_y_conserva_el_registro(caso):
    cliente, id_ = caso
    assert cliente.post(f"/api/siniestros/{id_}/anular", {}, format="json").status_code == 400
    assert cliente.post(f"/api/siniestros/{id_}/anular", {"motivo": "  "}, format="json").status_code == 400
    respuesta = cliente.post(f"/api/siniestros/{id_}/anular", {"motivo": "Carga errónea: era otro asegurado."}, format="json")
    assert respuesta.status_code == 200
    cuerpo = cliente.get(f"/api/siniestros/{id_}").json()
    assert cuerpo["estado"] == "anulado" and cuerpo["motivo_anulacion"] == "Carga errónea: era otro asegurado."
    assert cuerpo["relato"]  # no borra nada
    assert cliente.post(f"/api/siniestros/{id_}/anular", {"motivo": "otra vez"}, format="json").status_code == 400


def test_hu14_un_expediente_anulado_deja_de_contar_como_antecedente(perito08, perito15):
    c08 = cliente_de(perito08)
    id_ = c08.post("/api/siniestros", cuerpo_siniestro(confirmar=True), format="json").json()["id"]
    mio = crear_siniestro(perito15, "S-MIO", personas=[], bienes=["AB123CD"])
    c15 = cliente_de(perito15)
    assert c15.get(f"/api/siniestros/{mio.pk}/coincidencias").json()["total"] == 1
    c08.post(f"/api/siniestros/{id_}/anular", {"motivo": "Carga errónea"}, format="json")
    despues = c15.get(f"/api/siniestros/{mio.pk}/coincidencias").json()
    assert despues["total"] == 0 and despues["resultados"] == []
    assert despues["mensaje_vacio"] == "No hay antecedentes accesibles en la red"
    # ... ni se puede pedir su resumen
    assert c15.get(f"/api/siniestros/{mio.pk}/antecedentes/{id_}/resumen").status_code == 404


def test_f1_archivar_un_expediente_conserva_su_auditoria(perito08, admin_norte):
    c08 = cliente_de(perito08)
    id_ = c08.post("/api/siniestros", cuerpo_siniestro(confirmar=True), format="json").json()["id"]
    c08.get(f"/api/siniestros/{id_}")
    c08.get(f"/api/siniestros/{id_}/coincidencias")
    cerrar(c08, id_)
    antes = cliente_de(admin_norte).get("/api/auditoria").json()
    c08.post(f"/api/siniestros/{id_}/archivar")
    despues = cliente_de(admin_norte).get("/api/auditoria").json()
    ids_antes = {r["id"] for r in antes["resultados"]}
    assert ids_antes <= {r["id"] for r in despues["resultados"]}
    acciones = {r["accion"] for r in despues["resultados"]}
    assert {"crear_siniestro", "confirmar_siniestro", "ver_expediente", "ver_coincidencias", "cierre", "archivar"} <= acciones
    de_este_caso = [r for r in despues["resultados"] if r["siniestro_origen"] and r["siniestro_origen"]["id"] == id_]
    assert len(de_este_caso) >= 6


def test_f2_una_carga_erronea_no_aparece_como_antecedente(perito08, perito11):
    c08 = cliente_de(perito08)
    erroneo = crear_siniestro(perito08, "EXP-ERRONEO", personas=[], bienes=["AC904KL"])
    valido = crear_siniestro(perito11, "EXP-VALIDO", personas=[], bienes=["AC904KL"])
    mio = crear_siniestro(perito08, "EXP-MIO", personas=[], bienes=["AC904KL"])
    c08.post(f"/api/siniestros/{erroneo.pk}/anular", {"motivo": "Carga errónea"}, format="json")
    resultados = c08.get(f"/api/siniestros/{mio.pk}/coincidencias").json()["resultados"]
    assert [r["numero_expediente"] for r in resultados] == ["EXP-VALIDO"]
    assert valido.pk == resultados[0]["antecedente_id"]
