"""T03 · Seguridad de acceso (sección 5 del documento): login, bloqueo, restablecimiento, sesión y baja."""
import json
from datetime import datetime, timedelta
from unittest import mock

import pytest
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.sessions.models import Session
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from nucleo.models import Auditoria, Usuario
from tests.conftest import CLAVE, cliente_de, enlace_del_correo

pytestmark = pytest.mark.django_db

MENSAJE_GENERICO = "El correo o la contraseña no son correctos."


def ingresar(cliente, email, password):
    return cliente.post("/api/auth/ingresar", {"email": email, "password": password}, format="json")


def _dentro_de(segundos):
    """Adelanta el reloj del generador de enlaces la cantidad de segundos indicada."""
    ahora = datetime.now()
    return mock.patch.object(PasswordResetTokenGenerator, "_now", lambda self: ahora + timedelta(seconds=segundos))


def definir_contrasena(cliente, uid, token, password):
    return cliente.post("/api/auth/definir-contrasena", {"uid": uid, "token": token, "password": password}, format="json")


# --- Ingreso -----------------------------------------------------------------
def test_ingreso_correcto_devuelve_el_usuario_y_abre_la_sesion(perito08, anonimo):
    respuesta = ingresar(anonimo, "PERITO08@sigs.test", CLAVE)
    assert respuesta.status_code == 200
    usuario = respuesta.json()["usuario"]
    assert usuario["email"] == "perito08@sigs.test"
    assert usuario["rol"] == "perito"
    assert usuario["espacio"]["nombre"] == "Estudio Pericial Norte"
    assert "password" not in usuario
    sesion = anonimo.get("/api/auth/sesion").json()
    assert sesion["autenticado"] is True and sesion["usuario"]["id"] == perito08.id
    assert Auditoria.objects.filter(usuario=perito08, accion="ingreso", resultado="permitido").count() == 1


def test_la_cookie_de_sesion_es_httponly_y_dura_60_minutos(perito08, anonimo):
    respuesta = ingresar(anonimo, perito08.email, CLAVE)
    cookie = respuesta.cookies["sigs_sesion"]
    assert cookie["httponly"]
    assert int(cookie["max-age"]) == 3600


def test_la_sesion_vencida_por_inactividad_ya_no_autentica(perito08, anonimo):
    ingresar(anonimo, perito08.email, CLAVE)
    Session.objects.update(expire_date=timezone.now() - timedelta(minutes=1))
    assert anonimo.get("/api/auth/sesion").json() == {"autenticado": False, "usuario": None}
    assert anonimo.get("/api/siniestros").status_code == 401


def test_el_mensaje_de_error_del_login_no_dice_cual_dato_fallo(perito08, anonimo):
    clave_mala = ingresar(anonimo, perito08.email, "Otra.Clave#1")
    correo_malo = ingresar(anonimo, "no.existe@sigs.test", CLAVE)
    assert clave_mala.status_code == correo_malo.status_code == 400
    assert clave_mala.json() == correo_malo.json() == {"detalle": MENSAJE_GENERICO}


def test_cada_ingreso_fallido_queda_en_la_auditoria_como_rechazado(perito08, anonimo):
    ingresar(anonimo, perito08.email, "Otra.Clave#1")
    registro = Auditoria.objects.get(accion="ingreso_fallido")
    assert registro.resultado == "rechazado" and registro.usuario_id == perito08.id


def test_el_quinto_intento_fallido_bloquea_la_cuenta_y_envia_el_correo(perito08, admin_norte, anonimo):
    for _ in range(4):
        assert ingresar(anonimo, perito08.email, "Mala.Clave#1").status_code == 400
    assert len(mail.outbox) == 0
    assert ingresar(anonimo, perito08.email, "Mala.Clave#1").status_code == 400
    # el aviso llega al usuario con un enlace de restablecimiento
    assert len(mail.outbox) == 1
    aviso = mail.outbox[0]
    assert aviso.to == [perito08.email]
    assert "bloqueada" in aviso.subject.lower() or "bloqueada" in aviso.body.lower()
    assert "/restablecer?uid=" in aviso.body
    # ni siquiera la contraseña correcta deja entrar
    respuesta = ingresar(anonimo, perito08.email, CLAVE)
    assert respuesta.status_code == 400 and respuesta.json() == {"detalle": MENSAJE_GENERICO}
    # quedan auditados los 5 intentos fallidos y el bloqueo
    assert Auditoria.objects.filter(usuario=perito08, accion="ingreso_fallido", resultado="rechazado").count() >= 5
    assert Auditoria.objects.filter(usuario=perito08, accion="bloqueo_cuenta").count() == 1
    # el administrador ve la cuenta bloqueada
    listado = cliente_de(admin_norte).get("/api/admin/usuarios").json()
    fila = next(u for u in listado["resultados"] if u["id"] == perito08.id)
    assert fila["bloqueado_en"] is not None and fila["intentos_fallidos"] == 5


