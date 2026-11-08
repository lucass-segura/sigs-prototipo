"""T12 · HU-01, HU-02, HU-15 y HU-17: roles, usuarios y espacios, auditoría del espacio y perfil de contacto."""
import pytest
from django.core import mail
from rest_framework.test import APIClient

from nucleo.models import Auditoria, EspacioTrabajo, Usuario
from tests.conftest import CLAVE, cliente_de, enlace_del_correo

pytestmark = pytest.mark.django_db


# --- HU-01 ----------------------------------------------------------------------------
def test_hu01_con_credenciales_validas_el_perito_ve_su_panel(perito08):
    cliente = APIClient()
    assert cliente.post("/api/auth/ingresar", {"email": perito08.email, "password": CLAVE}, format="json").status_code == 200
    panel = cliente.get("/api/siniestros")
    assert panel.status_code == 200 and set(panel.json()) == {"resultados", "resumen"}


def test_hu01_un_perito_no_puede_administrar_las_reglas(perito08):
    cliente = cliente_de(perito08)
    respuesta = cliente.post("/api/reglas/versiones", {"version": "RS-2.0", "vigente_desde": "2026-12-01", "reglas": {}}, format="json")
    assert respuesta.status_code == 403
    assert respuesta.json() == {"detalle": "Solo el superadministrador publica versiones de reglas."}
    # puede leerlas, no cambiarlas
    assert cliente.get("/api/reglas").status_code == 200


def test_hu01_cada_rol_ve_solo_lo_suyo(perito08, admin_norte, superadmin):
    assert cliente_de(perito08).get("/api/admin/usuarios").status_code == 403
    assert cliente_de(perito08).get("/api/admin/espacios").status_code == 403
    assert cliente_de(perito08).get("/api/auditoria").status_code == 403
    assert cliente_de(admin_norte).get("/api/admin/espacios").status_code == 403
    assert cliente_de(superadmin).get("/api/admin/usuarios").status_code == 403
    assert cliente_de(superadmin).get("/api/auditoria").status_code == 403


# --- HU-02 ----------------------------------------------------------------------------
def test_hu02_el_usuario_dado_de_alta_recibe_el_enlace_define_su_contrasena_e_ingresa_con_su_rol(admin_norte):
    cliente = cliente_de(admin_norte)
    respuesta = cliente.post("/api/admin/usuarios", {"nombre": "PE-20", "email": "Nuevo.Perito@sigs.test", "rol": "perito"}, format="json")
    assert respuesta.status_code == 201, respuesta.content
    assert respuesta.json()["email"] == "nuevo.perito@sigs.test" and respuesta.json()["rol"] == "perito"
    assert respuesta.json()["espacio"]["nombre"] == "Estudio Pericial Norte"
    # sin contraseña usable: no puede ingresar todavía
    assert APIClient().post("/api/auth/ingresar", {"email": "nuevo.perito@sigs.test", "password": CLAVE}, format="json").status_code == 400
    # el correo trae el enlace de primer ingreso
    aviso = mail.outbox[-1]
    assert aviso.to == ["nuevo.perito@sigs.test"] and "/primer-ingreso?uid=" in aviso.body
    uid, token = enlace_del_correo(aviso)
    anonimo = APIClient()
    definir = anonimo.post("/api/auth/definir-contrasena", {"uid": uid, "token": token, "password": "Mi.Propia#Clave9"}, format="json")
    assert definir.status_code == 200
    ingreso = anonimo.post("/api/auth/ingresar", {"email": "nuevo.perito@sigs.test", "password": "Mi.Propia#Clave9"}, format="json")
    assert ingreso.status_code == 200 and ingreso.json()["usuario"]["rol"] == "perito"
    assert Auditoria.objects.filter(accion="primer_ingreso", resultado="permitido").exists()
    assert Auditoria.objects.filter(usuario=admin_norte, accion="alta_usuario").exists()


def test_hu02_ni_el_administrador_conoce_la_contrasena_del_usuario(admin_norte):
    cliente = cliente_de(admin_norte)
    cliente.post("/api/admin/usuarios", {"nombre": "PE-21", "email": "p21@sigs.test", "rol": "perito"}, format="json")
    usuario = Usuario.objects.get(email="p21@sigs.test")
    assert not usuario.has_usable_password()
    listado = cliente.get("/api/admin/usuarios").content.decode()
    assert "password" not in listado


