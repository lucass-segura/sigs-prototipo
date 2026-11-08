"""Correos del sistema: primer ingreso, restablecimiento y aviso de bloqueo.

En local salen por Mailpit (http://localhost:8025). Un fallo del servidor de correo
se registra en el log y no rompe la solicitud.
"""
import logging

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

registro = logging.getLogger(__name__)


def generar_enlace(usuario, ruta):
    """`APP_URL/<ruta>?uid=…&token=…`. El token es de un solo uso y vence a la hora."""
    uid = urlsafe_base64_encode(force_bytes(usuario.pk))
    token = default_token_generator.make_token(usuario)
    return f"{settings.APP_URL}/{ruta}?uid={uid}&token={token}"


def _enviar(usuario, asunto, cuerpo):
    try:
        send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [usuario.email], fail_silently=False)
        return True
    except Exception:  # noqa: BLE001 - el correo no puede romper el flujo del usuario
        registro.exception("No se pudo enviar el correo a %s", usuario.email)
        return False


def enviar_primer_ingreso(usuario):
    enlace = generar_enlace(usuario, "primer-ingreso")
    return _enviar(
        usuario,
        "Bienvenido a SIGS: definí tu contraseña",
        f"Hola {usuario.nombre},\n\nTe dieron de alta en SIGS. Definí tu contraseña con este enlace:\n\n{enlace}\n\n"
        "El enlace sirve una sola vez y vence en 1 hora.\n\nPrototipo académico. Datos ficticios.",
    )


def enviar_restablecimiento(usuario):
    enlace = generar_enlace(usuario, "restablecer")
    return _enviar(
        usuario,
        "SIGS: restablecé tu contraseña",
        f"Hola {usuario.nombre},\n\nRecibimos un pedido para restablecer tu contraseña. Usá este enlace:\n\n{enlace}\n\n"
        "El enlace sirve una sola vez y vence en 1 hora. Si no lo pediste vos, ignorá este correo.\n\n"
        "Prototipo académico. Datos ficticios.",
    )


def enviar_bloqueo(usuario):
    enlace = generar_enlace(usuario, "restablecer")
    return _enviar(
        usuario,
        "SIGS: tu cuenta fue bloqueada",
        f"Hola {usuario.nombre},\n\nTu cuenta quedó bloqueada por 5 intentos fallidos de ingreso. "
        f"Para habilitarla restablecé tu contraseña con este enlace:\n\n{enlace}\n\n"
        "El enlace sirve una sola vez y vence en 1 hora. Si no fuiste vos, avisá al administrador de tu espacio.\n\n"
        "Prototipo académico. Datos ficticios.",
    )
