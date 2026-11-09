"""Motor de reglas RS-1.0.

`evaluar` es una función pura y determinista: recibe las `entradas` y el conjunto de reglas y
devuelve señales, puntaje y prioridad. No lee la base ni la hora. Con las mismas entradas y la
misma versión el resultado es idéntico (reproducibilidad).

Los umbrales y los puntos salen de `regla.parametros`: no están escritos en el código.
"""
from datetime import date

from dateutil.relativedelta import relativedelta
from django.db import transaction

from .coincidencias import buscar_antecedentes, casos_en_analisis_vinculados, datos_del_caso, unir
from .expediente import cierres_vigentes, fecha_local
from .models import ConjuntoReglas, Evaluacion, Senal, Siniestro

ESTADOS_CON_CIERRE = (Siniestro.CERRADO, Siniestro.ARCHIVADO)
NOMBRES_BIEN = {"vehiculo": "vehículo", "motocicleta": "motocicleta", "telefono": "teléfono", "computadora": "equipo"}


# --------------------------------------------------------------------------
# Entradas (leen la base) y conjunto de reglas
# --------------------------------------------------------------------------
def conjunto_a_dict(conjunto):
    """Conjunto de reglas como diccionario simple (lo único que necesita `evaluar`)."""
    return {
        "id": conjunto.pk,
        "version": conjunto.version,
        "vigente_desde": conjunto.vigente_desde.isoformat(),
        "topes": conjunto.topes,
        "reglas": [
            {"codigo": r.codigo, "nombre": r.nombre, "grupo": r.grupo, "parametros": r.parametros, "puntos_max": r.puntos_max}
            for r in conjunto.reglas.order_by("codigo")
        ],
    }


def construir_entradas(siniestro):
    """Todo lo que usa el motor, leído de la base y listo para guardarse como JSON.

    Los nombres son los que el perito declaró en este caso, también para las personas de los antecedentes:
    las explicaciones no repiten lo que escribió el perito de otro expediente.
    """
    personas_caso, bienes_caso = datos_del_caso(siniestro)
    antecedentes = buscar_antecedentes(siniestro)
    cierres = cierres_vigentes([a["siniestro"].pk for a in antecedentes if a["siniestro"].estado in ESTADOS_CON_CIERRE])
    poliza = siniestro.poliza
    entradas_antecedentes = []
    for a in antecedentes:
        s = a["siniestro"]
        cierre = cierres.get(s.pk) if s.estado in ESTADOS_CON_CIERRE else None
        entradas_antecedentes.append({
            "id": s.pk,
            "numero_expediente": s.numero_expediente,
            "fecha_hecho": fecha_local(s.fecha_hecho).isoformat(),
            "estado": s.estado,
            "irregularidad": bool(cierre.irregularidad) if cierre else False,
            "resultado_reclamo": cierre.resultado_reclamo if cierre else None,
            "personas": sorted(
                (
                    {
                        "tipo_identificador": d["persona"].tipo_identificador,
                        "identificador": d["persona"].identificador,
                        "nombre": d["nombre"],
                        "roles": sorted(set(d["roles"])),
                    }
                    for d in a["personas"].values()
                ),
                key=lambda p: (p["tipo_identificador"], p["identificador"]),
            ),
            "bienes": sorted(b.identificador_norm for b in a["bienes"]),
        })
    return {
        "siniestro": {
            "id": siniestro.pk,
            "numero_expediente": siniestro.numero_expediente,
            "fecha_hecho": fecha_local(siniestro.fecha_hecho).isoformat(),
            "fecha_denuncia": siniestro.fecha_denuncia.isoformat() if siniestro.fecha_denuncia else None,
            "inicio_vigencia": poliza.inicio_vigencia.isoformat() if poliza and poliza.inicio_vigencia else None,
            "primer_pago": poliza.primer_pago.isoformat() if poliza and poliza.primer_pago else None,
        },
        "personas": sorted(
            (
                {
                    "tipo_identificador": d["persona"].tipo_identificador,
                    "identificador": d["persona"].identificador,
                    "nombre": d["nombre"],
                    "roles": sorted(set(d["roles"])),
                }
                for d in personas_caso.values()
            ),
            key=lambda p: (p["tipo_identificador"], p["identificador"]),
        ),
        "bienes": sorted(
            ({"tipo": b.tipo, "identificador_norm": b.identificador_norm} for b in bienes_caso),
            key=lambda b: b["identificador_norm"],
        ),
        "antecedentes": entradas_antecedentes,
    }


