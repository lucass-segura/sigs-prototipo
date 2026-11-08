"""Datos iniciales: el conjunto de reglas RS-1.0, vigente desde el 01/10/2026."""
import datetime

from django.db import migrations

TOPES = {
    "grupos": {"Cobertura": 30, "Persona": 35, "Bien": 25, "Antecedente": 30, "Denuncia": 10},
    "total": 100,
    "prioridad": {"media": 25, "alta": 50},
}

REGLAS = [
    ("R01", "Cobertura reciente", "Cobertura", {"niveles": [{"max_dias": 30, "puntos": 25}, {"max_dias": 60, "puntos": 12}]}, 25),
    ("R02", "Pago reciente", "Cobertura", {"min_dias": 0, "max_dias": 15, "puntos": 20}, 20),
    (
        "R03", "Persona recurrente", "Persona",
        {"ventana_meses": 12, "niveles": [{"min_antecedentes": 2, "puntos": 20}, {"min_antecedentes": 1, "puntos": 8}]}, 20,
    ),
    ("R04", "Siniestros cercanos", "Persona", {"max_dias": 90, "puntos": 15}, 15),
    ("R05", "Rol cruzado", "Persona", {"ventana_meses": 24, "puntos": 15}, 15),
    ("R06", "Bien repetido", "Bien", {"ventana_meses": 24, "puntos": 25}, 25),
    ("R07", "Vínculo con irregularidad confirmada", "Antecedente", {"puntos": 30}, 30),
    ("R08", "Denuncia tardía", "Denuncia", {"plazo_dias": 3, "puntos": 10}, 10),
]


def crear_rs_1_0(apps, schema_editor):
    ConjuntoReglas = apps.get_model("nucleo", "ConjuntoReglas")
    Regla = apps.get_model("nucleo", "Regla")
    conjunto = ConjuntoReglas.objects.create(
        version="RS-1.0", vigente_desde=datetime.date(2026, 10, 1), topes=TOPES, activo=True
    )
    for codigo, nombre, grupo, parametros, puntos_max in REGLAS:
        Regla.objects.create(
            conjunto=conjunto, codigo=codigo, nombre=nombre, grupo=grupo, parametros=parametros, puntos_max=puntos_max
        )


def borrar_rs_1_0(apps, schema_editor):
    apps.get_model("nucleo", "Regla").objects.filter(conjunto__version="RS-1.0").delete()
    apps.get_model("nucleo", "ConjuntoReglas").objects.filter(version="RS-1.0").delete()


class Migration(migrations.Migration):
    dependencies = [("nucleo", "0002_triggers_solo_altas")]
    operations = [migrations.RunPython(crear_rs_1_0, borrar_rs_1_0)]