def test_hu02_el_correo_es_unico_en_todo_el_sistema(admin_norte, perito15):
    cliente = cliente_de(admin_norte)
    repetido = cliente.post("/api/admin/usuarios", {"nombre": "Otro", "email": perito15.email.upper(), "rol": "perito"}, format="json")
    assert repetido.status_code == 400
    assert repetido.json() == {"email": ["Ya existe un usuario con ese correo."]}
    assert Usuario.objects.filter(email=perito15.email).count() == 1


@pytest.mark.parametrize("cuerpo", [
    {"nombre": "", "email": "a@sigs.test", "rol": "perito"},
    {"nombre": "A", "email": "no-es-correo", "rol": "perito"},
    {"nombre": "A", "email": "a@sigs.test", "rol": "superadministrador"},
    {"nombre": "A", "email": "a@sigs.test", "rol": "inventado"},
])
def test_hu02_el_alta_rechaza_datos_invalidos_y_no_se_puede_crear_un_superadministrador(admin_norte, cuerpo):
    assert cliente_de(admin_norte).post("/api/admin/usuarios", cuerpo, format="json").status_code == 400
    assert Usuario.objects.filter(email="a@sigs.test").count() == 0


def test_hu02_el_administrador_solo_ve_y_gestiona_los_usuarios_de_su_espacio(admin_norte, perito08, perito15):
    cliente = cliente_de(admin_norte)
    emails = {u["email"] for u in cliente.get("/api/admin/usuarios").json()["resultados"]}
    assert perito08.email in emails and perito15.email not in emails
    for accion in ("baja", "bloquear", "reenviar-enlace"):
        assert cliente.post(f"/api/admin/usuarios/{perito15.id}/{accion}").status_code == 404
    perito15.refresh_from_db()
    assert perito15.activo and perito15.bloqueado_en is None


def test_hu02_el_usuario_dado_de_baja_no_ingresa_y_conserva_su_historial(admin_norte, perito08):
    cliente_de(perito08).get("/api/siniestros")
    assert cliente_de(admin_norte).post(f"/api/admin/usuarios/{perito08.id}/baja").status_code == 200
    assert APIClient().post("/api/auth/ingresar", {"email": perito08.email, "password": CLAVE}, format="json").status_code == 400
    assert Usuario.objects.get(pk=perito08.pk).activo is False
    assert Auditoria.objects.filter(usuario=perito08).exists()
    fila = next(u for u in cliente_de(admin_norte).get("/api/admin/usuarios").json()["resultados"] if u["id"] == perito08.id)
    assert fila["activo"] is False


def test_hu02_el_administrador_no_puede_darse_de_baja_ni_bloquearse_a_si_mismo(admin_norte):
    cliente = cliente_de(admin_norte)
    assert cliente.post(f"/api/admin/usuarios/{admin_norte.id}/baja").status_code == 403
    assert cliente.post(f"/api/admin/usuarios/{admin_norte.id}/bloquear").status_code == 403
    admin_norte.refresh_from_db()
    assert admin_norte.activo and admin_norte.bloqueado_en is None


def test_hu02_reenviar_el_enlace_manda_primer_ingreso_o_restablecimiento_segun_el_caso(admin_norte, perito08):
    cliente = cliente_de(admin_norte)
    cliente.post("/api/admin/usuarios", {"nombre": "PE-22", "email": "p22@sigs.test", "rol": "perito"}, format="json")
    nuevo = Usuario.objects.get(email="p22@sigs.test")
    mail.outbox.clear()
    assert cliente.post(f"/api/admin/usuarios/{nuevo.id}/reenviar-enlace").status_code == 200
    assert "/primer-ingreso?uid=" in mail.outbox[-1].body
    assert cliente.post(f"/api/admin/usuarios/{perito08.id}/reenviar-enlace").status_code == 200
    assert "/restablecer?uid=" in mail.outbox[-1].body and mail.outbox[-1].to == [perito08.email]


def test_hu02_el_superadministrador_crea_el_espacio_con_su_administrador(superadmin):
    cliente = cliente_de(superadmin)
    respuesta = cliente.post(
        "/api/admin/espacios", {"nombre": "Estudio Oeste", "admin_nombre": "Admin Oeste", "admin_email": "admin.oeste@sigs.test"}, format="json"
    )
    assert respuesta.status_code == 201, respuesta.content
    espacio = EspacioTrabajo.objects.get(nombre="Estudio Oeste")
    admin = Usuario.objects.get(email="admin.oeste@sigs.test")
    assert admin.rol == "administrador" and admin.espacio_id == espacio.id
    assert "/primer-ingreso?uid=" in mail.outbox[-1].body and mail.outbox[-1].to == ["admin.oeste@sigs.test"]
    listado = cliente.get("/api/admin/espacios").json()["resultados"]
    assert {"id": espacio.id, "nombre": "Estudio Oeste", "cantidad_usuarios": 1}.items() <= next(e for e in listado if e["id"] == espacio.id).items()
    assert Auditoria.objects.filter(usuario=superadmin, accion="crear_espacio").exists()