# --------------------------------------------------------------------------
# Textos
# --------------------------------------------------------------------------
def _dias(n):
    return "1 día" if abs(n) == 1 else f"{abs(n)} días"


def _hace(fecha_antecedente, hecho):
    """«de hace 13 meses» (meses con `relativedelta`); si dan 0, se usan días."""
    delta = relativedelta(hecho, fecha_antecedente)
    meses = delta.years * 12 + delta.months
    if meses >= 1:
        return "de hace 1 mes" if meses == 1 else f"de hace {meses} meses"
    return f"de hace {_dias((hecho - fecha_antecedente).days)}"


def _nombre_bien(tipo):
    return NOMBRES_BIEN.get(tipo, "bien")


def _no_evaluable(dato):
    return f"No se pudo evaluar: falta la fecha {dato}."


# --------------------------------------------------------------------------
# Contexto de evaluación
# --------------------------------------------------------------------------
def _fecha(valor):
    return date.fromisoformat(valor) if valor else None


class _Caso:
    """Entradas ya interpretadas (fechas como `date`)."""

    def __init__(self, entradas):
        s = entradas["siniestro"]
        self.hecho = _fecha(s["fecha_hecho"])
        self.denuncia = _fecha(s.get("fecha_denuncia"))
        self.inicio_vigencia = _fecha(s.get("inicio_vigencia"))
        self.primer_pago = _fecha(s.get("primer_pago"))
        self.personas = entradas.get("personas", [])
        self.bienes = entradas.get("bienes", [])
        self.roles_caso = {(p["tipo_identificador"], p["identificador"]): set(p["roles"]) for p in self.personas}
        bienes_caso = {b["identificador_norm"] for b in self.bienes}
        self.antecedentes = []
        for a in sorted(entradas.get("antecedentes", []), key=lambda x: x["id"]):
            # Solo cuentan los vínculos reales: misma persona (tipo + identificador) o mismo bien.
            personas = [p for p in a["personas"] if (p["tipo_identificador"], p["identificador"]) in self.roles_caso]
            bienes = [b for b in a["bienes"] if b in bienes_caso]
            if not personas and not bienes:
                continue
            fecha = _fecha(a["fecha_hecho"])
            if fecha >= self.hecho:
                continue  # solo cuenta un antecedente anterior al hecho (también para R07, que no tiene ventana)
            copia = dict(a, personas=personas, bienes=bienes)
            copia["fecha"] = fecha
            self.antecedentes.append(copia)

    def en_ventana(self, antecedente, meses):
        """`H - N meses <= H_ant < H` (estrictamente antes del hecho)."""
        return self.hecho - relativedelta(months=meses) <= antecedente["fecha"] < self.hecho

    def dias_antes(self, antecedente):
        return (self.hecho - antecedente["fecha"]).days

    @property
    def nombres_personas(self):
        return unir(p["nombre"] for p in self.personas if p.get("nombre"))


def _item(antecedente, vinculo):
    return {
        "id": antecedente["id"],
        "numero_expediente": antecedente["numero_expediente"],
        "fecha_hecho": antecedente["fecha_hecho"],
        "vinculo": vinculo,
    }


def _resultado(regla, estado, puntos, texto, dato, antecedentes=()):
    puntos = min(puntos, regla["puntos_max"])  # una regla nunca otorga más que su máximo
    return {
        "codigo": regla["codigo"],
        "nombre": regla["nombre"],
        "grupo": regla["grupo"],
        "estado": estado,
        "puntos": puntos,
        "puntos_max": regla["puntos_max"],
        "texto": texto,
        "dato": dato,
        "antecedentes": list(antecedentes),
    }


