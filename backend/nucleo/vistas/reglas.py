"""Reglas del indicador: lectura para todos y publicación de versiones (solo superadministrador)."""
from django.db import IntegrityError, transaction
from django.utils.dateparse import parse_date
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import auditoria
from ..models import ConjuntoReglas, Usuario
from ..motor import recalcular_en_analisis
from ..permisos import exigir_rol, no_encontrado
from ..reglas import ESQUEMAS, conjunto_json, publicar_version, resumen_de_version, validar_parametros, validar_puntos_maximos, validar_topes


class Reglas(APIView):
    def get(self, solicitud):
        vigente = ConjuntoReglas.objects.get(activo=True)
        versiones = ConjuntoReglas.objects.order_by("-creado_en", "-id")
        return Response({"vigente": conjunto_json(vigente), "versiones": [resumen_de_version(v) for v in versiones]})


class DetalleVersion(APIView):
    def get(self, solicitud, pk):
        conjunto = ConjuntoReglas.objects.filter(pk=pk).first()
        if conjunto is None:
            raise no_encontrado("No se encontró la versión de reglas.", "ver_version_reglas", f"conjunto:{pk}")
        return Response(conjunto_json(conjunto))


class PublicarVersion(APIView):
    def post(self, solicitud):
        accion = "publicar_version_reglas"
        usuario = exigir_rol(
            solicitud, (Usuario.SUPERADMINISTRADOR,), "Solo el superadministrador publica versiones de reglas.", accion
        )
        datos = solicitud.data if isinstance(solicitud.data, dict) else {}
        errores = {}
        version = datos.get("version")
        if not isinstance(version, str) or not version.strip():
            errores["version"] = ["La versión es obligatoria."]
        elif len(version.strip()) > 20:
            errores["version"] = ["La versión no puede superar los 20 caracteres."]
        elif ConjuntoReglas.objects.filter(version=version.strip()).exists():
            errores["version"] = ["Ya existe una versión con ese nombre."]
        desde = parse_date(datos["vigente_desde"]) if isinstance(datos.get("vigente_desde"), str) else None
        if desde is None:
            errores["vigente_desde"] = ["La fecha de vigencia no es válida (AAAA-MM-DD)."]
        reglas = datos.get("reglas", {})
        mensajes_reglas = []
        if not isinstance(reglas, dict):
            mensajes_reglas.append("Las reglas tienen que ser un objeto con el código de cada regla.")
            reglas = {}
        for codigo, cambio in reglas.items():
            if codigo not in ESQUEMAS:
                mensajes_reglas.append(f"La regla {codigo} no existe.")
            elif not isinstance(cambio, dict):
                mensajes_reglas.append(f"El cambio de {codigo} tiene que ser un objeto.")
            else:
                if "parametros" in cambio:
                    mensajes_reglas.extend(validar_parametros(codigo, cambio["parametros"]))
                if "puntos_max" in cambio and (
                    not isinstance(cambio["puntos_max"], int) or isinstance(cambio["puntos_max"], bool) or cambio["puntos_max"] < 0
                ):
                    mensajes_reglas.append(f"Los puntos máximos de {codigo} tienen que ser un entero no negativo.")
        vigente = ConjuntoReglas.objects.get(activo=True)
        if not mensajes_reglas:
            # los puntos de cada nivel no pueden pasar de `puntos_max` (el nuevo o, si no cambia, el vigente)
            vigentes = {r.codigo: r for r in vigente.reglas.all()}
            for codigo, cambio in reglas.items():
                actual = vigentes[codigo]
                mensajes_reglas.extend(validar_puntos_maximos(
                    codigo, cambio.get("parametros", actual.parametros), cambio.get("puntos_max", actual.puntos_max)
                ))
        if mensajes_reglas:
            errores["reglas"] = mensajes_reglas
        topes = datos.get("topes")
        if topes is not None:
            mensajes_topes = validar_topes(topes, list(vigente.topes["grupos"]))
            if mensajes_topes:
                errores["topes"] = mensajes_topes
        if errores:
            raise serializers.ValidationError(errores)
        try:
            with transaction.atomic():
                nuevo = publicar_version(vigente, version.strip(), desde, reglas, topes, usuario)
                recalculados = recalcular_en_analisis(nuevo)
        except IntegrityError:
            raise serializers.ValidationError({"version": ["Ya existe una versión con ese nombre."]})
        auditoria.registrar(
            usuario, accion, f"conjunto:{nuevo.pk}",
            detalle={"version": nuevo.version, "basada_en": vigente.version, "casos_recalculados": [e.siniestro_id for e in recalculados]},
        )
        return Response(conjunto_json(nuevo), status=201)
