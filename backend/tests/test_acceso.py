"""T04 / TT-03 · Pruebas de acceso directo a la API: A1–A8, 3 solicitudes cada una = 24 rechazos.

Cada solicitud tiene que responder 403 o 404 sin filtrar datos y dejar una fila de auditoría
con `resultado = rechazado`.
"""
import json
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from nucleo.fabrica import crear_siniestro
from nucleo.models import Auditoria
from tests.conftest import cliente_de

pytestmark = pytest.mark.django_db

DATOS_SENSIBLES = ["30111017", "P-17", "Relato ficticio", "EXP-NORTE", "AB123CD", "secreto.txt", "contenido-privado", "nota privada"]
ASEGURADO = [{"tipo_identificador": "DNI", "identificador": "30111017", "nombre": "P-17", "roles": ["asegurado"]}]


class Escena:
    pass


@pytest.fixture
def escena(norte, sur, perito08, perito11, perito15, admin_norte, admin_sur, superadmin):
    e = Escena()
    ahora = timezone.now()
    poliza = {"numero": "AUT-1", "compania": "Aseguradora Ejemplo", "cobertura": "Todo riesgo", "inicio_vigencia": "2026-01-01", "primer_pago": "2026-01-05"}
    e.norte = crear_siniestro(
        perito08, "EXP-NORTE", tipo="Incendio total", fecha_hecho=ahora - timedelta(days=10), poliza=poliza,
        relato="Relato ficticio del hecho.", personas=ASEGURADO, bienes=["AB-123-CD"],
    )
    e.borrador = crear_siniestro(
        perito08, "EXP-BORRADOR", estado="borrador", fecha_hecho=ahora - timedelta(days=3), poliza=poliza, personas=ASEGURADO,
    )
    e.sur_vinculado = crear_siniestro(
        perito15, "S-SUR-VINCULADO", fecha_hecho=ahora - timedelta(days=400), bienes=["AB123CD"],
        cierre={"resultado_reclamo": "aprobado", "valoracion": 7}, estado="cerrado",
    )
    e.sur_no_vinculado = crear_siniestro(perito15, "S-SUR-NO-VINCULADO", fecha_hecho=ahora - timedelta(days=100), bienes=["ZZ999ZZ"])
    e.sur_anulado = crear_siniestro(
        perito15, "S-SUR-ANULADO", fecha_hecho=ahora - timedelta(days=100), personas=ASEGURADO, estado="anulado", motivo_anulacion="Carga errónea",
    )
    c08 = cliente_de(perito08)
    subida = c08.post(
        f"/api/siniestros/{e.norte.id}/documentos",
        {"archivo": SimpleUploadedFile("secreto.txt", b"contenido-privado", content_type="text/plain"), "tipo": "Fotografía"},
        format="multipart",
    )
    assert subida.status_code == 201, subida.content
    e.documento_id = subida.json()["id"]
    assert c08.post(f"/api/siniestros/{e.norte.id}/notas", {"texto": "nota privada del perito"}, format="json").status_code == 201
    tarea = c08.post(f"/api/siniestros/{e.norte.id}/tareas", {"titulo": "tarea privada"}, format="json")
    assert tarea.status_code == 201
    e.tarea_id = tarea.json()["id"]
    e.auditoria_id = Auditoria.objects.filter(espacio_id=norte.id).first().id
    return e