def _con_personas(caso):
    return [a for a in caso.antecedentes if a["personas"]]


# --------------------------------------------------------------------------
# Reglas
# --------------------------------------------------------------------------
def _r01(caso, regla):
    if caso.inicio_vigencia is None:
        return _resultado(regla, "no_evaluable", 0, _no_evaluable("de inicio de vigencia"), {"falta": "inicio_vigencia"})
    niveles = sorted(regla["parametros"]["niveles"], key=lambda n: n["max_dias"])
    d = (caso.hecho - caso.inicio_vigencia).days
    nivel = next((n for n in niveles if d <= n["max_dias"]), None)
    umbral = nivel["max_dias"] if nivel else niveles[-1]["max_dias"]
    if d > 0:
        cuando = f"{_dias(d)} después del inicio de vigencia"
    elif d < 0:
        cuando = f"{_dias(d)} antes del inicio de vigencia"
    else:
        cuando = "el mismo día del inicio de vigencia"
    texto = f"El hecho ocurrió {cuando}. Umbral {_dias(umbral)}."
    dato = {"dias": d, "umbral_dias": umbral, "inicio_vigencia": caso.inicio_vigencia.isoformat()}
    if nivel:
        return _resultado(regla, "activada", nivel["puntos"], texto, dato)
    return _resultado(regla, "no_activada", 0, texto, dato)


def _r02(caso, regla):
    if caso.primer_pago is None:
        return _resultado(regla, "no_evaluable", 0, _no_evaluable("del primer pago"), {"falta": "primer_pago"})
    p = regla["parametros"]
    d = (caso.hecho - caso.primer_pago).days
    if d > 0:
        cuando = f"{_dias(d)} antes del hecho"
    elif d < 0:
        cuando = f"{_dias(d)} después del hecho"
    else:
        cuando = "el mismo día del hecho"
    texto = f"El primer pago se registró {cuando}. Umbral {_dias(p['max_dias'])}."
    dato = {"dias": d, "umbral_dias": p["max_dias"], "primer_pago": caso.primer_pago.isoformat()}
    if p.get("min_dias", 0) <= d <= p["max_dias"]:
        return _resultado(regla, "activada", p["puntos"], texto, dato)
    return _resultado(regla, "no_activada", 0, texto, dato)


def _r03(caso, regla):
    """Persona recurrente: se cuenta por persona y gana el nivel más alto entre las personas del caso."""
    p = regla["parametros"]
    meses = p["ventana_meses"]
    niveles = sorted(p["niveles"], key=lambda n: -n["min_antecedentes"])

    def puntos_de(cantidad):
        return next((n["puntos"] for n in niveles if cantidad >= n["min_antecedentes"]), 0)

    por_persona = {}  # (tipo, identificador) -> {"nombre", "antecedentes": [antecedente]}
    for a in _con_personas(caso):
        if not caso.en_ventana(a, meses):
            continue
        for d in a["personas"]:
            clave = (d["tipo_identificador"], d["identificador"])
            entrada = por_persona.setdefault(clave, {"nombre": d["nombre"], "antecedentes": []})
            entrada["antecedentes"].append(a)
    mejor = max((puntos_de(len(e["antecedentes"])) for e in por_persona.values()), default=0)
    usadas = [e for e in por_persona.values() if mejor and puntos_de(len(e["antecedentes"])) == mejor]
    dato = {
        "cantidad": max((len(e["antecedentes"]) for e in usadas), default=0),
        "ventana_meses": meses,
        "personas": [{"nombre": e["nombre"], "cantidad": len(e["antecedentes"])} for e in usadas],
    }
    if not usadas:
        sujeto = f"{caso.nombres_personas} no tiene" if len(caso.personas) == 1 else "Ninguna persona del caso tiene"
        return _resultado(regla, "no_activada", 0, f"{sujeto} otros siniestros válidos en los últimos {meses} meses.", dato)
    frases = []
    items = {}
    for e in usadas:
        cantidad = "en 1 siniestro válido" if len(e["antecedentes"]) == 1 else f"en {len(e['antecedentes'])} siniestros válidos"
        numeros = ", ".join(a["numero_expediente"] for a in e["antecedentes"])
        frases.append(f"{e['nombre']} figura {cantidad} de los últimos {meses} meses: {numeros}.")
        for a in e["antecedentes"]:
            items.setdefault(a["id"], (a, []))[1].append(e["nombre"])
    lista = [_item(a, "Persona " + unir(nombres)) for a, nombres in sorted(items.values(), key=lambda x: x[0]["id"])]
    return _resultado(regla, "activada", mejor, " ".join(frases), dato, lista)


