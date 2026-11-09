"""S29 · Croquis: PNG + escena JSON reeditable, guardados como documento de tipo «Croquis»."""
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from nucleo.fabrica import crear_siniestro
from nucleo.models import Auditoria, Documento
from tests.conftest import cliente_de

pytestmark = pytest.mark.django_db

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 20


def escena(**cambios):
    base = {
        "version": 1,
        "ancho": 1200,
        "alto": 800,
        "cuadricula": True,
        "leyenda": True,
        "norte": True,
        "elementos": [
            {"id": "e1", "tipo": "calle", "x": 600, "y": 400, "rotacion": 0, "escala": 1},
            {"id": "e2", "tipo": "vehiculo", "x": 500.5, "y": 420, "rotacion": 90, "escala": 1, "etiqueta": "A", "color": "#2f6f62"},
            {"id": "e3", "tipo": "texto", "x": 100, "y": 100, "texto": "Esquina de calle 1 y 2"},
            {"id": "e4", "tipo": "lapiz", "x": 0, "y": 0, "color": "#9b2226", "puntos": [[10, 10], [20, 25.5], [30, 40]]},
        ],
    }
    base.update(cambios)
    return base


@pytest.fixture
def caso(perito08):
    return crear_siniestro(perito08, "EXP-C-1")


def guardar(cliente, caso, contenido_escena=None, imagen=PNG, **extra):
    datos = {"imagen": SimpleUploadedFile("croquis.png", imagen, content_type="image/png")}
    if contenido_escena is not None:
        datos["escena"] = contenido_escena if isinstance(contenido_escena, str) else json.dumps(contenido_escena)
    datos.update(extra)
    return cliente.post(f"/api/siniestros/{caso.pk}/croquis", datos, format="multipart")


def test_s29_guardar_crea_un_documento_de_tipo_croquis_con_el_png_y_la_escena(perito08, caso):
    cliente = cliente_de(perito08)
    respuesta = guardar(cliente, caso, escena())
    assert respuesta.status_code == 201, respuesta.content
    cuerpo = respuesta.json()
    assert cuerpo["tipo"] == "Croquis" and cuerpo["tiene_escena"] is True
    assert cuerpo["nombre_original"].startswith("croquis-") and cuerpo["nombre_original"].endswith(".png")
    documento = Documento.objects.get(pk=cuerpo["id"])
    assert documento.siniestro_id == caso.pk and documento.tipo_contenido == "image/png" and documento.subido_por_id == perito08.id
    assert documento.escena == escena()
    assert Auditoria.objects.filter(usuario=perito08, accion="subir_croquis", objeto=f"documento:{documento.pk}", resultado="permitido").exists()
    # aparece en la lista, se previsualiza como imagen y se descarga
    lista = cliente.get(f"/api/siniestros/{caso.pk}/documentos").json()
    assert [(d["tipo"], d["tiene_escena"]) for d in lista] == [("Croquis", True)]
    assert cliente.get(f"/api/documentos/{documento.pk}/ver")["Content-Type"] == "image/png"
    assert "attachment" in cliente.get(f"/api/documentos/{documento.pk}/descargar")["Content-Disposition"]


def test_s29_la_escena_se_puede_pedir_para_reabrir_el_croquis(perito08, caso):
    cliente = cliente_de(perito08)
    id_ = guardar(cliente, caso, escena()).json()["id"]
    respuesta = cliente.get(f"/api/documentos/{id_}/escena")
    assert respuesta.status_code == 200 and respuesta.json() == escena()
    assert Auditoria.objects.filter(usuario=perito08, accion="ver_escena_croquis", resultado="permitido").exists()


def test_s29_guardar_una_edicion_crea_un_documento_nuevo_y_no_pisa_el_original(perito08, caso):
    cliente = cliente_de(perito08)
    original = guardar(cliente, caso, escena()).json()["id"]
    editada = escena(elementos=escena()["elementos"][:1])
    nuevo = guardar(cliente, caso, editada, basado_en=str(original))
    assert nuevo.status_code == 201 and nuevo.json()["id"] != original
    assert Documento.objects.filter(siniestro=caso, tipo="Croquis").count() == 2
    assert cliente.get(f"/api/documentos/{original}/escena").json() == escena()
    assert cliente.get(f"/api/documentos/{nuevo.json()['id']}/escena").json() == editada
    assert Auditoria.objects.get(accion="subir_croquis", objeto=f"documento:{nuevo.json()['id']}").detalle["basado_en"] == original


def test_s29_basado_en_tiene_que_ser_un_croquis_del_mismo_expediente(perito08, caso):
    cliente = cliente_de(perito08)
    otro_caso = crear_siniestro(perito08, "EXP-C-2")
    ajeno = guardar(cliente, otro_caso, escena()).json()["id"]
    respuesta = guardar(cliente, caso, escena(), basado_en=str(ajeno))
    assert respuesta.status_code == 400 and "basado_en" in respuesta.json()
    assert guardar(cliente, caso, escena(), basado_en="no-es-un-numero").status_code == 400
    assert Documento.objects.filter(siniestro=caso).count() == 0


def test_s29_la_imagen_tiene_que_ser_un_png_verdadero(perito08, caso):
    cliente = cliente_de(perito08)
    for malo in (b"GIF89a" + b"\x00" * 20, b"<svg xmlns='http://www.w3.org/2000/svg'/>", b"<html></html>", b""):
        respuesta = guardar(cliente, caso, escena(), imagen=malo)
        assert respuesta.status_code == 400 and "imagen" in respuesta.json()
    sin_imagen = cliente.post(f"/api/siniestros/{caso.pk}/croquis", {"escena": json.dumps(escena())}, format="multipart")
    assert sin_imagen.status_code == 400 and "imagen" in sin_imagen.json()
    assert Documento.objects.count() == 0


