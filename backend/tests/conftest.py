"""Fixtures comunes: espacios, usuarios y clientes autenticados por la API."""
import re

import pytest
from rest_framework.test import APIClient

from nucleo.models import EspacioTrabajo, Usuario

CLAVE = "Clave.Segura#2026"


def crear_usuario(rol, espacio, email, nombre, **extra):
    return Usuario.objects.create_user(email=email, nombre=nombre, rol=rol, espacio=espacio, password=CLAVE, **extra)


@pytest.fixture(autouse=True)
def documentos_temporales(settings, tmp_path):
    """Los documentos de las pruebas van a una carpeta temporal."""
    settings.DOCUMENTOS_DIR = str(tmp_path / "documentos")


@pytest.fixture
def norte(db):
    return EspacioTrabajo.objects.create(nombre="Estudio Pericial Norte")


@pytest.fixture
def sur(db):
    return EspacioTrabajo.objects.create(nombre="Perito Independiente Sur")


@pytest.fixture
def superadmin(db):
    return crear_usuario("superadministrador", None, "superadmin@sigs.test", "Superadministrador")


@pytest.fixture
def admin_norte(norte):
    return crear_usuario("administrador", norte, "admin.norte@sigs.test", "Admin Norte")


@pytest.fixture
def admin_sur(sur):
    return crear_usuario("administrador", sur, "admin.sur@sigs.test", "Admin Sur")


@pytest.fixture
def perito08(norte):
    return crear_usuario("perito", norte, "perito08@sigs.test", "PE-08", contacto_email="pe08@correo.test", contacto_visible=True)


@pytest.fixture
def perito11(norte):
    return crear_usuario("perito", norte, "perito11@sigs.test", "PE-11", contacto_email="pe11@correo.test", contacto_visible=False)


@pytest.fixture
def perito15(sur):
    return crear_usuario("perito", sur, "perito15@sigs.test", "PE-15", contacto_email="pe15@correo.test", contacto_visible=True)


@pytest.fixture
def anonimo():
    return APIClient()


def cliente_de(usuario):
    cliente = APIClient()
    cliente.force_login(usuario)
    return cliente


@pytest.fixture
def como():
    """`como(usuario)` devuelve un cliente de API con la sesión de ese usuario."""
    return cliente_de


def enlace_del_correo(mensaje):
    """Extrae `(uid, token)` del enlace que trae un correo."""
    encontrado = re.search(r"uid=([^&\s]+)&token=([^&\s]+)", mensaje.body)
    assert encontrado, f"El correo no trae un enlace con uid y token: {mensaje.body}"
    return encontrado.group(1), encontrado.group(2)


def cuerpo_siniestro(**cambios):
    """Cuerpo válido de `POST /api/siniestros` (el caso EXP-2026-0147 de la demo)."""
    cuerpo = {
        "poliza": {
            "numero": "AUT-000123",
            "compania": "Aseguradora Ejemplo S. A.",
            "cobertura": "Todo riesgo",
            "inicio_vigencia": "2026-07-20",
            "primer_pago": "2026-08-04",
        },
        "tipo": "Incendio total",
        "fecha_hecho": "2026-08-12T23:40:00",
        "fecha_denuncia": "2026-08-14",
        "lugar": "Vía pública, Neuquén",
        "relato": "Relato ficticio del hecho.",
        "personas": [{"tipo_identificador": "DNI", "identificador": "30.111.017", "nombre": "P-17", "roles": ["asegurado", "conductor"]}],
        "bienes": [
            {
                "tipo": "vehiculo",
                "identificador": "AB-123 CD",
                "descripcion": "Auto ficticio",
                "detalle_dano": "Incendio total",
                "atributos": {"motor": "M123", "chasis": "C456"},
            }
        ],
    }
    cuerpo.update(cambios)
    return cuerpo