def _r04(caso, regla):
    p = regla["parametros"]
    umbral = p["max_dias"]
    cercanos = [a for a in _con_personas(caso) if 0 < caso.dias_antes(a) <= umbral]
    dato = {"umbral_dias": umbral, "cantidad": len(cercanos)}
    if not cercanos:
        texto = f"Ninguna persona del caso tiene siniestros válidos en los {umbral} días anteriores al hecho. Umbral {_dias(umbral)}."
        return _resultado(regla, "no_activada", 0, texto, dato)
    nombres = unir(d["nombre"] for a in cercanos for d in a["personas"])
    if len(cercanos) == 1:
        a = cercanos[0]
        detalle = f"el siniestro {a['numero_expediente']} de hace {_dias(caso.dias_antes(a))}"
    else:
        detalle = "los siniestros " + unir(f"{a['numero_expediente']} de hace {_dias(caso.dias_antes(a))}" for a in cercanos)
    texto = f"{nombres} tiene {detalle}. Umbral {_dias(umbral)}."
    items = [_item(a, "Persona " + unir(d["nombre"] for d in a["personas"])) for a in cercanos]
    return _resultado(regla, "activada", p["puntos"], texto, dato, items)


def _r05(caso, regla):
    p = regla["parametros"]
    meses = p["ventana_meses"]
    cruces = []  # (antecedente, persona del antecedente, roles distintos, roles del caso)
    for a in _con_personas(caso):
        if not caso.en_ventana(a, meses):
            continue
        for d in a["personas"]:
            roles_caso = caso.roles_caso.get((d["tipo_identificador"], d["identificador"]), set())
            distintos = [r for r in d["roles"] if r not in roles_caso]
            if distintos:
                cruces.append((a, d, distintos, sorted(roles_caso)))
    dato = {"ventana_meses": meses, "cantidad": len(cruces)}
    if not cruces:
        texto = f"Ninguna persona del caso figura con otro rol en siniestros válidos de los últimos {meses} meses."
        return _resultado(regla, "no_activada", 0, texto, dato)
    frases = [
        f"{d['nombre']} figura como {unir(distintos)} en {a['numero_expediente']} {_hace(a['fecha'], caso.hecho)}. "
        f"En este caso es {unir(roles_caso) or 'una persona sin rol'}."
        for a, d, distintos, roles_caso in cruces
    ]
    items = [_item(a, f"Persona {d['nombre']} como {unir(distintos)}") for a, d, distintos, _ in cruces]
    return _resultado(regla, "activada", p["puntos"], " ".join(frases), dato, items)


