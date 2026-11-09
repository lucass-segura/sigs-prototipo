"""Conversión de modelos a los JSON del contrato de la API (docs/DISENO.md §5)."""


def usuario_json(usuario):
    espacio = usuario.espacio
    return {
        "id": usuario.id,
        "nombre": usuario.nombre,
        "email": usuario.email,
        "rol": usuario.rol,
        "espacio": {"id": espacio.id, "nombre": espacio.nombre} if espacio else None,
        "activo": usuario.activo,
        "contacto_email": usuario.contacto_email,
        "contacto_visible": usuario.contacto_visible,
    }


def usuario_admin_json(usuario):
    """Usuario para la administración: suma el estado de bloqueo."""
    datos = usuario_json(usuario)
    datos.update(
        bloqueado_en=usuario.bloqueado_en,
        intentos_fallidos=usuario.intentos_fallidos,
        creado_en=usuario.creado_en,
        tiene_contrasena=usuario.has_usable_password(),
    )
    return datos


def persona_simple(usuario):
    """`{id, nombre}` de un usuario, o `None`."""
    return {"id": usuario.id, "nombre": usuario.nombre} if usuario else None


def siniestro_json(siniestro, usuario):
    """Siniestro completo del contrato (sección 5 de DISENO). Solo se arma para el espacio del usuario.

    El nombre de las personas y la descripción y los atributos de los bienes salen de los datos del caso
    (`participacion` y `bien_afectado`), nunca de los globales de `persona` y `bien`.
    """
    from .expediente import cierre_vigente
    from .models import BienAfectado, Participacion

    personas = {}
    for p in Participacion.objects.filter(siniestro=siniestro).select_related("persona").order_by("id"):
        entrada = personas.setdefault(p.persona_id, {
            "id": p.persona_id,
            "tipo_identificador": p.persona.tipo_identificador,
            "identificador": p.persona.identificador,
            "nombre": p.nombre,
            "roles": [],
        })
        entrada["roles"].append(p.rol)
    bienes = [
        {
            "id": a.bien_id,
            "tipo": a.bien.tipo,
            "identificador_norm": a.bien.identificador_norm,
            "descripcion": a.descripcion,
            "atributos": a.atributos,
            "detalle_dano": a.detalle_dano,
        }
        for a in BienAfectado.objects.filter(siniestro=siniestro).select_related("bien").order_by("id")
    ]
    poliza = siniestro.poliza
    cierre = cierre_vigente(siniestro)
    return {
        "id": siniestro.id,
        "numero_expediente": siniestro.numero_expediente,
        "tipo": siniestro.tipo,
        "fecha_hecho": siniestro.fecha_hecho,
        "fecha_denuncia": siniestro.fecha_denuncia,
        "hora_denuncia": siniestro.hora_denuncia.strftime("%H:%M:%S") if siniestro.hora_denuncia else None,
        "numero_denuncia": siniestro.numero_denuncia,
        "asesor": siniestro.asesor,
        "intervenciones": siniestro.intervenciones,
        "documentacion_adjunta": siniestro.documentacion_adjunta,
        "lugar": siniestro.lugar,
        "relato": siniestro.relato,
        "estado": siniestro.estado,
        "confirmado_en": siniestro.confirmado_en,
        "motivo_anulacion": siniestro.motivo_anulacion,
        "espacio": {"id": siniestro.espacio_id, "nombre": siniestro.espacio.nombre},
        "perito": persona_simple(siniestro.perito),
        "es_responsable": siniestro.perito_id == usuario.id,
        "poliza": {
            "id": poliza.id,
            "numero": poliza.numero,
            "compania": poliza.compania,
            "cobertura": poliza.cobertura,
            "inicio_vigencia": poliza.inicio_vigencia,
            "primer_pago": poliza.primer_pago,
        } if poliza else None,
        "personas": list(personas.values()),
        "bienes": bienes,
        "cierre_vigente": cierre_json(cierre) if cierre else None,
    }


def cierre_json(cierre):
    """Cierre del contrato. Con su respaldo: solo se arma para el perito responsable del expediente."""
    from .coincidencias import valoracion_texto
    from .models import Documento

    documentos = {d["id"]: d for d in Documento.objects.filter(pk__in=cierre.documentos_respaldo).values("id", "tipo", "nombre_original")}

    return {
        "id": cierre.id,
        "resultado_reclamo": cierre.resultado_reclamo,
        "irregularidad": cierre.irregularidad,
        "conclusion": cierre.conclusion,
        "valoracion": cierre.valoracion,
        "valoracion_texto": valoracion_texto(cierre.valoracion),
        "justificacion": cierre.justificacion,
        "motivo_cambio": cierre.motivo_cambio,
        "documentos_respaldo": [documentos[pk] for pk in cierre.documentos_respaldo if pk in documentos],
        "observacion_respaldo": cierre.observacion_respaldo,
        "creado_en": cierre.creado_en,
        "perito": persona_simple(cierre.perito),
    }
