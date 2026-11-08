"""Cierre del expediente con valoración, archivo y anulación (HU-13, HU-14)."""
from django.db import transaction
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import auditoria
from ..models import Cierre, Siniestro
from ..permisos import siniestro_del_espacio, exigir_responsable
from ..serializadores import cierre_json


class CierreEntrada(serializers.Serializer):
    resultado_reclamo = serializers.ChoiceField(
        choices=[r for r, _ in Cierre.RESULTADOS],
        error_messages={"required": "El resultado del reclamo es obligatorio.",
                        "invalid_choice": "El resultado tiene que ser aprobado, rechazado, desistido u otra_finalizacion."},
    )
    irregularidad = serializers.BooleanField(required=False, default=False)
    conclusion = serializers.CharField(required=False, allow_blank=True, default="")
    valoracion = serializers.IntegerField(error_messages={
        "required": "La valoración es obligatoria.", "invalid": "La valoración tiene que ser un número entero entre 1 y 10."})
    justificacion = serializers.CharField(
        max_length=500, trim_whitespace=True,
        error_messages={"required": "La justificación es obligatoria.", "blank": "La justificación es obligatoria.",
                        "null": "La justificación es obligatoria.",
                        "max_length": "La justificación no puede superar los 500 caracteres."},
    )
    motivo_cambio = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_valoracion(self, valor):
        if not 1 <= valor <= 10:
            raise serializers.ValidationError("La valoración tiene que estar entre 1 y 10.")
        return valor


class CierreDelSiniestro(APIView):
    def get(self, solicitud, pk):
        siniestro = siniestro_del_espacio(solicitud, pk, "ver_cierre")
        cierres = list(siniestro.cierres.select_related("perito").order_by("creado_en", "id"))
        return Response({
            "vigente": cierre_json(cierres[-1]) if cierres else None,
            "historial": [cierre_json(c) for c in cierres],
        })

    def post(self, solicitud, pk):
        siniestro = siniestro_del_espacio(solicitud, pk, "cierre")
        exigir_responsable(solicitud, siniestro, "cierre")
        entrada = CierreEntrada(data=solicitud.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        datos["motivo_cambio"] = datos["motivo_cambio"].strip()
        es_cambio = siniestro.estado in (Siniestro.CERRADO, Siniestro.ARCHIVADO)
        if siniestro.estado == Siniestro.EN_ANALISIS:
            datos["motivo_cambio"] = ""
        elif es_cambio:
            if not datos["motivo_cambio"]:
                raise serializers.ValidationError({"motivo_cambio": ["El motivo del cambio es obligatorio."]})
        else:
            raise serializers.ValidationError({"detalle": "Solo se puede cerrar un expediente que está en análisis."})
        with transaction.atomic():
            cierre = Cierre.objects.create(siniestro=siniestro, perito=solicitud.user, **datos)
            if not es_cambio:
                siniestro.estado = Siniestro.CERRADO
                siniestro.save(update_fields=["estado", "actualizado_en"])
            auditoria.registrar(
                solicitud.user, "cambio_valoracion" if es_cambio else "cierre", f"siniestro:{siniestro.pk}",
                siniestro_origen=siniestro, detalle={"cierre": cierre.pk, "valoracion": cierre.valoracion},
            )
        return Response(cierre_json(cierre), status=201)


class Archivar(APIView):
    def post(self, solicitud, pk):
        siniestro = siniestro_del_espacio(solicitud, pk, "archivar")
        exigir_responsable(solicitud, siniestro, "archivar")
        if siniestro.estado != Siniestro.CERRADO:
            raise serializers.ValidationError({"detalle": "Solo un expediente cerrado se puede archivar."})
        siniestro.estado = Siniestro.ARCHIVADO
        siniestro.save(update_fields=["estado", "actualizado_en"])
        auditoria.registrar(solicitud.user, "archivar", f"siniestro:{siniestro.pk}", siniestro_origen=siniestro)
        return Response({"id": siniestro.pk, "estado": siniestro.estado})


class AnularEntrada(serializers.Serializer):
    motivo = serializers.CharField(error_messages={"required": "El motivo de la anulación es obligatorio.",
                                                    "blank": "El motivo de la anulación es obligatorio."})


class Anular(APIView):
    """Anulación por carga errónea: no borra nada, pero el caso deja de contar como antecedente."""

    def post(self, solicitud, pk):
        siniestro = siniestro_del_espacio(solicitud, pk, "anular")
        exigir_responsable(solicitud, siniestro, "anular")
        entrada = AnularEntrada(data=solicitud.data)
        entrada.is_valid(raise_exception=True)
        if siniestro.estado == Siniestro.ANULADO:
            raise serializers.ValidationError({"detalle": "El expediente ya está anulado."})
        siniestro.estado = Siniestro.ANULADO
        siniestro.motivo_anulacion = entrada.validated_data["motivo"].strip()
        siniestro.save(update_fields=["estado", "motivo_anulacion", "actualizado_en"])
        auditoria.registrar(solicitud.user, "anular", f"siniestro:{siniestro.pk}", siniestro_origen=siniestro,
                            detalle={"motivo": siniestro.motivo_anulacion})
        return Response({"id": siniestro.pk, "estado": siniestro.estado, "motivo_anulacion": siniestro.motivo_anulacion})
