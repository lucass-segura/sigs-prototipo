"""Conjuntos de reglas: textos de umbral, validación de parámetros y publicación de versiones (HU-12)."""
import copy

from django.db import transaction

from .models import ConjuntoReglas, Regla


def umbral_texto(codigo, p):
    """Texto de la columna «Umbral y puntos» (pantalla de reglas), calculado desde los parámetros."""
    if codigo == "R01":
        niveles = sorted(p["niveles"], key=lambda n: n["max_dias"])
        partes, anterior = [], None
        for n in niveles:
            partes.append(f"≤ {n['max_dias']} días: {n['puntos']}" if anterior is None else f"{anterior + 1} a {n['max_dias']}: {n['puntos']}")
            anterior = n["max_dias"]
        return " · ".join(partes)
    if codigo == "R02":
        return f"≤ {p['max_dias']} días: {p['puntos']}"
    if codigo == "R03":
        niveles = sorted(p["niveles"], key=lambda n: -n["min_antecedentes"])
        partes = [
            f"{n['min_antecedentes']} o más en {p['ventana_meses']} meses: {n['puntos']}" if i == 0 else f"{n['min_antecedentes']}: {n['puntos']}"
            for i, n in enumerate(niveles)
        ]
        return " · ".join(partes)
    if codigo == "R04":
        return f"{p['max_dias']} días: {p['puntos']}"
    if codigo in ("R05", "R06"):
        return f"{p['ventana_meses']} meses: {p['puntos']}"
    if codigo == "R07":
        return f"Confirmada: {p['puntos']}"
    if codigo == "R08":
        return f"> {p['plazo_dias']} días: {p['puntos']}"
    return ""


def conjunto_json(conjunto):
    return {
        "id": conjunto.pk,
        "version": conjunto.version,
        "vigente_desde": conjunto.vigente_desde,
        "activo": conjunto.activo,
        "topes": conjunto.topes,
        "reglas": [
            {
                "codigo": r.codigo, "nombre": r.nombre, "grupo": r.grupo, "parametros": r.parametros,
                "puntos_max": r.puntos_max, "umbral_texto": umbral_texto(r.codigo, r.parametros),
            }
            for r in conjunto.reglas.order_by("codigo")
        ],
    }


def resumen_de_version(conjunto):
    return {"id": conjunto.pk, "version": conjunto.version, "vigente_desde": conjunto.vigente_desde,
            "activo": conjunto.activo, "creado_en": conjunto.creado_en}


# --------------------------------------------------------------------------
# Validación
# --------------------------------------------------------------------------
def _entero(valor):
    return isinstance(valor, int) and not isinstance(valor, bool) and valor >= 0


def _faltan(p, campos):
    return [c for c in campos if c not in p or not _entero(p[c])]


ESQUEMAS = {
    "R01": ("niveles", (), ("max_dias", "puntos")),
    "R02": (None, ("max_dias", "puntos")),
    "R03": ("niveles", ("ventana_meses",), ("min_antecedentes", "puntos")),
    "R04": (None, ("max_dias", "puntos")),
    "R05": (None, ("ventana_meses", "puntos")),
    "R06": (None, ("ventana_meses", "puntos")),
    "R07": (None, ("puntos",)),
    "R08": (None, ("plazo_dias", "puntos")),
}


def validar_parametros(codigo, p):
    """Lista de mensajes de error (vacía si los parámetros están completos y son enteros no negativos)."""
    if not isinstance(p, dict):
        return [f"Los parámetros de {codigo} tienen que ser un objeto."]
    esquema = ESQUEMAS[codigo]
    lista, campos = esquema[0], esquema[1]
    errores = [f"Falta el parámetro «{c}» de {codigo} o no es un entero no negativo." for c in _faltan(p, campos)]
    if lista:
        niveles = p.get(lista)
        campos_nivel = esquema[2] if len(esquema) > 2 else esquema[1]
        if not isinstance(niveles, list) or not niveles:
            errores.append(f"Los niveles de {codigo} tienen que ser una lista con al menos un nivel.")
        else:
            for nivel in niveles:
                if not isinstance(nivel, dict) or _faltan(nivel, campos_nivel):
                    errores.append(f"Cada nivel de {codigo} necesita {', '.join(campos_nivel)} como enteros no negativos.")
                    break
    return errores


def puntos_de_la_regla(p):
    """Todos los puntos que puede otorgar una regla según sus parámetros (uno por nivel o el propio)."""
    if isinstance(p.get("niveles"), list):
        return [n["puntos"] for n in p["niveles"]]
    return [p["puntos"]]


def validar_puntos_maximos(codigo, parametros, puntos_max):
    """Mensajes de error si algún nivel otorga más puntos que `puntos_max` (parámetros ya validados)."""
    mayor = max(puntos_de_la_regla(parametros))
    if mayor > puntos_max:
        return [f"Los puntos de {codigo} ({mayor}) no pueden superar sus puntos máximos ({puntos_max})."]
    return []


def validar_topes(topes, grupos_vigentes):
    errores = []
    if not isinstance(topes, dict):
        return ["Los topes tienen que ser un objeto."]
    grupos = topes.get("grupos")
    if not isinstance(grupos, dict) or set(grupos) != set(grupos_vigentes) or not all(_entero(v) for v in grupos.values()):
        errores.append("Los topes por grupo tienen que incluir " + ", ".join(grupos_vigentes) + " con enteros no negativos.")
    if not _entero(topes.get("total")) or topes.get("total") == 0:
        errores.append("El tope total tiene que ser un entero positivo.")
    prioridad = topes.get("prioridad")
    if not isinstance(prioridad, dict) or not _entero(prioridad.get("media")) or not _entero(prioridad.get("alta")) \
            or prioridad["media"] >= prioridad["alta"]:
        errores.append("Los umbrales de prioridad tienen que ser enteros con «media» menor que «alta».")
    return errores


@transaction.atomic
def publicar_version(vigente, version, vigente_desde, cambios_reglas, topes, usuario):
    """Copia la versión vigente, aplica los cambios y la deja activa. La anterior queda guardada y sin edición."""
    ConjuntoReglas.objects.filter(activo=True).update(activo=False)
    nuevo = ConjuntoReglas.objects.create(
        version=version, vigente_desde=vigente_desde, topes=copy.deepcopy(topes if topes is not None else vigente.topes),
        activo=True, creado_por=usuario, basado_en=vigente,
    )
    for regla in vigente.reglas.order_by("codigo"):
        cambio = cambios_reglas.get(regla.codigo, {})
        Regla.objects.create(
            conjunto=nuevo, codigo=regla.codigo, nombre=regla.nombre, grupo=regla.grupo,
            parametros=copy.deepcopy(cambio.get("parametros", regla.parametros)),
            puntos_max=cambio.get("puntos_max", regla.puntos_max),
        )
    return nuevo
