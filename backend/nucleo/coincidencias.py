"""Búsqueda de coincidencias: antecedentes válidos que comparten una persona o un bien con un siniestro.

El grafo es simple y va a dos saltos: siniestro → persona o bien → otro siniestro. Se apoya en los
índices de `participacion(persona_id)`, `bien_afectado(bien_id)` y `siniestro(estado, confirmado_en)`.
"""
import math

from .expediente import cierres_vigentes
from .models import BienAfectado, Participacion, Siniestro

TAMANIO_PAGINA = 20
MENSAJE_VACIO = "No hay antecedentes accesibles en la red"
SIN_NOMBRE = "Persona sin nombre"
ESCALA_VALORACION = [
    (2, "No verificado, con elementos que lo contradicen"),
    (4, "Inconsistencias relevantes"),
    (6, "Dudas concretas"),
    (8, "Verificado con observaciones menores"),
    (10, "Verificado sin observaciones"),
]


def valoracion_texto(valoracion):
    """Texto de la escala de valoración (tabla 2 del TFG)."""
    for tope, texto in ESCALA_VALORACION:
        if valoracion <= tope:
            return texto
    return ESCALA_VALORACION[-1][1]


def unir(textos):
    """`['a', 'b', 'c']` → `a, b y c` (sin repetir)."""
    textos = list(dict.fromkeys(textos))
    if len(textos) <= 1:
        return "".join(textos)
    return ", ".join(textos[:-1]) + " y " + textos[-1]


def _ids_de_siniestros_vinculados(siniestro, persona_ids, bien_ids):
    ids = set()
    if persona_ids:
        ids.update(
            Participacion.objects.filter(persona_id__in=persona_ids).exclude(siniestro_id=siniestro.pk)
            .values_list("siniestro_id", flat=True)
        )
    if bien_ids:
        ids.update(
            BienAfectado.objects.filter(bien_id__in=bien_ids).exclude(siniestro_id=siniestro.pk)
            .values_list("siniestro_id", flat=True)
        )
    return ids


def datos_del_caso(siniestro):
    """Personas (con sus roles) y bienes del siniestro.

    `nombre` es el que el perito declaró en este caso (`participacion.nombre`); si lo dejó vacío, un texto
    neutro. Nunca se usa `Persona.nombre`, que es global.
    """
    personas = {}
    for p in Participacion.objects.filter(siniestro=siniestro).select_related("persona").order_by("id"):
        entrada = personas.setdefault(p.persona_id, {"persona": p.persona, "roles": [], "nombre": SIN_NOMBRE})
        if entrada["nombre"] == SIN_NOMBRE and p.nombre.strip():
            entrada["nombre"] = p.nombre.strip()
        entrada["roles"].append(p.rol)
    bienes = [a.bien for a in BienAfectado.objects.filter(siniestro=siniestro).select_related("bien").order_by("id")]
    return personas, bienes


def buscar_antecedentes(siniestro):
    """Antecedentes válidos del siniestro, ordenados por id.

    Antecedente válido: otro siniestro, de cualquier espacio, con `confirmado_en` y estado en análisis,
    cerrado o archivado. Los anulados y los borradores nunca cuentan.

    Devuelve `[{"siniestro", "personas": {persona_id: {"persona", "roles", "nombre"}}, "bienes": [Bien]}]`
    con solo las personas y los bienes compartidos. El `nombre` de cada persona es el de `siniestro` (el
    caso que consulta), no el que escribió el perito del antecedente, que puede ser de otro espacio.
    """
    personas_caso, bienes_caso = datos_del_caso(siniestro)
    ids = _ids_de_siniestros_vinculados(siniestro, set(personas_caso), {b.pk for b in bienes_caso})
    if not ids:
        return []
    candidatos = list(
        Siniestro.objects.filter(
            id__in=ids, confirmado_en__isnull=False, estado__in=Siniestro.ESTADOS_VALIDOS_COMO_ANTECEDENTE
        ).select_related("perito").order_by("id")
    )
    ids_validos = [s.pk for s in candidatos]
    personas = {s.pk: {} for s in candidatos}
    for p in Participacion.objects.filter(siniestro_id__in=ids_validos, persona_id__in=list(personas_caso)).select_related("persona").order_by("id"):
        entrada = personas[p.siniestro_id].setdefault(
            p.persona_id, {"persona": p.persona, "roles": [], "nombre": personas_caso[p.persona_id]["nombre"]}
        )
        entrada["roles"].append(p.rol)
    bienes = {s.pk: [] for s in candidatos}
    for a in BienAfectado.objects.filter(siniestro_id__in=ids_validos, bien_id__in=[b.pk for b in bienes_caso]).select_related("bien").order_by("id"):
        bienes[a.siniestro_id].append(a.bien)
    return [{"siniestro": s, "personas": personas[s.pk], "bienes": bienes[s.pk]} for s in candidatos]