def _r06(caso, regla):
    p = regla["parametros"]
    meses = p["ventana_meses"]
    tipos = {b["identificador_norm"]: b["tipo"] for b in caso.bienes}
    repetidos = [(a, bien) for a in caso.antecedentes if caso.en_ventana(a, meses) for bien in a["bienes"]]
    dato = {"ventana_meses": meses, "cantidad": len(repetidos)}
    if not repetidos:
        texto = f"Ningún bien del caso figura en antecedentes válidos de los últimos {meses} meses."
        return _resultado(regla, "no_activada", 0, texto, dato)
    frases = []
    items = []
    for bien in dict.fromkeys(b for _, b in repetidos):
        donde = [a for a, b in repetidos if b == bien]
        nombre = f"El {_nombre_bien(tipos.get(bien))} {bien}"
        if len(donde) == 1:
            frases.append(f"{nombre} figura en el antecedente {donde[0]['numero_expediente']} {_hace(donde[0]['fecha'], caso.hecho)}.")
        else:
            lista = unir(f"{a['numero_expediente']} {_hace(a['fecha'], caso.hecho)}" for a in donde)
            frases.append(f"{nombre} figura en los antecedentes {lista}.")
        items.extend(_item(a, f"{_nombre_bien(tipos.get(bien)).capitalize()} {bien}") for a in donde)
    return _resultado(regla, "activada", p["puntos"], " ".join(frases), dato, items)


def _r07(caso, regla):
    p = regla["parametros"]
    graves = [
        a for a in caso.antecedentes
        if a["estado"] in ESTADOS_CON_CIERRE and a.get("irregularidad") and (a["personas"] or a["bienes"])
    ]
    dato = {"cantidad": len(graves)}
    if not graves:
        texto = "Ningún antecedente vinculado fue cerrado con irregularidad confirmada."
        return _resultado(regla, "no_activada", 0, texto, dato)
    frases = []
    items = []
    for a in graves:
        sujetos = [d["nombre"] for d in a["personas"]] + list(a["bienes"])
        frases.append(f"{unir(sujetos)} figura en el antecedente {a['numero_expediente']} cerrado con irregularidad confirmada.")
        items.append(_item(a, unir(sujetos)))
    return _resultado(regla, "activada", p["puntos"], " ".join(frases), dato, items)


def _r08(caso, regla):
    if caso.denuncia is None:
        return _resultado(regla, "no_evaluable", 0, _no_evaluable("de denuncia"), {"falta": "fecha_denuncia"})
    plazo = regla["parametros"]["plazo_dias"]
    d = (caso.denuncia - caso.hecho).days
    if d > 0:
        cuando = f"{_dias(d)} después del hecho"
    elif d < 0:
        cuando = f"{_dias(d)} antes del hecho"
    else:
        cuando = "el mismo día del hecho"
    texto = f"La denuncia se hizo {cuando}. Plazo {_dias(plazo)}."
    dato = {"dias": d, "plazo_dias": plazo, "fecha_denuncia": caso.denuncia.isoformat()}
    if d > plazo:
        return _resultado(regla, "activada", regla["parametros"]["puntos"], texto, dato)
    return _resultado(regla, "no_activada", 0, texto, dato)


REGLAS = {"R01": _r01, "R02": _r02, "R03": _r03, "R04": _r04, "R05": _r05, "R06": _r06, "R07": _r07, "R08": _r08}


# --------------------------------------------------------------------------
# Topes y prioridad
# --------------------------------------------------------------------------
def aplicar_topes(senales, topes):
    """Suma por grupo y corta en el tope del grupo; después suma los grupos y corta en el total."""
    grupos = {nombre: {"bruto": 0, "tope": tope, "puntos": 0} for nombre, tope in topes["grupos"].items()}
    for s in senales:
        if s["estado"] != "activada":
            continue
        g = grupos.setdefault(s["grupo"], {"bruto": 0, "tope": topes["total"], "puntos": 0})
        g["bruto"] += s["puntos"]
    for g in grupos.values():
        g["puntos"] = min(g["bruto"], g["tope"])
    puntaje = min(sum(g["puntos"] for g in grupos.values()), topes["total"])
    return grupos, puntaje


def prioridad_de(puntaje, topes):
    if puntaje >= topes["prioridad"]["alta"]:
        return "alta"
    if puntaje >= topes["prioridad"]["media"]:
        return "media"
    return "baja"


