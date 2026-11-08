"""No existe un buscador de personas: toda variante de /api/personas se rechaza y se audita (A5)."""
from rest_framework.views import APIView

from ..permisos import prohibido

MENSAJE = "La búsqueda de personas solo se hace desde un expediente confirmado."


class PersonasNoDisponible(APIView):
    """Responde 403 a cualquier método y ruta bajo /api/personas."""

    def _rechazar(self, solicitud, *args, **kwargs):
        raise prohibido(MENSAJE, "buscar_personas", solicitud.path)

    get = post = put = patch = delete = options = head = _rechazar