def test_restablecer_desbloquea_la_cuenta_y_pone_en_cero_los_intentos(perito08, admin_norte, anonimo):
    for _ in range(5):
        ingresar(anonimo, perito08.email, "Mala.Clave#1")
    uid, token = enlace_del_correo(mail.outbox[0])
    respuesta = definir_contrasena(anonimo, uid, token, "Nueva.Clave#2027")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"detalle": "Contraseña actualizada. Ya podés ingresar."}
    assert ingresar(anonimo, perito08.email, CLAVE).status_code == 400  # la anterior ya no sirve
    assert ingresar(anonimo, perito08.email, "Nueva.Clave#2027").status_code == 200
    fila = next(u for u in cliente_de(admin_norte).get("/api/admin/usuarios").json()["resultados"] if u["id"] == perito08.id)
    assert fila["bloqueado_en"] is None and fila["intentos_fallidos"] == 0


def test_un_ingreso_correcto_pone_en_cero_los_intentos(perito08, anonimo):
    for _ in range(3):
        ingresar(anonimo, perito08.email, "Mala.Clave#1")
    assert ingresar(anonimo, perito08.email, CLAVE).status_code == 200
    cliente_nuevo = APIClient()
    for _ in range(4):  # si no se hubieran reiniciado, el 2.º fallo ya bloquearía
        ingresar(cliente_nuevo, perito08.email, "Mala.Clave#1")
    assert len(mail.outbox) == 0
    assert ingresar(cliente_nuevo, perito08.email, CLAVE).status_code == 200


def test_el_usuario_dado_de_baja_no_puede_ingresar_y_conserva_su_historial(perito08, admin_norte, anonimo):
    ingresar(anonimo, perito08.email, CLAVE)  # deja una fila de auditoría propia
    assert cliente_de(admin_norte).post(f"/api/admin/usuarios/{perito08.id}/baja").status_code == 200
    respuesta = ingresar(APIClient(), perito08.email, CLAVE)
    assert respuesta.status_code == 400 and respuesta.json() == {"detalle": MENSAJE_GENERICO}
    perito08.refresh_from_db()
    assert perito08.activo is False
    assert Auditoria.objects.filter(usuario=perito08, accion="ingreso", resultado="permitido").exists()


def test_la_sesion_de_un_usuario_dado_de_baja_deja_de_funcionar(perito08, admin_norte, anonimo):
    ingresar(anonimo, perito08.email, CLAVE)
    assert anonimo.get("/api/siniestros").status_code == 200
    cliente_de(admin_norte).post(f"/api/admin/usuarios/{perito08.id}/baja")
    assert anonimo.get("/api/siniestros").status_code == 401


def test_salir_cierra_la_sesion(perito08, anonimo):
    ingresar(anonimo, perito08.email, CLAVE)
    assert anonimo.post("/api/auth/salir").status_code == 204
    assert anonimo.get("/api/auth/sesion").json()["autenticado"] is False
    assert Auditoria.objects.filter(usuario=perito08, accion="salida").exists()


# --- Restablecimiento y enlaces -----------------------------------------------
def test_pedir_el_restablecimiento_responde_lo_mismo_exista_o_no_el_correo(perito08, anonimo):
    conocido = anonimo.post("/api/auth/restablecer", {"email": perito08.email}, format="json")
    desconocido = anonimo.post("/api/auth/restablecer", {"email": "nadie@sigs.test"}, format="json")
    assert conocido.status_code == desconocido.status_code == 200
    assert conocido.json() == desconocido.json()
    assert [m.to for m in mail.outbox] == [[perito08.email]]
    assert "/restablecer?uid=" in mail.outbox[0].body