def solicitudes(e, usuarios):
    """Las 24 solicitudes: `{id: [(usuario, método, ruta, cuerpo, estado esperado), ...]}`."""
    p08, p11, p15, adm_norte = usuarios["perito08"], usuarios["perito11"], usuarios["perito15"], usuarios["admin_norte"]
    n, b = e.norte.id, e.borrador.id
    return {
        "A1": [
            (p08, "get", f"/api/siniestros/{b}/coincidencias", None, 403),
            (p08, "get", f"/api/siniestros/{b}/evaluacion", None, 403),
            (p08, "get", f"/api/siniestros/{b}/antecedentes/{e.sur_vinculado.id}/resumen", None, 403),
        ],
        "A2": [
            (p15, "get", f"/api/siniestros/{n}", None, 404),
            (p15, "patch", f"/api/siniestros/{n}", {"tipo": "Cambiado"}, 404),
            (p15, "get", f"/api/siniestros/{n}/evaluacion", None, 404),
        ],
        "A3": [
            (p15, "get", f"/api/documentos/{e.documento_id}/descargar", None, 404),
            (p11, "get", f"/api/documentos/{e.documento_id}/descargar", None, 404),
            (adm_norte, "get", f"/api/documentos/{e.documento_id}/descargar", None, 404),
        ],
        "A4": [
            (p15, "get", f"/api/siniestros/{n}/notas", None, 404),
            (p11, "get", f"/api/siniestros/{n}/notas", None, 404),
            (p11, "get", f"/api/siniestros/{n}/tareas", None, 404),
        ],
        "A5": [
            (p08, "get", "/api/personas?dni=30111017", None, 403),
            (p08, "get", "/api/personas/30111017", None, 403),
            (p15, "post", "/api/personas/buscar", {"dni": "30111017"}, 403),
        ],
        "A6": [
            (p08, "get", f"/api/siniestros/{n}/antecedentes/{e.sur_no_vinculado.id}/resumen", None, 404),
            (p08, "get", f"/api/siniestros/{n}/antecedentes/{e.sur_anulado.id}/resumen", None, 404),
            (p08, "get", f"/api/siniestros/{n}/antecedentes/{e.borrador.id}/resumen", None, 404),
        ],
        "A7": [
            (adm_norte, "put", f"/api/auditoria/{e.auditoria_id}", {"accion": "x"}, 403),
            (adm_norte, "patch", f"/api/auditoria/{e.auditoria_id}", {"resultado": "permitido"}, 403),
            (adm_norte, "delete", f"/api/auditoria/{e.auditoria_id}", None, 403),
        ],
        "A8": [
            (p08, "post", "/api/reglas/versiones", {"version": "RS-9.9", "vigente_desde": "2026-12-01", "reglas": {}}, 403),
            (adm_norte, "post", "/api/reglas/versiones", {"version": "RS-9.8", "vigente_desde": "2026-12-01", "reglas": {}}, 403),
            (p11, "post", "/api/reglas/versiones", {"version": "RS-9.7", "vigente_desde": "2026-12-01", "reglas": {}}, 403),
        ],
    }


@pytest.fixture
def usuarios(perito08, perito11, perito15, admin_norte, admin_sur, superadmin):
    return {"perito08": perito08, "perito11": perito11, "perito15": perito15, "admin_norte": admin_norte,
            "admin_sur": admin_sur, "superadmin": superadmin}


def _ejecutar(usuario, metodo, ruta, cuerpo):
    cliente = cliente_de(usuario)
    if cuerpo is None:
        return getattr(cliente, metodo)(ruta)
    return getattr(cliente, metodo)(ruta, cuerpo, format="json")


