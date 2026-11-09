"""Cierre del expediente con valoración, archivo y anulación (HU-13, HU-14)."""
from django.db import transaction
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import auditoria
from ..models import Cierre, Documento, Siniestro
from ..motor import recalcular_vinculados
from ..permisos import siniestro_asignado
from ..serializadores import cierre_json


MENSAJE_RESPALDO = (
    "Una irregularidad confirmada necesita respaldo: adjuntá al menos un documento del expediente o escribí una observación."
)


class CierreEntrada(serializers.Serializer):
    """Datos del cierre. Recibe el siniestro en el contexto para validar los documentos de respaldo."""

    resultado_reclamo = serializers.ChoiceField(
        choices=[r for r, _ in Cierre.RESULTADOS],
        error_messages={"required": "El resultado del reclamo es obligatorio.",
                        "invalid_choice": "El resultado tiene que ser aprobado, rechazado, desistido u otra_finalizacion."},
    )
    irregularidad = serializers.BooleanField(required=False, default=False)
    conclusion = serializers.CharField(
        trim_whitespace=True,
        error_messages={"required": "La conclusión es obligatoria.", "blank": "La conclusión es obligatoria.",
                        "null": "La conclusión es obligatoria."},
    )
    valoracion = serializers.IntegerField(error_messages={
        "required": "La valoración es obligatoria.", "invalid": "La valoración tiene que ser un número entero entre 1 y 10."})
    justificacion = serializers.CharField(
        max_length=500, trim_whitespace=True,
        error_messages={"required": "La justificación es obligatoria.", "blank": "La justificación es obligatoria.",
                        "null": "La justificación es obligatoria.",
                        "max_length": "La justificación no puede superar los 500 caracteres."},
    )
    motivo_cambio = serializers.CharField(required=False, allow_blank=True, default="")
    documentos_respaldo = serializers.ListField(
        child=serializers.IntegerField(error_messages={"invalid": "Los documentos de respaldo se indican por su número."}),
        required=False, default=list,
        error_messages={"not_a_list": "Los documentos de respaldo tienen que ser una lista."},
    )
    observacion_respaldo = serializers.CharField(
        max_length=500, required=False, allow_blank=True, default="", trim_whitespace=True,
        error_messages={"max_length": "La observación no puede superar los 500 caracteres."},
    )

    def validate_valoracion(self, valor):
        if not 1 <= valor <= 10:
            raise serializers.ValidationError("La valoración tiene que estar entre 1 y 10.")
        return valor

    def validate(self, datos):
        ids = list(dict.fromkeys(datos.get("documentos_respaldo") or []))
        if ids and Documento.objects.filter(siniestro=self.context["siniestro"], pk__in=ids).count() != len(ids):
            raise serializers.ValidationError({"documentos_respaldo": ["Algún documento no pertenece a este expediente."]})
        datos["documentos_respaldo"] = ids
        if datos["irregularidad"] and not ids and not datos.get("observacion_respaldo"):
            raise serializers.ValidationError({"respaldo": [MENSAJE_RESPALDO]})
        return datos


class CierreDelSiniestro(APIView):
    def get(self, solicitud, pk):
        siniestro = siniestro_asignado(solicitud, pk, "ver_cierre")
        cierres = list(siniestro.cierres.select_related("perito").order_by("creado_en", "id"))
        return Response({
            "vigente": cierre_json(cierres[-1]) if cierres else None,
            "historial": [cierre_json(c) for c in cierres],
        })

    def post(self, solicitud, pk):
        siniestro = siniestro_asignado(solicitud, pk, "cierre")
        entrada = CierreEntrada(data=solicitud.data, context={"siniestro": siniestro})
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
            recalculados = recalcular_vinculados(siniestro, "antecedente_cerrado")
            auditoria.registrar(
                solicitud.user, "cambio_valoracion" if es_cambio else "cierre", f"siniestro:{siniestro.pk}",
                siniestro_origen=siniestro,
                detalle={"cierre": cierre.pk, "valoracion": cierre.valoracion, "casos_recalculados": [e.siniestro_id for e in recalculados]},
            )
        return Response(cierre_json(cierre), status=201)


class Archivar(APIView):
    def post(self, solicitud, pk):
        siniestro = siniestro_asignado(solicitud, pk, "archivar")
        if siniestro.estado != Siniestro.CERRADO:
            raise serializers.ValidationError({"detalle": "Solo un expediente cerrado se puede archivar."})
        with transaction.atomic():
            siniestro.estado = Siniestro.ARCHIVADO
            siniestro.save(update_fields=["estado", "actualizado_en"])
            recalculados = recalcular_vinculados(siniestro, "antecedente_archivado")
            auditoria.registrar(solicitud.user, "archivar", f"siniestro:{siniestro.pk}", siniestro_origen=siniestro,
                                detalle={"casos_recalculados": [e.siniestro_id for e in recalculados]})
        return Response({"id": siniestro.pk, "estado": siniestro.estado})


class AnularEntrada(serializers.Serializer):
    motivo = serializers.CharField(error_messages={"required": "El motivo de la anulación es obligatorio.",
                                                    "blank": "El motivo de la anulación es obligatorio."})


class Anular(APIView):
    """Anulación por carga errónea: no borra nada, pero el caso deja de contar como antecedente."""

    def post(self, solicitud, pk):
        siniestro = siniestro_asignado(solicitud, pk, "anular")
        entrada = AnularEntrada(data=solicitud.data)
        entrada.is_valid(raise_exception=True)
        if siniestro.estado == Siniestro.ANULADO:
            raise serializers.ValidationError({"detalle": "El expediente ya está anulado."})
        # solo un caso confirmado contaba como antecedente: anular un borrador no cambia la evaluación de nadie
        contaba = siniestro.confirmado_en is not None and siniestro.estado in Siniestro.ESTADOS_VALIDOS_COMO_ANTECEDENTE
        with transaction.atomic():
            siniestro.estado = Siniestro.ANULADO
            siniestro.motivo_anulacion = entrada.validated_data["motivo"].strip()
            siniestro.save(update_fields=["estado", "motivo_anulacion", "actualizado_en"])
            recalculados = recalcular_vinculados(siniestro, "antecedente_anulado") if contaba else []
            auditoria.registrar(solicitud.user, "anular", f"siniestro:{siniestro.pk}", siniestro_origen=siniestro,
                                detalle={"motivo": siniestro.motivo_anulacion, "casos_recalculados": [e.siniestro_id for e in recalculados]})
        return Response({"id": siniestro.pk, "estado": siniestro.estado, "motivo_anulacion": siniestro.motivo_anulacion})