def test_hu02_no_se_crea_un_espacio_repetido_ni_con_el_correo_de_otro_usuario(superadmin, norte, admin_norte):
    cliente = cliente_de(superadmin)
    assert cliente.post("/api/admin/espacios", {"nombre": norte.nombre, "admin_nombre": "X", "admin_email": "x@sigs.test"}, format="json").status_code == 400
    assert cliente.post("/api/admin/espacios", {"nombre": "Otro", "admin_nombre": "X", "admin_email": admin_norte.email}, format="json").status_code == 400
    assert not EspacioTrabajo.objects.filter(nombre="Otro").exists()


def test_hu02_el_superadministrador_puede_bloquear_y_cerrar_sesiones_de_una_cuenta_comprometida(superadmin, perito15):
    perito = APIClient()
    perito.post("/api/auth/ingresar", {"email": perito15.email, "password": CLAVE}, format="json")
    assert perito.get("/api/siniestros").status_code == 200
    assert cliente_de(superadmin).post(f"/api/admin/usuarios/{perito15.id}/bloquear").status_code == 200
    assert perito.get("/api/siniestros").status_code == 401
    assert APIClient().post("/api/auth/ingresar", {"email": perito15.email, "password": CLAVE}, format="json").status_code == 400
    registro = Auditoria.objects.get(accion="bloquear_cuenta")
    assert registro.usuario_id == superadmin.id and registro.espacio_id == perito15.espacio_id


# --- HU-15 ----------------------------------------------------------------------------
def test_hu15_el_administrador_ve_la_auditoria_de_su_espacio_con_filtros(admin_norte, perito08, perito11, perito15):
    cliente_de(perito08).get("/api/siniestros/999999")  # rechazo
    cliente_de(perito08).get("/api/siniestros")
    cliente_de(perito15).get("/api/siniestros/999999")  # del otro espacio
    cuerpo = cliente_de(admin_norte).get("/api/auditoria").json()
    assert set(cuerpo) == {"resultados", "total", "pagina", "paginas", "acciones"}
    assert all(r["usuario"]["id"] in (perito08.id, perito11.id, admin_norte.id) for r in cuerpo["resultados"] if r["usuario"])
    assert not any(r["usuario"] and r["usuario"]["id"] == perito15.id for r in cuerpo["resultados"])
    fechas = [r["fecha"] for r in cuerpo["resultados"]]
    assert fechas == sorted(fechas, reverse=True)
    assert set(cuerpo["resultados"][0]) == {"id", "fecha", "usuario", "accion", "objeto", "resultado", "siniestro_origen"}
    rechazados = cliente_de(admin_norte).get("/api/auditoria?resultado=rechazado").json()
    assert rechazados["total"] >= 1 and {r["resultado"] for r in rechazados["resultados"]} == {"rechazado"}
    por_usuario = cliente_de(admin_norte).get(f"/api/auditoria?usuario={perito08.id}").json()
    assert {r["usuario"]["id"] for r in por_usuario["resultados"]} == {perito08.id}
    por_accion = cliente_de(admin_norte).get("/api/auditoria?accion=ver_expediente").json()
    assert por_accion["total"] == 1  # solo el rechazo de PE-08: el de PE-15 es de otro espacio
    assert por_accion["resultados"][0]["resultado"] == "rechazado"
    assert "ver_expediente" in cuerpo["acciones"]


def test_hu15_la_auditoria_se_pagina_de_a_50(admin_norte, perito08):
    for _ in range(60):
        Auditoria.objects.create(usuario=perito08, espacio_id=perito08.espacio_id, accion="prueba", objeto="x", resultado="permitido")
    cliente = cliente_de(admin_norte)
    primera = cliente.get("/api/auditoria?accion=prueba").json()
    segunda = cliente.get("/api/auditoria?accion=prueba&pagina=2").json()
    assert (primera["total"], primera["paginas"], len(primera["resultados"]), len(segunda["resultados"])) == (60, 2, 50, 10)