@pytest.mark.parametrize("prueba", ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"])
def test_el_acceso_no_autorizado_se_rechaza_sin_filtrar_datos_y_queda_auditado(escena, usuarios, prueba):
    for usuario, metodo, ruta, cuerpo, estado in solicitudes(escena, usuarios)[prueba]:
        antes = Auditoria.objects.filter(resultado="rechazado").count()
        respuesta = _ejecutar(usuario, metodo, ruta, cuerpo)
        assert respuesta.status_code == estado, f"{prueba} {metodo.upper()} {ruta}: {respuesta.status_code} {respuesta.content}"
        # el cuerpo es solo un mensaje: sin datos del expediente
        cuerpo_respuesta = respuesta.json()
        assert list(cuerpo_respuesta) == ["detalle"]
        texto = json.dumps(cuerpo_respuesta, ensure_ascii=False)
        for dato in DATOS_SENSIBLES:
            assert dato not in texto, f"{prueba} filtró «{dato}»"
        # y queda una fila nueva en la auditoría, rechazada y del usuario que lo intentó
        assert Auditoria.objects.filter(resultado="rechazado").count() == antes + 1
        registro = Auditoria.objects.filter(resultado="rechazado").latest("id")
        assert registro.usuario_id == usuario.id
        assert registro.detalle["estado"] == estado


def test_las_24_solicitudes_directas_dejan_24_rechazos_auditados(escena, usuarios):
    antes = Auditoria.objects.filter(resultado="rechazado").count()
    total = 0
    for lista in solicitudes(escena, usuarios).values():
        for usuario, metodo, ruta, cuerpo, estado in lista:
            assert _ejecutar(usuario, metodo, ruta, cuerpo).status_code == estado
            total += 1
    assert total == 24
    assert Auditoria.objects.filter(resultado="rechazado").count() - antes == 24


def test_un_expediente_ajeno_y_uno_inexistente_responden_igual(escena, perito15):
    ajeno = cliente_de(perito15).get(f"/api/siniestros/{escena.norte.id}")
    inexistente = cliente_de(perito15).get("/api/siniestros/999999")
    assert ajeno.status_code == inexistente.status_code == 404
    assert ajeno.json() == inexistente.json()


def test_el_rechazo_de_un_resumen_se_audita_con_el_siniestro_de_origen(escena, perito08):
    cliente_de(perito08).get(f"/api/siniestros/{escena.norte.id}/antecedentes/{escena.sur_no_vinculado.id}/resumen")
    registro = Auditoria.objects.get(accion="ver_resumen_antecedente", resultado="rechazado")
    assert registro.siniestro_origen_id == escena.norte.id
    assert registro.objeto == f"siniestro:{escena.sur_no_vinculado.id}"
    assert registro.usuario_id == perito08.id


def test_sin_sesion_la_api_responde_401_y_audita_el_rechazo_sin_usuario(escena, anonimo):
    respuesta = anonimo.get(f"/api/siniestros/{escena.norte.id}")
    assert respuesta.status_code == 401
    registro = Auditoria.objects.filter(resultado="rechazado").latest("id")
    assert registro.usuario_id is None and registro.accion == f"GET /api/siniestros/{escena.norte.id}"


def test_el_administrador_y_el_superadministrador_no_leen_expedientes(escena, admin_norte, superadmin):
    for usuario in (admin_norte, superadmin):
        cliente = cliente_de(usuario)
        for ruta in (f"/api/siniestros/{escena.norte.id}", f"/api/siniestros/{escena.norte.id}/notas", "/api/siniestros"):
            respuesta = cliente.get(ruta)
            assert respuesta.status_code == 403, (usuario.rol, ruta)
            assert "Relato" not in json.dumps(respuesta.json())
    assert Auditoria.objects.filter(resultado="rechazado", usuario=admin_norte).count() == 3


def test_una_ruta_inexistente_bajo_api_responde_json_y_se_audita(perito08):
    respuesta = cliente_de(perito08).get("/api/no/existe")
    assert respuesta.status_code == 404
    assert respuesta.json() == {"detalle": "No se encontró lo que pedís."}
    assert Auditoria.objects.filter(usuario=perito08, resultado="rechazado", accion="GET /api/no/existe").exists()


def test_un_metodo_no_permitido_se_rechaza_y_se_audita(perito08):
    respuesta = cliente_de(perito08).delete("/api/siniestros")
    assert respuesta.status_code == 405
    assert respuesta.json() == {"detalle": "Método no permitido."}
    assert Auditoria.objects.filter(usuario=perito08, resultado="rechazado", accion="DELETE /api/siniestros").exists()


def test_otro_perito_del_mismo_espacio_no_accede_a_nada_del_expediente(escena, perito11):
    """S14: solo el perito asignado accede. El resto, aunque sea del mismo espacio, recibe 404 y queda auditado."""
    cliente = cliente_de(perito11)
    n, b = escena.norte.id, escena.borrador.id
    rutas = (
        ("get", f"/api/siniestros/{n}", None),
        ("get", f"/api/siniestros/{n}/evaluacion", None),
        ("get", f"/api/siniestros/{n}/evaluaciones", None),
        ("get", f"/api/siniestros/{n}/coincidencias", None),
        ("get", f"/api/siniestros/{n}/antecedentes/{escena.sur_vinculado.id}/resumen", None),
        ("get", f"/api/siniestros/{n}/cierre", None),
        ("get", f"/api/siniestros/{n}/documentos", None),
        ("get", f"/api/siniestros/{n}/notas", None),
        ("get", f"/api/siniestros/{n}/tareas", None),
        ("post", f"/api/siniestros/{n}/recalcular", None),
        ("post", f"/api/siniestros/{n}/notas", {"texto": "intruso"}),
        ("post", f"/api/siniestros/{n}/tareas", {"titulo": "intruso"}),
        ("post", f"/api/siniestros/{n}/cierre", {"resultado_reclamo": "aprobado", "valoracion": 5, "justificacion": "x"}),
        ("post", f"/api/siniestros/{n}/archivar", None),
        ("post", f"/api/siniestros/{n}/anular", {"motivo": "x"}),
        ("post", f"/api/siniestros/{b}/confirmar", None),
        ("patch", f"/api/siniestros/{b}", {"tipo": "Cambiado"}),
        ("get", f"/api/siniestros/{b}", None),
        ("patch", f"/api/tareas/{escena.tarea_id}", {"estado": "hecha"}),
    )
    for metodo, ruta, cuerpo in rutas:
        antes = Auditoria.objects.filter(resultado="rechazado", usuario=perito11).count()
        respuesta = getattr(cliente, metodo)(ruta, cuerpo, format="json") if cuerpo else getattr(cliente, metodo)(ruta)
        assert respuesta.status_code == 404, (metodo, ruta, respuesta.content)
        assert list(respuesta.json()) == ["detalle"]
        assert Auditoria.objects.filter(resultado="rechazado", usuario=perito11).count() == antes + 1, (metodo, ruta)
    escena.norte.refresh_from_db()
    escena.borrador.refresh_from_db()
    assert escena.norte.estado == "en_analisis" and escena.borrador.estado == "borrador" and escena.borrador.tipo == "Choque"
    from nucleo.models import Cierre, Evaluacion, Nota, Tarea

    assert (Nota.objects.count(), Tarea.objects.count(), Cierre.objects.filter(siniestro=escena.norte).count()) == (1, 1, 0)
    assert Tarea.objects.get().estado == "pendiente"


def test_el_otro_perito_del_mismo_espacio_recibe_lo_mismo_que_ante_un_expediente_inexistente(escena, perito11):
    ajeno = cliente_de(perito11).get(f"/api/siniestros/{escena.norte.id}")
    inexistente = cliente_de(perito11).get("/api/siniestros/999999")
    assert ajeno.status_code == inexistente.status_code == 404
    assert ajeno.json() == inexistente.json()


def test_el_perito_asignado_sigue_accediendo_a_todo_su_expediente(escena, perito08):
    cliente = cliente_de(perito08)
    n = escena.norte.id
    assert cliente.post(f"/api/siniestros/{n}/recalcular").status_code == 200
    for ruta in ("", "/evaluacion", "/evaluaciones", "/coincidencias", "/cierre", "/documentos", "/notas", "/tareas",
                 f"/antecedentes/{escena.sur_vinculado.id}/resumen"):
        assert cliente.get(f"/api/siniestros/{n}{ruta}").status_code == 200, ruta


def test_el_panel_solo_muestra_los_expedientes_propios(escena, perito11):
    cuerpo = cliente_de(perito11).get("/api/siniestros").json()
    assert cuerpo["resultados"] == []


def test_los_24_rechazos_dejan_los_datos_sin_cambios(escena, usuarios):
    from nucleo.models import ConjuntoReglas, Documento, Nota, Tarea

    registro = Auditoria.objects.get(pk=escena.auditoria_id)
    accion_original = registro.accion
    for lista in solicitudes(escena, usuarios).values():
        for usuario, metodo, ruta, cuerpo, estado in lista:
            assert _ejecutar(usuario, metodo, ruta, cuerpo).status_code == estado
    escena.norte.refresh_from_db()
    assert escena.norte.tipo == "Incendio total" and escena.norte.estado == "en_analisis"
    assert ConjuntoReglas.objects.count() == 1 and ConjuntoReglas.objects.get().version == "RS-1.0"
    assert Auditoria.objects.get(pk=escena.auditoria_id).accion == accion_original
    assert (Nota.objects.count(), Tarea.objects.count(), Documento.objects.count()) == (1, 1, 1)
