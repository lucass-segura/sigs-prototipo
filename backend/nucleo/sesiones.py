"""Cierre de sesiones de un usuario (baja, bloqueo y cambio de contraseña)."""
from django.contrib.sessions.models import Session
from django.utils import timezone


def cerrar_sesiones(usuario):
    """Borra todas las sesiones activas del usuario. Devuelve cuántas cerró."""
    cantidad = 0
    for sesion in Session.objects.filter(expire_date__gte=timezone.now()):
        if str(sesion.get_decoded().get("_auth_user_id")) == str(usuario.pk):
            sesion.delete()
            cantidad += 1
    return cantidad
