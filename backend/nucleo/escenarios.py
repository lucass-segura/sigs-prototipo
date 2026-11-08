"""Escenarios de prueba (TT-02): 24 por regla y 6 combinados, con su resultado esperado documentado.

Todo es ficticio. Cada escenario usa personas y bienes únicos (prefijo `ESC-<id>`) para no cruzarse
con los demás ni con la demo. Por decisión del usuario (S12), R03 se cuenta como esperada donde la
definición la activa siempre. Esperado global: 16 activaciones por regla + 20 combinadas = 36.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from .constantes import CLAVE_DEMO
from .expediente import fecha_local
from .fabrica import crear_siniestro
from .models import ConjuntoReglas, EspacioTrabajo, Siniestro, Usuario
from .motor import conjunto_a_dict, construir_entradas, evaluar, guardar_evaluacion
from .normalizacion import normalizar_identificador_bien

NOMBRE_ESPACIO = "Escenarios de prueba (TT-02)"
EMAIL_PERITO = "perito.escenarios@sigs.test"
ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
H = datetime(2026, 6, 15, 12, 0, tzinfo=ZONA)
REGLAS = ["R01", "R02", "R03", "R04", "R05", "R06", "R07", "R08"]
CIERRE_APROBADO = {"resultado_reclamo": "aprobado", "irregularidad": False, "valoracion": 7, "justificacion": "Caso de prueba."}
CIERRE_IRREGULAR = {"resultado_reclamo": "rechazado", "irregularidad": True, "valoracion": 2, "justificacion": "Irregularidad confirmada."}
CIERRE_RECHAZADO = {"resultado_reclamo": "rechazado", "irregularidad": False, "valoracion": 5, "justificacion": "Rechazo sin irregularidad."}


@dataclass(frozen=True)
class Previo:
    """Antecedente de un escenario. `dias` o `meses` son hacia atrás desde H."""

    clave: str
    dias: int | None = None
    meses: int | None = None
    persona: str | None = "misma"  # "misma", "otra" o None
    roles: tuple = ("asegurado",)
    bien: str | None = None  # "mismo", "otro" o None
    estado: str = "cerrado"
    cierre: dict | None = field(default_factory=lambda: dict(CIERRE_APROBADO))

    def fecha(self):
        return H - (timedelta(days=self.dias) if self.dias is not None else relativedelta(months=self.meses))


@dataclass(frozen=True)
class Escenario:
    id: str
    descripcion: str
    esperado: dict  # {"reglas": {codigo: puntos}, "puntaje": n, "prioridad": "baja"|"media"|"alta", "no_evaluables": [..]}
    vigencia: int | None = 400  # días antes de H; None = sin inicio de vigencia
    pago: int | None = 400  # días antes de H; None = sin primer pago
    denuncia: int | None = 1  # días después de H; None = sin fecha de denuncia
    previos: tuple = ()
    dominio_caso: str = "VEH"  # cómo se escribe el dominio del caso (se normaliza al guardar)


def _e(reglas, puntaje, prioridad, no_evaluables=()):
    return {"reglas": reglas, "puntaje": puntaje, "prioridad": prioridad, "no_evaluables": list(no_evaluables)}


ESCENARIOS = [
    # R01 · Cobertura reciente
    Escenario("R01-A", "Vigencia y pago a 20 días del hecho", _e({"R01": 25}, 25, "media"), vigencia=20, pago=20),
    Escenario("R01-B", "Vigencia y pago a 75 días del hecho", _e({}, 0, "baja"), vigencia=75, pago=75),
    Escenario("R01-C", "Vigencia y pago a 30 días del hecho (límite)", _e({"R01": 25}, 25, "media"), vigencia=30, pago=30),
    # R02 · Pago reciente
    Escenario("R02-A", "Primer pago 10 días antes del hecho", _e({"R02": 20}, 20, "baja"), pago=10),
    Escenario("R02-B", "Primer pago 40 días antes del hecho", _e({}, 0, "baja"), pago=40),
    Escenario("R02-C", "Sin fecha de primer pago", _e({}, 0, "baja", ["R02"]), pago=None),
    # R03 · Persona recurrente
    Escenario("R03-A", "Dos previos de la persona en 12 meses", _e({"R03": 20}, 20, "baja"),
              previos=(Previo("A1", dias=120), Previo("A2", dias=200))),
    Escenario("R03-B", "Sin previos", _e({}, 0, "baja")),
    Escenario("R03-C", "Un previo de la persona", _e({"R03": 8}, 8, "baja"), previos=(Previo("A1", dias=150),)),
    # R04 · Siniestros cercanos (R03 se activa siempre con un previo de la persona en 12 meses)
    Escenario("R04-A", "Previo de la persona hace 45 días", _e({"R03": 8, "R04": 15}, 23, "baja"), previos=(Previo("A1", dias=45),)),
    Escenario("R04-B", "Previo de la persona hace 150 días", _e({"R03": 8}, 8, "baja"), previos=(Previo("A1", dias=150),)),
    Escenario("R04-C", "Previo de la persona hace 90 días (límite)", _e({"R03": 8, "R04": 15}, 23, "baja"), previos=(Previo("A1", dias=90),)),
    # R05 · Rol cruzado
    Escenario("R05-A", "Testigo en un previo de hace 10 meses", _e({"R03": 8, "R05": 15}, 23, "baja"),
              previos=(Previo("A1", meses=10, roles=("testigo",)),)),
    Escenario("R05-B", "Mismo rol en un previo de hace 18 meses", _e({}, 0, "baja"), previos=(Previo("A1", meses=18),)),
    Escenario("R05-C", "Rol cruzado en un previo de hace 25 meses", _e({}, 0, "baja"),
              previos=(Previo("A1", meses=25, roles=("testigo",)),)),
    # R06 · Bien repetido
    Escenario("R06-A", "Mismo dominio hace 8 meses, otra persona", _e({"R06": 25}, 25, "media"),
              previos=(Previo("A1", meses=8, persona="otra", bien="mismo"),)),
    Escenario("R06-B", "Antecedente con otro dominio y otra persona", _e({}, 0, "baja"),
              previos=(Previo("A1", meses=8, persona="otra", bien="otro"),)),
    Escenario("R06-C", "Dominio del caso escrito con guiones y antecedente sin guiones", _e({"R06": 25}, 25, "media"),
              previos=(Previo("A1", meses=8, persona="otra", bien="mismo"),), dominio_caso="AB-123-CD"),
    # R07 · Vínculo con irregularidad confirmada
    Escenario("R07-A", "Antecedente de hace 30 meses cerrado con irregularidad", _e({"R07": 30}, 30, "media"),
              previos=(Previo("A1", meses=30, cierre=dict(CIERRE_IRREGULAR)),)),
    Escenario("R07-B", "Antecedente de hace 30 meses rechazado sin irregularidad", _e({}, 0, "baja"),
              previos=(Previo("A1", meses=30, cierre=dict(CIERRE_RECHAZADO)),)),
    Escenario("R07-C", "Antecedente con irregularidad pero anulado", _e({}, 0, "baja"),
              previos=(Previo("A1", meses=30, estado="anulado", cierre=dict(CIERRE_IRREGULAR)),)),
    # R08 · Denuncia tardía
    Escenario("R08-A", "Denuncia a los 5 días", _e({"R08": 10}, 10, "baja"), denuncia=5),
    Escenario("R08-B", "Denuncia al día siguiente", _e({}, 0, "baja"), denuncia=1),
    Escenario("R08-C", "Denuncia a los 3 días (límite)", _e({}, 0, "baja"), denuncia=3),
    # Combinados
    Escenario("C1", "Tabla 9 del TFG", _e({"R01": 25, "R02": 20, "R03": 8, "R04": 15}, 53, "alta"),
              vigencia=20, pago=10, denuncia=1, previos=(Previo("A1", dias=60),)),
    Escenario("C2", "Robo de rueda: dos robos previos de la misma persona y el mismo dominio",
              _e({"R01": 12, "R03": 20, "R04": 15, "R06": 25}, 72, "alta"), vigencia=40, pago=35,
              previos=(Previo("A1", dias=60, bien="mismo"), Previo("A2", meses=8, bien="mismo"))),
    Escenario("C3", "Un antecedente coincide por el bien y está cerrado con irregularidad", _e({"R06": 25, "R07": 30}, 55, "alta"),
              previos=(Previo("A1", meses=10, persona="otra", bien="mismo", cierre=dict(CIERRE_IRREGULAR)),)),
    Escenario("C4", "Tres previos de la persona y un rol cruzado como tercero", _e({"R03": 20, "R05": 15}, 35, "media"),
              previos=(Previo("A1", dias=100), Previo("A2", dias=200), Previo("A3", dias=300, roles=("tercero",)))),
    Escenario("C5", "Cumple las 8 reglas: 160 en bruto, 130 con los topes por grupo, total 100",
              _e({f"R0{i}": p for i, p in zip(range(1, 9), (25, 20, 20, 15, 15, 25, 30, 10))}, 100, "alta"),
              vigencia=10, pago=5, denuncia=10,
              previos=(
                  Previo("A1", dias=30),
                  Previo("A2", dias=200, roles=("testigo",), bien="mismo"),
                  Previo("A3", dias=400, persona=None, bien="mismo", cierre=dict(CIERRE_IRREGULAR)),
              )),
    Escenario("C6", "Hecho a 200 días de la vigencia, sin coincidencias, sin primer pago", _e({}, 0, "baja", ["R02"]),
              vigencia=200, pago=None, denuncia=1),
]
POR_ID = {e.id: e for e in ESCENARIOS}


def numero_expediente(escenario_id):
    return f"ESC-{escenario_id}"


def espacio_y_perito():
    """Espacio y perito propios de los escenarios (se crean si no existen)."""
    espacio, _ = EspacioTrabajo.objects.get_or_create(nombre=NOMBRE_ESPACIO)
    perito = Usuario.objects.filter(email=EMAIL_PERITO).first()
    if perito is None:
        perito = Usuario.objects.create_user(
            email=EMAIL_PERITO, nombre="Perito de escenarios", rol=Usuario.PERITO, espacio=espacio, password=CLAVE_DEMO
        )
    return espacio, perito


def _persona(escenario_id, quien):
    return {"tipo_identificador": "DNI", "identificador": f"ESC-{escenario_id}-{quien}", "nombre": f"Persona {escenario_id}-{quien}"}


def _poliza(escenario):
    return {
        "numero": f"ESC-{escenario.id}",
        "compania": "Aseguradora Ejemplo S. A.",
        "cobertura": "Todo riesgo",
        "inicio_vigencia": (H - timedelta(days=escenario.vigencia)).date() if escenario.vigencia is not None else None,
        "primer_pago": (H - timedelta(days=escenario.pago)).date() if escenario.pago is not None else None,
    }


def crear_escenario(escenario, perito, evaluar_caso=True):
    """Crea el caso y sus antecedentes. Devuelve el siniestro del caso (con una evaluación `escenario` si se pide)."""
    persona = _persona(escenario.id, "P1")
    dominio_caso = f"ESC-{escenario.id}-{escenario.dominio_caso}"
    caso = crear_siniestro(
        perito, numero_expediente(escenario.id), tipo=f"Escenario {escenario.id}", fecha_hecho=H,
        fecha_denuncia=(H + timedelta(days=escenario.denuncia)).date() if escenario.denuncia is not None else None,
        poliza=_poliza(escenario), personas=[dict(persona, roles=["asegurado"])],
        bienes=[{"tipo": "vehiculo", "identificador": dominio_caso}],
    )
    for previo in escenario.previos:
        personas, bienes = [], []
        if previo.persona == "misma":
            personas = [dict(persona, roles=list(previo.roles))]
        elif previo.persona == "otra":
            personas = [dict(_persona(escenario.id, f"OTRA-{previo.clave}"), roles=["asegurado"])]
        if previo.bien == "mismo":
            bienes = [{"tipo": "vehiculo", "identificador": normalizar_identificador_bien(dominio_caso)}]
        elif previo.bien == "otro":
            bienes = [{"tipo": "vehiculo", "identificador": f"ESC-{escenario.id}-OTRO-{previo.clave}"}]
        crear_siniestro(
            perito, f"ESC-{escenario.id}-{previo.clave}", tipo="Antecedente de escenario", fecha_hecho=previo.fecha(),
            personas=personas, bienes=bienes, estado=previo.estado, cierre=previo.cierre,
            motivo_anulacion="Carga errónea (escenario)" if previo.estado == "anulado" else "",
        )
    if evaluar_caso:
        guardar_evaluacion(caso, "escenario")
    return caso


def crear_escenarios(solo=None):
    """Crea los escenarios (todos o los ids indicados) y una evaluación por caso. Devuelve `{id: siniestro}`."""
    _, perito = espacio_y_perito()
    return {e.id: crear_escenario(e, perito) for e in ESCENARIOS if solo is None or e.id in solo}


def hay_escenarios():
    return EspacioTrabajo.objects.filter(nombre=NOMBRE_ESPACIO).exists()


# --------------------------------------------------------------------------
# Evaluación de los escenarios con el pipeline real (sin guardar nada)
# --------------------------------------------------------------------------
def evaluar_escenarios(conjunto=None):
    """Recorre los casos desde la base con `construir_entradas` + `evaluar`. Compara con lo esperado.

    Devuelve `{"escenarios": [...], "reglas": {...}, "metricas": {...}}`. La unidad de evaluación es cada
    combinación (escenario, regla): VP = regla esperada que se activa, FP = activación no prevista,
    FN = regla esperada que no se activa.
    """
    conjunto = conjunto or ConjuntoReglas.objects.get(version="RS-1.0")
    conjunto_dict = conjunto_a_dict(conjunto)
    filas = []
    por_regla = {r: {"esperadas": 0, "obtenidas": 0, "vp": 0, "fp": 0, "fn": 0} for r in REGLAS}
    for escenario in ESCENARIOS:
        caso = Siniestro.objects.filter(numero_expediente=numero_expediente(escenario.id)).first()
        if caso is None:
            filas.append({"id": escenario.id, "encontrado": False, "coincide": False})
            for regla in escenario.esperado["reglas"]:
                por_regla[regla]["esperadas"] += 1
                por_regla[regla]["fn"] += 1
            continue
        resultado = evaluar(construir_entradas(caso), conjunto_dict)
        obtenidas = {s["codigo"]: s["puntos"] for s in resultado["senales"] if s["estado"] == "activada"}
        no_evaluables = sorted(s["codigo"] for s in resultado["senales"] if s["estado"] == "no_evaluable")
        esperadas = escenario.esperado["reglas"]
        for regla in REGLAS:
            if regla in esperadas:
                por_regla[regla]["esperadas"] += 1
            if regla in obtenidas:
                por_regla[regla]["obtenidas"] += 1
            if regla in esperadas and regla in obtenidas:
                por_regla[regla]["vp"] += 1
            elif regla in obtenidas:
                por_regla[regla]["fp"] += 1
            elif regla in esperadas:
                por_regla[regla]["fn"] += 1
        coincide = (
            obtenidas == esperadas
            and resultado["puntaje"] == escenario.esperado["puntaje"]
            and resultado["prioridad"] == escenario.esperado["prioridad"]
            and no_evaluables == sorted(escenario.esperado["no_evaluables"])
        )
        filas.append({
            "id": escenario.id, "encontrado": True, "esperadas": esperadas, "obtenidas": obtenidas,
            "puntaje_esperado": escenario.esperado["puntaje"], "puntaje": resultado["puntaje"],
            "prioridad_esperada": escenario.esperado["prioridad"], "prioridad": resultado["prioridad"],
            "no_evaluables_esperadas": sorted(escenario.esperado["no_evaluables"]), "no_evaluables": no_evaluables,
            "coincide": coincide, "fecha_hecho": fecha_local(caso.fecha_hecho),
        })
    vp = sum(r["vp"] for r in por_regla.values())
    fp = sum(r["fp"] for r in por_regla.values())
    fn = sum(r["fn"] for r in por_regla.values())
    metricas = {
        "vp": vp, "fp": fp, "fn": fn,
        "precision": vp / (vp + fp) if vp + fp else 1.0,
        "sensibilidad": vp / (vp + fn) if vp + fn else 1.0,
        "activaciones_esperadas": sum(len(e.esperado["reglas"]) for e in ESCENARIOS),
    }
    return {"escenarios": filas, "reglas": por_regla, "metricas": metricas}
