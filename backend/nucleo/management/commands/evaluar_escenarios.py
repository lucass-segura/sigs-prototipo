"""Evalúa los escenarios con el pipeline real y compara con el resultado esperado (precisión y sensibilidad)."""
import sys

from django.core.management.base import BaseCommand

from nucleo import escenarios


def _porcentaje(valor):
    return f"{valor * 100:.0f} %" if abs(valor * 100 - round(valor * 100)) < 1e-9 else f"{valor * 100:.1f} %"


def _reglas(diccionario):
    return ", ".join(f"{codigo} {puntos}" for codigo, puntos in sorted(diccionario.items())) or "—"


class Command(BaseCommand):
    help = (
        "Recorre los escenarios desde la base con construir_entradas + evaluar (RS-1.0, sin guardar nada), "
        "imprime una tabla por escenario, una por regla y las métricas. Sale con código 1 si algo no coincide."
    )

    def handle(self, *args, **opciones):
        resultado = escenarios.evaluar_escenarios()
        out = self.stdout.write
        out("Escenarios (esperado → obtenido)")
        out(f"{'Escenario':<10} {'Esperado':<62} {'Obtenido':<62} {'Total':>9} {'Prioridad':<13} Resultado")
        for fila in resultado["escenarios"]:
            if not fila["encontrado"]:
                out(f"{fila['id']:<10} {'—':<62} {'(no existe en la base)':<62} {'':>9} {'':<13} FALLA")
                continue
            total = f"{fila['puntaje_esperado']}→{fila['puntaje']}"
            prioridad = f"{fila['prioridad_esperada']}→{fila['prioridad']}"
            estado = "ok" if fila["coincide"] else "FALLA"
            out(f"{fila['id']:<10} {_reglas(fila['esperadas']):<62} {_reglas(fila['obtenidas']):<62} {total:>9} {prioridad:<13} {estado}")
        out("")
        out("Reglas (activaciones)")
        out(f"{'Regla':<6} {'Esperadas':>9} {'Obtenidas':>9} {'VP':>4} {'FP':>4} {'FN':>4}")
        for codigo, r in resultado["reglas"].items():
            out(f"{codigo:<6} {r['esperadas']:>9} {r['obtenidas']:>9} {r['vp']:>4} {r['fp']:>4} {r['fn']:>4}")
        m = resultado["metricas"]
        out("")
        out(f"Activaciones esperadas: {m['activaciones_esperadas']}")
        out(f"VP {m['vp']} · FP {m['fp']} · FN {m['fn']}")
        out(f"Precisión: {_porcentaje(m['precision'])}")
        out(f"Sensibilidad: {_porcentaje(m['sensibilidad'])}")
        fallas = [f["id"] for f in resultado["escenarios"] if not f["coincide"]]
        if fallas or m["fp"] or m["fn"]:
            out(self.style.ERROR(f"Hay diferencias con lo esperado: {', '.join(fallas) or 'revisar las métricas'}."))
            sys.exit(1)
        out(self.style.SUCCESS("Todos los escenarios coinciden con lo esperado."))