def evaluar(entradas, conjunto):
    """Evaluación pura: `{version, senales, grupos, puntaje, prioridad}`."""
    caso = _Caso(entradas)
    senales = []
    for regla in sorted(conjunto["reglas"], key=lambda r: r["codigo"]):
        senales.append(REGLAS[regla["codigo"]](caso, regla))
    grupos, puntaje = aplicar_topes(senales, conjunto["topes"])
    return {
        "version": conjunto["version"],
        "senales": senales,
        "grupos": grupos,
        "puntaje": puntaje,
        "prioridad": prioridad_de(puntaje, conjunto["topes"]),
    }


# --------------------------------------------------------------------------
# Persistencia
# --------------------------------------------------------------------------
def conjunto_activo():
    return ConjuntoReglas.objects.get(activo=True)


@transaction.atomic
def guardar_evaluacion(siniestro, motivo, conjunto=None, entradas=None, creada_en=None):
    """Evalúa el siniestro y guarda una evaluación nueva (nunca se sobrescribe) con sus señales."""
    conjunto = conjunto or conjunto_activo()
    entradas = entradas if entradas is not None else construir_entradas(siniestro)
    resultado = evaluar(entradas, conjunto_a_dict(conjunto))
    campos = {"creada_en": creada_en} if creada_en is not None else {}
    evaluacion = Evaluacion.objects.create(
        siniestro=siniestro,
        conjunto=conjunto,
        puntaje=resultado["puntaje"],
        prioridad=resultado["prioridad"],
        entradas=entradas,
        motivo=motivo,
        **campos,
    )
    reglas = {r.codigo: r for r in conjunto.reglas.all()}
    Senal.objects.bulk_create([
        Senal(
            evaluacion=evaluacion,
            regla=reglas[s["codigo"]],
            estado=s["estado"],
            puntos=s["puntos"],
            antecedentes=s["antecedentes"],
            texto_explicacion=s["texto"],
            dato=s["dato"],
        )
        for s in resultado["senales"]
    ])
    return evaluacion


def recalcular_vinculados(siniestro, motivo="antecedente_confirmado"):
    """Recalcula los casos `en_analisis` (de cualquier espacio) a los que `siniestro` les cuenta como antecedente.

    Se llama al confirmar, cerrar (o cambiar el cierre), archivar o anular `siniestro`; `motivo` dice cuál fue.
    Cada caso afectado recibe una evaluación nueva y las anteriores no se tocan.
    """
    return [guardar_evaluacion(caso, motivo) for caso in casos_en_analisis_vinculados(siniestro)]


def recalcular_en_analisis(conjunto):
    """Al publicar una versión nueva de reglas: una evaluación nueva, con esa versión, de todos los casos `en_analisis`."""
    casos = Siniestro.objects.filter(estado=Siniestro.EN_ANALISIS, confirmado_en__isnull=False).order_by("id")
    return [guardar_evaluacion(caso, "nueva_version", conjunto=conjunto) for caso in casos]


def resultado_de_evaluacion(evaluacion):
    """Cuerpo de `GET /siniestros/<id>/evaluacion`."""
    conjunto = evaluacion.conjunto
    topes = conjunto.topes
    senales = []
    for s in evaluacion.senales.select_related("regla"):
        senales.append({
            "codigo": s.regla.codigo,
            "nombre": s.regla.nombre,
            "grupo": s.regla.grupo,
            "estado": s.estado,
            "puntos": s.puntos,
            "puntos_max": s.regla.puntos_max,
            "texto": s.texto_explicacion,
            "dato": s.dato,
            "antecedentes": s.antecedentes,
        })
    grupos, _ = aplicar_topes(senales, topes)
    return {
        "id": evaluacion.pk,
        "version": conjunto.version,
        "creada_en": evaluacion.creada_en,
        "motivo": evaluacion.motivo,
        "puntaje": evaluacion.puntaje,
        "prioridad": evaluacion.prioridad,
        "grupos": grupos,
        "senales": senales,
        "entradas": evaluacion.entradas,
    }
