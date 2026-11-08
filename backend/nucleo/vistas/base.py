"""Vistas auxiliares: salud, CSRF fallido y rutas inexistentes bajo /api/."""
from django.http import HttpResponseNotFound, JsonResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import auditoria


class Salud(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, solicitud):
        return Response({"estado": "ok"})


def csrf_fallido(solicitud, reason=""):
    """Respuesta JSON cuando falla la verificación CSRF de Django. Queda auditada."""
    auditoria.rechazar(getattr(solicitud, "user", None), "csrf_fallido", solicitud.path, detalle={"estado": 403})
    return JsonResponse({"detalle": "Falta o no es válido el token CSRF."}, status=403)


def no_encontrado(solicitud, exception=None):
    """handler404: las rutas inexistentes bajo /api/ responden JSON y se auditan."""
    if solicitud.path.startswith("/api/"):
        auditoria.rechazar(
            getattr(solicitud, "user", None), f"{solicitud.method} {solicitud.path}", solicitud.path, detalle={"estado": 404}
        )
        return JsonResponse({"detalle": "No se encontró lo que pedís."}, status=404)
    return HttpResponseNotFound("No encontrado")