def test_hu15_un_administrador_no_lee_registros_de_otro_espacio(admin_norte, perito15):
    cliente_de(perito15).get("/api/siniestros/999999")
    registro = Auditoria.objects.filter(usuario=perito15).latest("id")
    assert cliente_de(admin_norte).get(f"/api/auditoria/{registro.id}").status_code == 404
    propio = Auditoria.objects.filter(espacio_id=admin_norte.espacio_id).first() or Auditoria.objects.create(
        usuario=admin_norte, espacio_id=admin_norte.espacio_id, accion="x", objeto="", resultado="permitido")
    assert cliente_de(admin_norte).get(f"/api/auditoria/{propio.id}").status_code == 200


@pytest.mark.parametrize("metodo", ["put", "patch", "delete"])
def test_hu15_nadie_edita_ni_borra_un_registro_de_auditoria(admin_norte, perito08, superadmin, metodo):
    registro = Auditoria.objects.create(usuario=perito08, espacio_id=perito08.espacio_id, accion="original", objeto="o", resultado="permitido")
    for usuario in (admin_norte, perito08, superadmin):
        respuesta = getattr(cliente_de(usuario), metodo)(f"/api/auditoria/{registro.id}", {"accion": "x"}, format="json")
        assert respuesta.status_code == 403
        assert respuesta.json() == {"detalle": "Los registros de auditoría no se pueden modificar ni borrar."}
    registro.refresh_from_db()
    assert registro.accion == "original"


# --- HU-17 ----------------------------------------------------------------------------
def test_hu17_el_perfil_guarda_el_correo_de_contacto_y_la_opcion_de_mostrarlo(perito11):
    cliente = cliente_de(perito11)
    assert cliente.get("/api/perfil").json()["contacto_visible"] is False
    respuesta = cliente.patch("/api/perfil", {"contacto_email": "pe11@contacto.test", "contacto_visible": True}, format="json")
    assert respuesta.status_code == 200
    assert respuesta.json()["contacto_email"] == "pe11@contacto.test" and respuesta.json()["contacto_visible"] is True
    assert cliente.get("/api/perfil").json()["contacto_visible"] is True


def test_hu17_el_correo_habilitado_aparece_en_los_resumenes_de_mis_casos_cerrados_y_si_se_desactiva_deja_de_aparecer(perito11, perito15):
    from nucleo.fabrica import crear_siniestro

    mio = crear_siniestro(perito11, "S-MIO", bienes=["ZZ111ZZ"], estado="cerrado",
                          cierre={"resultado_reclamo": "aprobado", "valoracion": 6, "justificacion": "Dudas concretas."})
    ajeno = crear_siniestro(perito15, "S-AJENO", bienes=["ZZ111ZZ"])
    consulta = lambda: cliente_de(perito15).get(f"/api/siniestros/{ajeno.pk}/antecedentes/{mio.pk}/resumen").json()  # noqa: E731
    assert consulta()["contacto_perito"] is None
    cliente_de(perito11).patch("/api/perfil", {"contacto_email": "pe11@contacto.test", "contacto_visible": True}, format="json")
    assert consulta()["contacto_perito"] == {"email": "pe11@contacto.test"}
    cliente_de(perito11).patch("/api/perfil", {"contacto_visible": False}, format="json")
    assert consulta()["contacto_perito"] is None
    assert "pe11@contacto.test" not in str(consulta())


def test_hu17_un_cambio_en_la_opcion_de_contacto_queda_en_la_auditoria(perito11, admin_norte):
    cliente_de(perito11).patch("/api/perfil", {"contacto_email": "pe11@contacto.test", "contacto_visible": True}, format="json")
    registro = Auditoria.objects.get(accion="perfil_contacto")
    assert registro.usuario_id == perito11.id and registro.resultado == "permitido"
    assert registro.detalle["antes"]["contacto_visible"] is False and registro.detalle["despues"]["contacto_visible"] is True
    acciones = [r["accion"] for r in cliente_de(admin_norte).get("/api/auditoria").json()["resultados"]]
    assert "perfil_contacto" in acciones


def test_hu17_un_correo_de_contacto_invalido_se_rechaza(perito11):
    respuesta = cliente_de(perito11).patch("/api/perfil", {"contacto_email": "esto-no-es-un-correo"}, format="json")
    assert respuesta.status_code == 400 and "contacto_email" in respuesta.json()
    assert Usuario.objects.get(pk=perito11.pk).contacto_email == "pe11@correo.test"
