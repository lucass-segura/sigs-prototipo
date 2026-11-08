"""Normalización de identificadores (sección 6 del documento de especificación)."""
import re


def normalizar_identificador_persona(valor):
    """Sin puntos ni espacios y en mayúsculas: `30.111 017` → `30111017`."""
    return re.sub(r"[.\s]", "", str(valor or "")).upper()


def normalizar_identificador_bien(valor):
    """En mayúsculas y sin espacios, guiones ni puntos: `AB-123 CD` → `AB123CD`."""
    return re.sub(r"[\s.\-]", "", str(valor or "")).upper()
