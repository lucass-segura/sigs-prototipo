"""Carga los datos de demostración (ficticios)."""
from django.core.management.base import BaseCommand, CommandError

from nucleo import demo
from nucleo.constantes import CLAVE_DEMO


class Command(BaseCommand):
    help = "Carga los datos de demostración: espacios, usuarios y los casos de la narrativa del TFG (todo ficticio)."

    def add_arguments(self, parser):
        parser.add_argument("--si-vacia", action="store_true", help="No hace nada si la demo ya está cargada.")

    def handle(self, *args, **opciones):
        if demo.hay_demo():
            if opciones["si_vacia"]:
                self.stdout.write("La demo ya está cargada: no se crea nada.")
                return
            raise CommandError("La demo ya está cargada. Usá --si-vacia para omitirla sin error.")
        demo.cargar_demo()
        self.stdout.write(self.style.SUCCESS(f"Demo cargada. Todos los usuarios usan la contraseña {CLAVE_DEMO}"))
