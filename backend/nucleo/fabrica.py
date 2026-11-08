"""Fábrica de datos para los seeds y las pruebas: arma siniestros completos sin pasar por la API."""
from django.utils import timezone

from .expediente import crear_siniestro_con_datos
from .models import Cierre, Siniestro


def crear_siniestro(
    perito,
    numero_expediente,
    *,
    tipo="Choque",
    fecha_hecho=None,
    fecha_denuncia=None,
    lugar="",
    relato="",
    poliza=None,
    personas=(),
    bienes=(),
    estado=Siniestro.EN_ANALISIS,
    confirmado_en=None,
    cierre=None,
    motivo_anulacion="",
):
    """Crea un siniestro. Si no es borrador y no se indica `confirmado_en`, se confirma en la fecha del hecho.

    - personas: `[{"tipo_identificador", "identificador", "nombre", "roles": [...]}]`
    - bienes: `[{"tipo", "identificador", "descripcion", "detalle_dano", "atributos"}]` o identificadores sueltos.
    - cierre: `{"resultado_reclamo", "irregularidad", "conclusion", "valoracion", "justificacion", "creado_en"}`.
    """
    fecha_hecho = fecha_hecho or timezone.now()
    if estado != Siniestro.BORRADOR and confirmado_en is None:
        confirmado_en = fecha_hecho
    bienes = [b if isinstance(b, dict) else {"tipo": "vehiculo", "identificador": b} for b in bienes]
    siniestro = crear_siniestro_con_datos(
        perito=perito,
        numero_expediente=numero_expediente,
        poliza=poliza,
        personas=personas,
        bienes=bienes,
        tipo=tipo,
        fecha_hecho=fecha_hecho,
        fecha_denuncia=fecha_denuncia,
        lugar=lugar,
        relato=relato,
        estado=estado,
        confirmado_en=confirmado_en,
        motivo_anulacion=motivo_anulacion,
    )
    if cierre:
        crear_cierre(siniestro, perito, **cierre)
    return siniestro


def crear_cierre(siniestro, perito, *, resultado_reclamo="aprobado", irregularidad=False, conclusion="", valoracion=7,
                 justificacion="Justificación de prueba.", creado_en=None, motivo_cambio=""):
    datos = dict(
        siniestro=siniestro, perito=perito, resultado_reclamo=resultado_reclamo, irregularidad=irregularidad,
        conclusion=conclusion, valoracion=valoracion, justificacion=justificacion, motivo_cambio=motivo_cambio,
    )
    if creado_en is not None:
        datos["creado_en"] = creado_en
    return Cierre.objects.create(**datos)
