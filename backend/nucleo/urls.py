"""Rutas de la API (todas bajo /api)."""
from django.urls import path, re_path

from .vistas import admin, auth, base, cierre, expediente, personas, reglas, siniestros

urlpatterns = [
    path("health", base.Salud.as_view()),
    # Autenticación y perfil
    path("auth/sesion", auth.Sesion.as_view()),
    path("auth/ingresar", auth.Ingresar.as_view()),
    path("auth/salir", auth.Salir.as_view()),
    path("auth/restablecer", auth.Restablecer.as_view()),
    path("auth/enlace", auth.Enlace.as_view()),
    path("auth/definir-contrasena", auth.DefinirContrasena.as_view()),
    path("perfil", auth.Perfil.as_view()),
    # Expedientes
    path("siniestros", siniestros.Siniestros.as_view()),
    path("siniestros/<int:pk>", siniestros.DetalleSiniestro.as_view()),
    path("siniestros/<int:pk>/confirmar", siniestros.Confirmar.as_view()),
    path("siniestros/<int:pk>/evaluacion", siniestros.UltimaEvaluacion.as_view()),
    path("siniestros/<int:pk>/evaluaciones", siniestros.Evaluaciones.as_view()),
    path("siniestros/<int:pk>/recalcular", siniestros.Recalcular.as_view()),
    path("siniestros/<int:pk>/coincidencias", siniestros.Coincidencias.as_view()),
    path("siniestros/<int:pk>/antecedentes/<int:antecedente_pk>/resumen", siniestros.ResumenAntecedente.as_view()),
    path("siniestros/<int:pk>/documentos", expediente.Documentos.as_view()),
    path("siniestros/<int:pk>/croquis", expediente.GuardarCroquis.as_view()),
    path("siniestros/<int:pk>/notas", expediente.Notas.as_view()),
    path("siniestros/<int:pk>/tareas", expediente.Tareas.as_view()),
    path("siniestros/<int:pk>/cierre", cierre.CierreDelSiniestro.as_view()),
    path("siniestros/<int:pk>/archivar", cierre.Archivar.as_view()),
    path("siniestros/<int:pk>/anular", cierre.Anular.as_view()),
    path("documentos/<int:pk>/descargar", expediente.DescargarDocumento.as_view()),
    path("documentos/<int:pk>/ver", expediente.VerDocumento.as_view()),
    path("documentos/<int:pk>/escena", expediente.EscenaDocumento.as_view()),
    path("tareas", expediente.MisTareas.as_view()),
    path("tareas/<int:pk>", expediente.DetalleTarea.as_view()),
    # Reglas
    path("reglas", reglas.Reglas.as_view()),
    path("reglas/versiones", reglas.PublicarVersion.as_view()),
    path("reglas/versiones/<int:pk>", reglas.DetalleVersion.as_view()),
    # Administración
    path("admin/usuarios", admin.Usuarios.as_view()),
    path("admin/usuarios/<int:pk>/baja", admin.BajaUsuario.as_view()),
    path("admin/usuarios/<int:pk>/bloquear", admin.BloquearUsuario.as_view()),
    path("admin/usuarios/<int:pk>/reenviar-enlace", admin.ReenviarEnlace.as_view()),
    path("admin/espacios", admin.Espacios.as_view()),
    path("auditoria", admin.ListaAuditoria.as_view()),
    path("auditoria/<int:pk>", admin.DetalleAuditoria.as_view()),
    # No hay buscador de personas
    re_path(r"^personas(/.*)?$", personas.PersonasNoDisponible.as_view()),
]
