"""Política de contraseña del TFG: mínimo 8 caracteres, mayúscula, minúscula, número y carácter especial."""
import re

from django.core.exceptions import ValidationError

MINIMO = 8


class ComplejidadValidator:
    """Validador de complejidad con mensajes en español.

    El largo mínimo lo exige este validador y también `MinimumLengthValidator` de Django.
    """

    def validate(self, password, user=None):
        errores = []
        if len(password) < MINIMO:
            errores.append(ValidationError(f"La contraseña tiene que tener al menos {MINIMO} caracteres.", code="password_corta"))
        if not re.search(r"[A-ZÁÉÍÓÚÑÜ]", password):
            errores.append(ValidationError("La contraseña tiene que incluir al menos una letra mayúscula.", code="sin_mayuscula"))
        if not re.search(r"[a-záéíóúñü]", password):
            errores.append(ValidationError("La contraseña tiene que incluir al menos una letra minúscula.", code="sin_minuscula"))
        if not re.search(r"\d", password):
            errores.append(ValidationError("La contraseña tiene que incluir al menos un número.", code="sin_numero"))
        if not re.search(r"[^\w\s]|_", password):
            errores.append(ValidationError("La contraseña tiene que incluir al menos un carácter especial.", code="sin_especial"))
        if errores:
            raise ValidationError(errores)

    def get_help_text(self):
        return (
            f"La contraseña tiene que tener al menos {MINIMO} caracteres, con una mayúscula, "
            "una minúscula, un número y un carácter especial."
        )
