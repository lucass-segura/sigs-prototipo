"""Registro de auditoría: solo altas. Cada acción permitida y cada rechazo deja una fila."""
from .models import Auditoria, Siniestro


def _usuario_real(usuario):
    """Convierte el usuario anónimo de Django en `None`."""
    if usuario is None or not getattr(usuario, "is_authenticated", False):
        return None
    return usuario


def _resolver_siniestro(origen):
    """Acepta un Siniestro o un id; devuelve el Siniestro o `None` si no existe."""
    if origen is None or isinstance(origen, Siniestro):
        return origen
    try:
        return Siniestro.objects.filter(pk=int(origen)).first()
    except (TypeError, ValueError):
        return None


def registrar(usuario, accion, objeto="", resultado=Auditoria.PERMITIDO, siniestro_origen=None, detalle=None, espacio_id=None):
    """Crea un registro de auditoría. El espacio sale del usuario o, si no hay, del siniestro (o se indica)."""
    usuario = _usuario_real(usuario)
    siniestro = _resolver_siniestro(siniestro_origen)
    if espacio_id is None and usuario is not None:
        espacio_id = usuario.espacio_id
    if espacio_id is None and siniestro is not None:
        espacio_id = siniestro.espacio_id
    return Auditoria.objects.create(
        usuario=usuario,
        siniestro_origen=siniestro,
        accion=accion[:120],
        objeto=str(objeto)[:250],
        resultado=resultado,
        espacio_id=espacio_id,
        detalle=detalle or {},
    )


def rechazar(usuario, accion, objeto="", siniestro_origen=None, detalle=None):
    return registrar(usuario, accion, objeto, Auditoria.RECHAZADO, siniestro_origen, detalle)