def casos_en_analisis_vinculados(siniestro):
    """Otros siniestros `en_analisis` (de cualquier espacio) que comparten una persona o un bien con `siniestro`."""
    personas_caso, bienes_caso = datos_del_caso(siniestro)
    ids = _ids_de_siniestros_vinculados(siniestro, set(personas_caso), {b.pk for b in bienes_caso})
    return list(
        Siniestro.objects.filter(id__in=ids, estado=Siniestro.EN_ANALISIS, confirmado_en__isnull=False).order_by("id")
    )


def _roles_texto(roles):
    return unir(roles)


def vinculos_de_coincidencia(siniestro, antecedente, roles_caso):
    """Vínculos de un antecedente con el caso: `[{tipo, etiqueta, rol_en_antecedente, rol_en_caso}]`."""
    vinculos = []
    for persona_id, datos in antecedente["personas"].items():
        vinculos.append({
            "tipo": "persona",
            "etiqueta": datos["nombre"],
            "rol_en_antecedente": _roles_texto(datos["roles"]),
            "rol_en_caso": _roles_texto(roles_caso.get(persona_id, [])),
        })
    for bien in antecedente["bienes"]:
        vinculos.append({
            "tipo": "bien",
            "etiqueta": bien.identificador_norm,
            "rol_en_antecedente": "Bien afectado",
            "rol_en_caso": "Bien afectado",
        })
    return vinculos


def descripcion_vinculo(antecedente):
    """Frase corta del vínculo, como en la maqueta: «Mismo vehículo AB123CD»."""
    frases = []
    for bien in antecedente["bienes"]:
        frases.append(f"Mismo {_sustantivo_bien(bien.tipo)} {bien.identificador_norm}")
    for datos in antecedente["personas"].values():
        frases.append(f"{datos['nombre']} figura como {_roles_texto(datos['roles'])}")
    return " · ".join(frases)


def _sustantivo_bien(tipo):
    return {"vehiculo": "vehículo", "motocicleta": "motocicleta", "telefono": "teléfono", "computadora": "equipo"}.get(tipo, "bien")


def promedio_valoracion(antecedentes):
    """Promedio y cantidad de casos con valoración entre los antecedentes vinculados. Se calcula al vuelo."""
    cierres = cierres_vigentes([a["siniestro"].pk for a in antecedentes if a["siniestro"].estado in (Siniestro.CERRADO, Siniestro.ARCHIVADO)])
    valores = [c.valoracion for c in cierres.values()]
    if not valores:
        return {"promedio": None, "cantidad": 0}
    return {"promedio": round(sum(valores) / len(valores), 1), "cantidad": len(valores)}


def resultados_de_coincidencias(siniestro, pagina=1):
    """Cuerpo de `GET /siniestros/<id>/coincidencias`."""
    antecedentes = buscar_antecedentes(siniestro)
    antecedentes.sort(key=lambda a: (a["siniestro"].fecha_hecho, a["siniestro"].pk), reverse=True)
    personas_caso, _ = datos_del_caso(siniestro)
    roles_caso = {pk: datos["roles"] for pk, datos in personas_caso.items()}
    total = len(antecedentes)
    paginas = max(1, math.ceil(total / TAMANIO_PAGINA))
    pagina = min(max(1, pagina), paginas)
    visibles = antecedentes[(pagina - 1) * TAMANIO_PAGINA: pagina * TAMANIO_PAGINA]
    cierres = cierres_vigentes([a["siniestro"].pk for a in visibles])
    resultados = []
    for a in visibles:
        s = a["siniestro"]
        cierre = cierres.get(s.pk) if s.estado in (Siniestro.CERRADO, Siniestro.ARCHIVADO) else None
        resultados.append({
            "antecedente_id": s.pk,
            "numero_expediente": s.numero_expediente,
            "tipo": s.tipo,
            "fecha_hecho": s.fecha_hecho,
            "estado": s.estado,
            "resultado_reclamo": cierre.resultado_reclamo if cierre else None,
            "vinculos": vinculos_de_coincidencia(siniestro, a, roles_caso),
            "descripcion_vinculo": descripcion_vinculo(a),
        })
    return {
        "resultados": resultados,
        "total": total,
        "pagina": pagina,
        "paginas": paginas,
        "promedio_valoracion": promedio_valoracion(antecedentes),
        "mensaje_vacio": MENSAJE_VACIO if total == 0 else None,
    }
