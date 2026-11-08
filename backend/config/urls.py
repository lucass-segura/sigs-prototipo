"""URLs del prototipo SIGS: toda la API vive bajo /api."""
from django.urls import include, path

urlpatterns = [path("api/", include("nucleo.urls"))]

handler404 = "nucleo.vistas.base.no_encontrado"
