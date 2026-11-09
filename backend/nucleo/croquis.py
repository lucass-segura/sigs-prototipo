"""Validación de la escena del croquis (S29).

La escena es el JSON con el que el editor del frontend vuelve a dibujar el croquis. El servidor no la interpreta,
pero la valida antes de guardarla: tamaño máximo, estructura cerrada (solo claves y tipos conocidos), números finitos
y acotados y textos cortos. Así nunca se guarda contenido arbitrario.
"""
import json
import math
import re

from django.conf import settings
from rest_framework import serializers

VERSION = 1
TIPOS_ELEMENTO = ("calle", "cruce", "curva", "rotonda", "vehiculo", "moto", "persona", "flecha", "impacto", "texto", "lapiz")
MAX_ELEMENTOS = 500
MAX_PUNTOS = 3000
LIMITE_COORDENADA = 20000
CLAVES_ESCENA = {"version", "ancho", "alto", "cuadricula", "leyenda", "norte", "elementos"}
CLAVES_ELEMENTO = {"id", "tipo", "x", "y", "rotacion", "escala", "etiqueta", "texto", "color", "puntos"}
COLOR = re.compile(r"^#[0-9a-fA-F]{3,8}$")


def _numero(valor, minimo, maximo):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor) and minimo <= valor <= maximo


def _error(mensaje):
    return serializers.ValidationError({"escena": [mensaje]})


def _validar_elemento(elemento, posicion):
    cuando = f"El elemento {posicion + 1} del croquis"
    if not isinstance(elemento, dict):
        raise _error(f"{cuando} no es válido.")
    if set(elemento) - CLAVES_ELEMENTO:
        raise _error(f"{cuando} tiene datos que no se admiten.")
    if elemento.get("tipo") not in TIPOS_ELEMENTO:
        raise _error(f"{cuando} tiene un tipo desconocido.")
    for eje in ("x", "y"):
        if not _numero(elemento.get(eje), -LIMITE_COORDENADA, LIMITE_COORDENADA):
            raise _error(f"{cuando} tiene una posición fuera de rango.")
    if "rotacion" in elemento and not _numero(elemento["rotacion"], -3600, 3600):
        raise _error(f"{cuando} tiene una rotación fuera de rango.")
    if "escala" in elemento and not _numero(elemento["escala"], 0.05, 20):
        raise _error(f"{cuando} tiene una escala fuera de rango.")
    for clave, largo in (("id", 40), ("etiqueta", 20), ("texto", 200)):
        if clave in elemento and (not isinstance(elemento[clave], str) or len(elemento[clave]) > largo):
            raise _error(f"{cuando} tiene un texto demasiado largo o inválido.")
    if "color" in elemento and (not isinstance(elemento["color"], str) or not COLOR.match(elemento["color"])):
        raise _error(f"{cuando} tiene un color inválido.")
    puntos = elemento.get("puntos")
    if elemento["tipo"] == "lapiz":
        if not isinstance(puntos, list) or not 1 <= len(puntos) <= MAX_PUNTOS:
            raise _error(f"{cuando} (lápiz) tiene que tener entre 1 y {MAX_PUNTOS} puntos.")
        for punto in puntos:
            if not (isinstance(punto, list) and len(punto) == 2 and all(_numero(c, -LIMITE_COORDENADA, LIMITE_COORDENADA) for c in punto)):
                raise _error(f"{cuando} (lápiz) tiene un punto inválido.")
    elif puntos is not None:
        raise _error(f"{cuando} no admite puntos.")


def validar_escena(texto):
    """Devuelve la escena (dict) o lanza `ValidationError({"escena": [...]})`."""
    if not texto:
        raise _error("Falta la escena del croquis.")
    if len(texto.encode("utf-8")) > settings.CROQUIS_ESCENA_MAXIMO:
        raise _error(f"La escena supera los {settings.CROQUIS_ESCENA_MAXIMO // 1024} KB.")
    try:
        # NaN e Infinity no son JSON válido: se rechazan.
        escena = json.loads(texto, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
    except (ValueError, RecursionError):
        raise _error("La escena no es un JSON válido.")
    if not isinstance(escena, dict) or set(escena) - CLAVES_ESCENA:
        raise _error("La escena no tiene el formato esperado.")
    if escena.get("version") != VERSION:
        raise _error("La versión de la escena no es compatible.")
    for clave in ("ancho", "alto"):
        valor = escena.get(clave)
        if not (isinstance(valor, int) and not isinstance(valor, bool) and 200 <= valor <= 4000):
            raise _error("El tamaño del croquis no es válido.")
    for clave in ("cuadricula", "leyenda", "norte"):
        if clave in escena and not isinstance(escena[clave], bool):
            raise _error("La escena no tiene el formato esperado.")
    elementos = escena.get("elementos")
    if not isinstance(elementos, list):
        raise _error("La escena no tiene el formato esperado.")
    if len(elementos) > MAX_ELEMENTOS:
        raise _error(f"El croquis no puede tener más de {MAX_ELEMENTOS} elementos.")
    for posicion, elemento in enumerate(elementos):
        _validar_elemento(elemento, posicion)
    return escena
