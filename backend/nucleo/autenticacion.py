"""Autenticación por sesión de Django con CSRF obligatorio."""
from rest_framework.authentication import CSRFCheck, SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed

from .permisos import Rechazo


class SesionAutenticacion(SessionAuthentication):
    """Sesión + CSRF. Rechaza sesiones de usuarios dados de baja o bloqueados.

    A diferencia de la clase base, también exige CSRF a los usuarios anónimos en los
    métodos que modifican datos, para evitar el *login CSRF*.
    """

    def authenticate_header(self, request):
        # Hace que DRF responda 401 (y no 403) cuando falta la sesión.
        return "Session"

    def enforce_csrf(self, request):
        verificacion = CSRFCheck(lambda solicitud: None)
        verificacion.process_request(request)
        motivo = verificacion.process_view(request, None, (), {})
        if motivo:
            raise Rechazo("Falta o no es válido el token CSRF.", estado=403, accion="csrf_fallido", objeto=request.path)

    def authenticate(self, request):
        usuario = getattr(request._request, "user", None)
        if usuario is None or not usuario.is_authenticated:
            self.enforce_csrf(request)
            return None
        if not usuario.activo or usuario.bloqueado_en is not None:
            raise AuthenticationFailed("Tu sesión ya no es válida. Volvé a ingresar.")
        self.enforce_csrf(request)
        return (usuario, None)


class SesionTolerante(SessionAuthentication):
    """Lee la sesión sin fallar: una cuenta inactiva o bloqueada se toma como anónima (nunca 401)."""

    def authenticate(self, request):
        usuario = getattr(request._request, "user", None)
        if usuario is None or not usuario.is_authenticated or not usuario.activo or usuario.bloqueado_en is not None:
            return None
        return (usuario, None)
