"""Crea los 30 escenarios de prueba (TT-02) con una evaluación por caso."""
from django.core.management.base import BaseCommand

from nucleo import escenarios


class Command(BaseCommand):
    help = "Crea los 30 escenarios de prueba con su resultado esperado documentado (datos ficticios)."

    def add_arguments(self, parser):
        parser.add_argument("--si-vacia", action="store_true", help="No hace nada si los escenarios ya existen.")

    def handle(self, *args, **opciones):
        if opciones["si_vacia"] and escenarios.hay_escenarios():
            self.stdout.write("Los escenarios ya existen: no se crea nada.")
            return
        creados = escenarios.crear_escenarios()
        self.stdout.write(self.style.SUCCESS(f"Escenarios creados: {len(creados)} casos con su evaluación (motivo «escenario»)."))
