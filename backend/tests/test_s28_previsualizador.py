"""S28 · Previsualizador: `GET /api/documentos/<id>/ver` sirve en línea solo imágenes, PDF y texto plano."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from nucleo.fabrica import crear_siniestro
from nucleo.models import Auditoria
from tests.conftest import cliente_de

pytestmark = pytest.mark.django_db

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 20
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 20
GIF = b"GIF89a" + b"\x00" * 20
WEBP = b"RIFF\x1a\x00\x00\x00WEBPVP8 " + b"\x00" * 20
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
TEXTO = "Acta de inspección: daños en el vehículo.\n".encode()

CSP_SEGURA = "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"


@pytest.fixture
def caso(perito08):
    return crear_siniestro(perito08, "EXP-V-1")


def subir(cliente, caso, nombre, contenido, tipo_contenido):
    respuesta = cliente.post(
        f"/api/siniestros/{caso.pk}/documentos",
        {"archivo": SimpleUploadedFile(nombre, contenido, content_type=tipo_contenido), "tipo": "Fotografía"},
        format="multipart",
    )
    assert respuesta.status_code == 201, respuesta.content
    return respuesta.json()["id"]


@pytest.mark.parametrize(
    "nombre, contenido, tipo_contenido, tipo_servido",
    [
        ("foto.png", PNG, "image/png", "image/png"),
        ("foto.jpg", JPEG, "image/jpeg", "image/jpeg"),
        ("foto.gif", GIF, "image/gif", "image/gif"),
        ("foto.webp", WEBP, "image/webp", "image/webp"),
        ("informe.pdf", PDF, "application/pdf", "application/pdf"),
        ("acta.txt", TEXTO, "text/plain", "text/plain; charset=utf-8"),
        ("acta.txt", TEXTO, "text/plain; charset=iso-8859-1", "text/plain; charset=utf-8"),
    ],
)
def test_s28_los_tipos_seguros_se_sirven_en_linea_con_su_tipo_detectado(perito08, caso, nombre, contenido, tipo_contenido, tipo_servido):
    cliente = cliente_de(perito08)
    id_ = subir(cliente, caso, nombre, contenido, tipo_contenido)
    respuesta = cliente.get(f"/api/documentos/{id_}/ver")
    assert respuesta.status_code == 200
    assert b"".join(respuesta.streaming_content) == contenido
    assert respuesta["Content-Type"] == tipo_servido
    assert respuesta["Content-Disposition"].startswith("inline;") and nombre in respuesta["Content-Disposition"]
    assert respuesta["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in respuesta["Cache-Control"]


def test_s28_la_politica_de_contenido_aisla_el_archivo_y_el_pdf_conserva_su_visor(perito08, caso):
    cliente = cliente_de(perito08)
    imagen = cliente.get(f"/api/documentos/{subir(cliente, caso, 'a.png', PNG, 'image/png')}/ver")
    assert imagen["Content-Security-Policy"] == CSP_SEGURA
    pdf = cliente.get(f"/api/documentos/{subir(cliente, caso, 'a.pdf', PDF, 'application/pdf')}/ver")
    # el visor de PDF del navegador no funciona dentro de un `sandbox`: se mantiene el resto de la política
    assert "sandbox" not in pdf["Content-Security-Policy"] and "default-src 'none'" in pdf["Content-Security-Policy"]
    assert pdf["X-Frame-Options"] == "SAMEORIGIN"


@pytest.mark.parametrize(
    "nombre, contenido, tipo_contenido",
    [
        ("dibujo.svg", b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>', "image/svg+xml"),
        ("pagina.html", b"<html><script>alert(1)</script></html>", "text/html"),
        ("datos.xml", b"<?xml version='1.0'?><a/>", "application/xml"),
        ("codigo.js", b"alert(1)", "application/javascript"),
        ("foto.png", b"<html><script>alert(1)</script></html>", "image/png"),  # dice ser imagen y no lo es
        ("foto.png", JPEG, "image/png"),  # la firma no coincide con el tipo declarado
        ("foto.png", PNG, "application/octet-stream"),  # tipo declarado no seguro, aunque la firma sea de PNG
        ("pagina.txt", b"<html><script>alert(1)</script></html>", "text/html"),
        ("binario.txt", b"abc\x00def", "text/plain"),  # texto con bytes nulos
        ("latin1.txt", "acción".encode("latin-1"), "text/plain"),  # no es UTF-8
        ("informe.pdf", TEXTO, "application/pdf"),
    ],
)
def test_s28_el_contenido_activo_o_dudoso_se_rechaza_con_415_y_queda_auditado(perito08, caso, nombre, contenido, tipo_contenido):
    cliente = cliente_de(perito08)
    id_ = subir(cliente, caso, nombre, contenido, tipo_contenido)
    respuesta = cliente.get(f"/api/documentos/{id_}/ver")
    assert respuesta.status_code == 415
    assert respuesta.json()["detalle"].startswith("Este tipo de archivo no se puede previsualizar")
    assert respuesta["X-Content-Type-Options"] == "nosniff"
    assert Auditoria.objects.filter(usuario=perito08, accion="ver_documento", objeto=f"documento:{id_}", resultado="rechazado").exists()
    # la descarga sigue siendo siempre como adjunto
    assert "attachment" in cliente.get(f"/api/documentos/{id_}/descargar")["Content-Disposition"]


def test_s28_ver_audita_el_acceso_permitido_con_el_expediente_de_origen(perito08, caso):
    cliente = cliente_de(perito08)
    id_ = subir(cliente, caso, "a.png", PNG, "image/png")
    cliente.get(f"/api/documentos/{id_}/ver")
    fila = Auditoria.objects.get(usuario=perito08, accion="ver_documento", resultado="permitido")
    assert fila.objeto == f"documento:{id_}" and fila.siniestro_origen_id == caso.pk


def test_s28_otro_perito_recibe_404_y_queda_auditado_como_rechazado(perito08, perito11, perito15, caso):
    id_ = subir(cliente_de(perito08), caso, "a.png", PNG, "image/png")
    for otro in (perito11, perito15):
        respuesta = cliente_de(otro).get(f"/api/documentos/{id_}/ver")
        assert respuesta.status_code == 404
        assert Auditoria.objects.filter(usuario=otro, accion="ver_documento", resultado="rechazado").exists()
    assert not Auditoria.objects.filter(accion="ver_documento", resultado="permitido").exists()


def test_s28_administrador_y_anonimo_no_acceden_y_un_documento_inexistente_da_404(perito08, admin_norte, anonimo, caso):
    id_ = subir(cliente_de(perito08), caso, "a.png", PNG, "image/png")
    assert cliente_de(admin_norte).get(f"/api/documentos/{id_}/ver").status_code == 404
    assert anonimo.get(f"/api/documentos/{id_}/ver").status_code in (401, 403)
    assert cliente_de(perito08).get("/api/documentos/99999/ver").status_code == 404


def test_s28_si_el_archivo_falta_en_el_volumen_responde_404(perito08, caso, settings):
    import shutil

    cliente = cliente_de(perito08)
    id_ = subir(cliente, caso, "a.png", PNG, "image/png")
    shutil.rmtree(settings.DOCUMENTOS_DIR)
    assert cliente.get(f"/api/documentos/{id_}/ver").status_code == 404


def test_s28_la_lista_de_documentos_dice_si_se_puede_previsualizar(perito08, caso):
    cliente = cliente_de(perito08)
    subir(cliente, caso, "a.png", PNG, "image/png")
    subir(cliente, caso, "a.svg", b"<svg/>", "image/svg+xml")
    lista = {d["nombre_original"]: d for d in cliente.get(f"/api/siniestros/{caso.pk}/documentos").json()}
    assert lista["a.png"]["previsualizable"] == "image/png"
    assert lista["a.svg"]["previsualizable"] is None