def test_el_enlace_de_restablecimiento_es_de_un_solo_uso(perito08, anonimo):
    anonimo.post("/api/auth/restablecer", {"email": perito08.email}, format="json")
    uid, token = enlace_del_correo(mail.outbox[0])
    assert anonimo.get("/api/auth/enlace", {"uid": uid, "token": token}).json() == {"valido": True, "email": perito08.email}
    assert definir_contrasena(anonimo, uid, token, "Nueva.Clave#2027").status_code == 200
    segundo = definir_contrasena(anonimo, uid, token, "Otra.Clave#2028")
    assert segundo.status_code == 400
    assert segundo.json() == {"detalle": "El enlace no es válido o venció."}
    assert anonimo.get("/api/auth/enlace", {"uid": uid, "token": token}).json() == {"valido": False, "email": None}


def test_el_enlace_de_restablecimiento_vence_a_la_hora(perito08, anonimo):
    anonimo.post("/api/auth/restablecer", {"email": perito08.email}, format="json")
    uid, token = enlace_del_correo(mail.outbox[0])
    with _dentro_de(segundos=3601):
        vencido = definir_contrasena(anonimo, uid, token, "Nueva.Clave#2027")
    assert vencido.status_code == 400
    assert vencido.json() == {"detalle": "El enlace no es válido o venció."}
    # justo dentro de la hora todavía sirve
    with _dentro_de(segundos=3590):
        assert definir_contrasena(anonimo, uid, token, "Nueva.Clave#2027").status_code == 200


def test_un_enlace_adulterado_o_de_otro_usuario_no_sirve(perito08, perito11, anonimo):
    anonimo.post("/api/auth/restablecer", {"email": perito08.email}, format="json")
    uid, token = enlace_del_correo(mail.outbox[0])
    otro_uid = enlace_del_correo(_enviar_enlace(anonimo, perito11))[0]
    assert definir_contrasena(anonimo, otro_uid, token, "Nueva.Clave#2027").status_code == 400
    assert definir_contrasena(anonimo, uid, token + "x", "Nueva.Clave#2027").status_code == 400
    assert definir_contrasena(anonimo, "basura", token, "Nueva.Clave#2027").status_code == 400


def _enviar_enlace(cliente, usuario):
    cliente.post("/api/auth/restablecer", {"email": usuario.email}, format="json")
    return mail.outbox[-1]


def test_el_enlace_de_un_usuario_dado_de_baja_no_sirve(perito08, anonimo):
    anonimo.post("/api/auth/restablecer", {"email": perito08.email}, format="json")
    uid, token = enlace_del_correo(mail.outbox[0])
    Usuario.objects.filter(pk=perito08.pk).update(activo=False)
    assert definir_contrasena(anonimo, uid, token, "Nueva.Clave#2027").status_code == 400


# --- Política de contraseña -----------------------------------------------------
@pytest.mark.parametrize(
    "clave, fragmento",
    [
        ("Ab1$", "al menos 8 caracteres"),
        ("sin.mayuscula#1", "mayúscula"),
        ("SIN.MINUSCULA#1", "minúscula"),
        ("Sin.Numero.Aqui#", "número"),
        ("SinEspecial2026", "carácter especial"),
        ("Password1!", "demasiado común"),
    ],
)
def test_la_politica_de_contrasena_rechaza_las_claves_debiles_con_mensajes_en_espanol(perito08, anonimo, clave, fragmento):
    anonimo.post("/api/auth/restablecer", {"email": perito08.email}, format="json")
    uid, token = enlace_del_correo(mail.outbox[0])
    respuesta = definir_contrasena(anonimo, uid, token, clave)
    assert respuesta.status_code == 400
    mensajes = " ".join(respuesta.json()["password"])
    assert fragmento in mensajes
    # la contraseña no cambió y el enlace sigue sirviendo
    assert ingresar(anonimo, perito08.email, CLAVE).status_code == 200


def test_la_contrasena_parecida_al_nombre_o_al_correo_se_rechaza(perito08, anonimo):
    anonimo.post("/api/auth/restablecer", {"email": perito08.email}, format="json")
    uid, token = enlace_del_correo(mail.outbox[0])
    respuesta = definir_contrasena(anonimo, uid, token, "Perito08@sigs.test1!")
    assert respuesta.status_code == 400 and "password" in respuesta.json()


