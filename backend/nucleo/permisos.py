"""Permisos por objeto y manejo de rechazos.

Todo rechazo (401, 403, 404 y 405) queda en la auditoría con `resultado = rechazado`.
"""
from django.core.exceptions import PermissionDenied as PermisoDenegadoDjango
from django.http import Http404
from rest_framework import exceptions

from . import auditoria
from .models import Siniestro, Usuario

ESTADOS_AUDITADOS = (401, 403, 404, 405)


class Rechazo(exceptions.APIException):
    """Rechazo con los datos que se guardan en la auditoría."""

    status_code = 403

    def __init__(self, mensaje, estado=403, accion=None, objeto="", siniestro_origen=None):
        super().__init__(detail=mensaje)
        self.status_code = estado
        self.accion = accion
        self.objeto = objeto
        self.siniestro_origen = siniestro_origen


def prohibido(mensaje, accion=None, objeto="", siniestro_origen=None):
    return Rechazo(mensaje, 403, accion, objeto, siniestro_origen)


def no_encontrado(mensaje="No se encontró lo que pedís.", accion=None, objeto="", siniestro_origen=None):
    return Rechazo(mensaje, 404, accion, objeto, siniestro_origen)


MENSAJES_POR_DEFECTO = (
    (exceptions.NotAuthenticated, "Hace falta iniciar sesión."),
    (exceptions.AuthenticationFailed, "Hace falta iniciar sesión."),
    (exceptions.PermissionDenied, "No tenés permiso para realizar esta acción."),
    (exceptions.NotFound, "No se encontró lo que pedís."),
    (exceptions.MethodNotAllowed, "Método no permitido."),
    (exceptions.ParseError, "El cuerpo de la solicitud no es válido."),
    (exceptions.UnsupportedMediaType, "Tipo de contenido no admitido."),
)


def manejar_excepcion(exc, contexto):
    """EXCEPTION_HANDLER de DRF: unifica el formato y audita los rechazos."""
    from rest_framework.views import exception_handler  # import tardío: evita un ciclo con la autenticación

    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermisoDenegadoDjango):
        exc = exceptions.PermissionDenied()
    respuesta = exception_handler(exc, contexto)
    if respuesta is None:
        return None

    solicitud = contexto.get("request")
    if respuesta.status_code in ESTADOS_AUDITADOS and solicitud is not None:
        if isinstance(exc, Rechazo):
            accion, objeto, origen = exc.accion, exc.objeto, exc.siniestro_origen
        else:
            accion = objeto = origen = None
        auditoria.rechazar(
            solicitud.user,
            accion or f"{solicitud.method} {solicitud.path}",
            objeto or solicitud.path,
            origen,
            {"estado": respuesta.status_code},
        )

    datos = respuesta.data
    if isinstance(datos, dict) and isinstance(datos.get("detalle"), list):
        datos = respuesta.data = {**datos, "detalle": " ".join(str(d) for d in datos["detalle"])}
    if isinstance(datos, dict) and "detail" in datos:
        mensaje = str(datos["detail"])
        if not isinstance(exc, (Rechazo, exceptions.AuthenticationFailed)):
            for clase, texto in MENSAJES_POR_DEFECTO:
                if isinstance(exc, clase):
                    mensaje = texto
                    break
        respuesta.data = {"detalle": mensaje}
    elif isinstance(datos, list):
        respuesta.data = {"detalle": " ".join(str(d) for d in datos)}
    return respuesta


# --------------------------------------------------------------------------
# Autorización por objeto
# --------------------------------------------------------------------------
def exigir_rol(solicitud, roles, mensaje, accion):
    """Exige que el usuario tenga alguno de los roles."""
    if solicitud.user.rol not in roles:
        raise prohibido(mensaje, accion, solicitud.path)
    return solicitud.user


def exigir_perito(solicitud, accion):
    return exigir_rol(solicitud, (Usuario.PERITO,), "Solo un perito puede acceder a los expedientes.", accion)


def siniestro_asignado(solicitud, pk, accion):
    """Devuelve el siniestro pedido solo si el usuario es el perito asignado (`perito_id`).

    Cualquier otro caso (otro espacio, otro perito del mismo espacio o un id inexistente) responde igual:
    404 sin dar pistas de que el expediente existe. Queda auditado como rechazo.
    """
    usuario = exigir_perito(solicitud, accion)
    siniestro = Siniestro.objects.select_related("espacio", "perito", "poliza").filter(pk=pk).first()
    if siniestro is None or siniestro.perito_id != usuario.id:
        raise no_encontrado("No se encontró el expediente.", accion, f"siniestro:{pk}")
    return siniestro


def exigir_confirmado(solicitud, siniestro, accion):
    """Solo un siniestro confirmado (en análisis, cerrado o archivado) se analiza."""
    if siniestro.confirmado_en is None or siniestro.estado not in Siniestro.ESTADOS_VALIDOS_COMO_ANTECEDENTE:
        raise prohibido("Solo un siniestro confirmado se analiza.", accion, f"siniestro:{siniestro.pk}", siniestro.pk)