def test_s29_la_imagen_no_puede_superar_el_limite(perito08, caso, settings):
    settings.CROQUIS_IMAGEN_MAXIMO = 100
    respuesta = guardar(cliente_de(perito08), caso, escena(), imagen=PNG + b"\x00" * 200)
    assert respuesta.status_code == 400 and "imagen" in respuesta.json()


@pytest.mark.parametrize(
    "mala",
    [
        "esto no es json",
        "[1, 2]",
        "null",
        {"version": 2, "ancho": 1200, "alto": 800, "elementos": []},
        {"version": 1, "ancho": 1200, "alto": 800},  # faltan los elementos
        {"version": 1, "ancho": 10, "alto": 800, "elementos": []},  # ancho fuera de rango
        {"version": 1, "ancho": 1200, "alto": 800, "elementos": [{"tipo": "script", "x": 1, "y": 1}]},
        {"version": 1, "ancho": 1200, "alto": 800, "elementos": [{"tipo": "calle", "x": "uno", "y": 1}]},
        {"version": 1, "ancho": 1200, "alto": 800, "elementos": [{"tipo": "calle", "x": 1e9, "y": 1}]},
        {"version": 1, "ancho": 1200, "alto": 800, "elementos": [{"tipo": "calle", "x": 1, "y": 1, "onclick": "x"}]},
        {"version": 1, "ancho": 1200, "alto": 800, "elementos": [{"tipo": "texto", "x": 1, "y": 1, "texto": "x" * 201}]},
        {"version": 1, "ancho": 1200, "alto": 800, "elementos": [{"tipo": "calle", "x": 1, "y": 1, "color": "url(javascript:1)"}]},
        {"version": 1, "ancho": 1200, "alto": 800, "elementos": [{"tipo": "lapiz", "x": 0, "y": 0, "puntos": []}]},
        {"version": 1, "ancho": 1200, "alto": 800, "elementos": [{"tipo": "lapiz", "x": 0, "y": 0, "puntos": [[1, 2, 3]]}]},
        {"version": 1, "ancho": 1200, "alto": 800, "elementos": [{"tipo": "calle", "x": 1, "y": 1, "puntos": [[1, 2]]}]},
        {"version": 1, "ancho": 1200, "alto": 800, "elementos": [{"tipo": "calle", "x": 1, "y": 1}] * 501},
        {"version": 1, "ancho": 1200, "alto": 800, "elementos": "nada"},
        {"version": 1, "ancho": 1200, "alto": 800, "cuadricula": "si", "elementos": []},
    ],
)
def test_s29_una_escena_invalida_se_rechaza_con_400_y_no_se_guarda_nada(perito08, caso, mala, settings):
    respuesta = guardar(cliente_de(perito08), caso, mala)
    assert respuesta.status_code == 400 and "escena" in respuesta.json()
    assert Documento.objects.count() == 0
    assert not [p for p in __import__("pathlib").Path(settings.DOCUMENTOS_DIR).rglob("*") if p.is_file()]


def test_s29_la_escena_es_obligatoria_y_tiene_un_tamano_maximo(perito08, caso, settings):
    assert guardar(cliente_de(perito08), caso).status_code == 400
    settings.CROQUIS_ESCENA_MAXIMO = 200
    respuesta = guardar(cliente_de(perito08), caso, escena())
    assert respuesta.status_code == 400 and "escena" in respuesta.json()


def test_s29_nan_e_infinito_no_son_numeros_validos(perito08, caso):
    texto = '{"version":1,"ancho":1200,"alto":800,"elementos":[{"tipo":"calle","x":NaN,"y":1}]}'
    assert guardar(cliente_de(perito08), caso, texto).status_code == 400


def test_s29_otro_perito_no_puede_guardar_ni_leer_la_escena_y_queda_auditado(perito08, perito11, caso):
    id_ = guardar(cliente_de(perito08), caso, escena()).json()["id"]
    otro = cliente_de(perito11)
    assert guardar(otro, caso, escena()).status_code == 404
    assert otro.get(f"/api/documentos/{id_}/escena").status_code == 404
    assert Auditoria.objects.filter(usuario=perito11, accion="ver_escena_croquis", resultado="rechazado").exists()
    assert Auditoria.objects.filter(usuario=perito11, accion="subir_croquis", resultado="rechazado").exists()
    assert Documento.objects.filter(siniestro=caso).count() == 1


def test_s29_un_documento_que_no_es_croquis_no_tiene_escena(perito08, caso):
    cliente = cliente_de(perito08)
    id_ = cliente.post(
        f"/api/siniestros/{caso.pk}/documentos",
        {"archivo": SimpleUploadedFile("a.png", PNG, content_type="image/png"), "tipo": "Fotografía"},
        format="multipart",
    ).json()
    assert id_["tiene_escena"] is False
    respuesta = cliente.get(f"/api/documentos/{id_['id']}/escena")
    assert respuesta.status_code == 404 and respuesta.json()["detalle"] == "Este documento no tiene una escena de croquis."


def test_s29_la_subida_comun_no_puede_adjuntar_una_escena(perito08, caso):
    cliente = cliente_de(perito08)
    respuesta = cliente.post(
        f"/api/siniestros/{caso.pk}/documentos",
        {"archivo": SimpleUploadedFile("a.png", PNG, content_type="image/png"), "tipo": "Croquis", "escena": json.dumps(escena())},
        format="multipart",
    )
    assert respuesta.status_code == 201 and Documento.objects.get().escena is None