def test_el_validador_de_complejidad_acepta_una_clave_que_cumple(perito08, anonimo):
    anonimo.post("/api/auth/restablecer", {"email": perito08.email}, format="json")
    uid, token = enlace_del_correo(mail.outbox[0])
    assert definir_contrasena(anonimo, uid, token, "Correcta.Y.Larga#42").status_code == 200


# --- CSRF y sesión ---------------------------------------------------------------
def test_la_api_exige_csrf_en_las_solicitudes_que_modifican_datos(perito08):
    cliente = APIClient(enforce_csrf_checks=True)
    respuesta = cliente.get("/api/auth/sesion")
    token = respuesta.cookies["csrftoken"].value
    sin_token = cliente.post("/api/auth/ingresar", {"email": perito08.email, "password": CLAVE}, format="json")
    assert sin_token.status_code == 403
    assert sin_token.json() == {"detalle": "Falta o no es válido el token CSRF."}
    assert Auditoria.objects.filter(accion="csrf_fallido", resultado="rechazado").exists()
    con_token = cliente.post(
        "/api/auth/ingresar", {"email": perito08.email, "password": CLAVE}, format="json", HTTP_X_CSRFTOKEN=token
    )
    assert con_token.status_code == 200
    # ya autenticado, un POST sin token también se rechaza
    assert cliente.post("/api/auth/salir").status_code == 403


def test_sesion_siempre_entrega_la_cookie_csrf_y_nunca_responde_401(anonimo):
    respuesta = anonimo.get("/api/auth/sesion")
    assert respuesta.status_code == 200
    assert "csrftoken" in respuesta.cookies
    assert respuesta.json() == {"autenticado": False, "usuario": None}


def test_health_es_publico(anonimo):
    assert anonimo.get("/api/health").json() == {"estado": "ok"}


def test_un_usuario_bloqueado_por_el_administrador_pierde_la_sesion(perito08, admin_norte, anonimo):
    ingresar(anonimo, perito08.email, CLAVE)
    respuesta = cliente_de(admin_norte).post(f"/api/admin/usuarios/{perito08.id}/bloquear")
    assert respuesta.status_code == 200
    assert anonimo.get("/api/siniestros").status_code == 401
    assert ingresar(APIClient(), perito08.email, CLAVE).status_code == 400
    assert Auditoria.objects.filter(usuario=admin_norte, accion="bloquear_cuenta", objeto=f"usuario:{perito08.id}").exists()


def test_la_configuracion_de_sesion_y_enlaces_es_la_del_documento(settings):
    assert settings.SESSION_COOKIE_AGE == 3600 and settings.SESSION_SAVE_EVERY_REQUEST is True
    assert settings.PASSWORD_RESET_TIMEOUT == 3600
    assert settings.SESSION_COOKIE_HTTPONLY is True


def test_sesion_con_cuenta_bloqueada_por_la_base_responde_no_autenticado_y_no_401(perito08, anonimo):
    ingresar(anonimo, perito08.email, CLAVE)
    Usuario.objects.filter(pk=perito08.pk).update(bloqueado_en=timezone.now())  # sesión vieja que quedó abierta
    respuesta = anonimo.get("/api/auth/sesion")
    assert respuesta.status_code == 200 and respuesta.json() == {"autenticado": False, "usuario": None}
    assert anonimo.get("/api/siniestros").status_code == 401


def test_la_vista_de_csrf_fallido_responde_json_y_audita(perito08):
    from django.test import RequestFactory

    from nucleo.vistas.base import csrf_fallido

    solicitud = RequestFactory().post("/api/siniestros")
    solicitud.user = perito08
    respuesta = csrf_fallido(solicitud, reason="CSRF token missing")
    assert respuesta.status_code == 403
    assert json.loads(respuesta.content) == {"detalle": "Falta o no es válido el token CSRF."}
    assert Auditoria.objects.filter(usuario=perito08, accion="csrf_fallido", resultado="rechazado").exists()


def test_no_hay_migraciones_pendientes():
    from django.core.management import call_command

    call_command("makemigrations", "--check", "--dry-run", verbosity=0)
