"""Resumen minimizado de un antecedente (HU-11). Se arma al momento y no se guarda."""
from .coincidencias import buscar_antecedentes, datos_del_caso, valoracion_texto
from .expediente import cierre_vigente, fecha_local
from .models import Siniestro

NO_SE_MUESTRA = (
    "Fotografías, documentos, notas privadas, DNI, teléfono, relato, detalle del daño y datos de contacto "
    "del asegurado y de los terceros quedan en el expediente de origen."
)
ESTADO_TEXTO = {Siniestro.EN_ANALISIS: "En análisis", Siniestro.CERRADO: "Cerrado", Siniestro.ARCHIVADO: "Archivado"}


def construir_resumen(origen, antecedente_id):
    """Resumen del antecedente o `None` si no está entre las coincidencias válidas del origen.

    Nunca incluye documentos, notas, DNI, teléfono, relato ni detalle del daño. Las personas se
    identifican con el nombre que el perito ya conoce de su caso (el del origen, nunca el que escribió otro
    espacio), no con su identificador.
    """
    coincidencia = next((a for a in buscar_antecedentes(origen) if a["siniestro"].pk == antecedente_id), None)
    if coincidencia is None:
        return None
    antecedente = coincidencia["siniestro"]
    personas_caso, _ = datos_del_caso(origen)
    vinculos = [
        {"tipo": "persona", "etiqueta": datos["nombre"], "rol_en_antecedente": ", ".join(datos["roles"])}
        for datos in coincidencia["personas"].values()
    ] + [
        {"tipo": "bien", "etiqueta": bien.identificador_norm, "rol_en_antecedente": "Bien afectado"}
        for bien in coincidencia["bienes"]
    ]
    cierre = cierre_vigente(antecedente) if antecedente.estado in (Siniestro.CERRADO, Siniestro.ARCHIVADO) else None
    perito = antecedente.perito
    # el correo de contacto aparece en los resúmenes de los casos cerrados o archivados (HU-17, criterio 1)
    cerrado_o_archivado = antecedente.estado in (Siniestro.CERRADO, Siniestro.ARCHIVADO)
    contacto = {"email": perito.contacto_email} if cerrado_o_archivado and perito.contacto_visible and perito.contacto_email else None
    return {
        "numero_expediente": antecedente.numero_expediente,
        "tipo": antecedente.tipo,
        "fecha_hecho": fecha_local(antecedente.fecha_hecho).isoformat(),
        "estado": antecedente.estado,
        "estado_texto": ESTADO_TEXTO.get(antecedente.estado, "En análisis") if cierre else "En análisis",
        "vinculos": vinculos,
        "cerrado": cierre is not None,
        "resultado_reclamo": cierre.resultado_reclamo if cierre else None,
        "irregularidad": cierre.irregularidad if cierre else None,
        "valoracion": cierre.valoracion if cierre else None,
        "valoracion_texto": valoracion_texto(cierre.valoracion) if cierre else None,
        "justificacion": cierre.justificacion if cierre else None,
        "perito_responsable": {"nombre": perito.nombre},
        "contacto_perito": contacto,
        "origen": {"id": origen.pk, "numero_expediente": origen.numero_expediente},
        "no_se_muestra": NO_SE_MUESTRA,
    }
