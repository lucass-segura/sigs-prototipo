"""Expediente del perito: registro, confirmación, panel, análisis, coincidencias y resumen (HU-03, 04, 08–11, 16)."""
from datetime import datetime, time, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import auditoria
from ..coincidencias import resultados_de_coincidencias
from ..expediente import (
    crear_siniestro_con_datos,
    fecha_local,
    guardar_poliza,
    reemplazar_bienes,
    reemplazar_personas,
)
from ..models import Bien, BienAfectado, Cierre, Evaluacion, Participacion, Persona, Siniestro, Tarea
from ..motor import guardar_evaluacion, recalcular_vinculados, resultado_de_evaluacion
from ..permisos import (
    exigir_confirmado,
    exigir_perito,
    exigir_responsable,
    no_encontrado,
    siniestro_del_espacio,
)
from ..resumen import construir_resumen
from ..serializadores import siniestro_json

MENSAJE_CONFIRMAR = "Para confirmar hacen falta la póliza, la fecha del hecho y al menos una persona o un bien."
PRIORIDAD_ORDEN = {"alta": 0, "media": 1, "baja": 2}


# --------------------------------------------------------------------------
# Entradas
# --------------------------------------------------------------------------
class FechaOpcional(serializers.DateField):
    """Fecha ISO; la cadena vacía se toma como «sin dato»."""

    def run_validation(self, data=serializers.empty):
        if data == "":
            data = None
        return super().run_validation(data)


class FechaHoraFlexible(serializers.DateTimeField):
    """Fecha y hora ISO. Si llega solo la fecha, se toma el mediodía local."""

    def to_internal_value(self, valor):
        if isinstance(valor, str):
            solo_fecha = parse_date(valor.strip()) if len(valor.strip()) == 10 else None
            if solo_fecha:
                valor = timezone.make_aware(datetime.combine(solo_fecha, time(12, 0))).isoformat()
        return super().to_internal_value(valor)


class PolizaEntrada(serializers.Serializer):
    numero = serializers.CharField(max_length=60, allow_blank=True, required=False, default="")
    compania = serializers.CharField(max_length=150, allow_blank=True, required=False, default="")
    cobertura = serializers.CharField(max_length=150, allow_blank=True, required=False, default="")
    inicio_vigencia = FechaOpcional(required=False, allow_null=True, default=None,
                                    error_messages={"invalid": "El inicio de vigencia no tiene un formato de fecha válido."})
    primer_pago = FechaOpcional(required=False, allow_null=True, default=None,
                                error_messages={"invalid": "La fecha del primer pago no tiene un formato válido."})


class PersonaEntrada(serializers.Serializer):
    tipo_identificador = serializers.ChoiceField(choices=[t for t, _ in Persona.TIPOS], default=Persona.DNI)
    identificador = serializers.CharField(max_length=40, error_messages={
        "required": "El identificador de la persona es obligatorio.", "blank": "El identificador de la persona es obligatorio."})
    nombre = serializers.CharField(max_length=150, allow_blank=True, required=False, default="")
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=[r for r, _ in Participacion.ROLES], error_messages={"invalid_choice": "El rol no es válido."}),
        allow_empty=False, error_messages={"required": "Indicá al menos un rol para la persona.", "empty": "Indicá al menos un rol para la persona."},
    )


class BienEntrada(serializers.Serializer):
    tipo = serializers.ChoiceField(choices=[t for t, _ in Bien.TIPOS], default="otro")
    identificador = serializers.CharField(max_length=60, error_messages={
        "required": "El identificador del bien es obligatorio.", "blank": "El identificador del bien es obligatorio."})
    descripcion = serializers.CharField(max_length=250, allow_blank=True, required=False, default="")
    detalle_dano = serializers.CharField(allow_blank=True, required=False, default="")
    atributos = serializers.DictField(required=False, default=dict)


class SiniestroEntrada(serializers.Serializer):
    numero_expediente = serializers.CharField(max_length=40, required=False, allow_blank=True)
    poliza = PolizaEntrada(required=False, allow_null=True)
    tipo = serializers.CharField(max_length=150, required=False, allow_blank=True)
    fecha_hecho = FechaHoraFlexible(error_messages={
        "required": "La fecha del hecho es obligatoria.", "null": "La fecha del hecho es obligatoria.",
        "invalid": "La fecha del hecho no tiene un formato válido."})
    fecha_denuncia = FechaOpcional(required=False, allow_null=True,
                                   error_messages={"invalid": "La fecha de denuncia no tiene un formato válido."})
    lugar = serializers.CharField(max_length=250, required=False, allow_blank=True)
    relato = serializers.CharField(required=False, allow_blank=True)
    personas = PersonaEntrada(many=True, required=False)
    bienes = BienEntrada(many=True, required=False)
    confirmar = serializers.BooleanField(required=False, default=False)


def _validar_entrada(solicitud, parcial):
    entrada = SiniestroEntrada(data=solicitud.data, partial=parcial)
    entrada.is_valid(raise_exception=True)
    return entrada.validated_data


def _requisitos_de_confirmacion(poliza, hay_personas_o_bienes):
    if poliza is None or not hay_personas_o_bienes:
        raise serializers.ValidationError({"detalle": MENSAJE_CONFIRMAR})


# --------------------------------------------------------------------------
# Panel y alta
# --------------------------------------------------------------------------
def _panel(usuario):
    siniestros = list(Siniestro.objects.filter(perito=usuario).order_by("-fecha_hecho", "-id"))
    ids = [s.pk for s in siniestros]
    ultimas = {
        e.siniestro_id: e
        for e in Evaluacion.objects.filter(siniestro_id__in=ids).order_by("siniestro_id", "-creada_en", "-id").distinct("siniestro_id")
    }
    bien_principal = {}
    for a in BienAfectado.objects.filter(siniestro_id__in=ids).select_related("bien").order_by("-id"):
        bien_principal[a.siniestro_id] = a.bien.identificador_norm
    pendientes = dict(
        Tarea.objects.filter(siniestro_id__in=ids).exclude(estado=Tarea.HECHA)
        .values_list("siniestro_id").annotate(total=Count("id")).values_list("siniestro_id", "total")
    )
    items = []
    for s in siniestros:
        evaluacion = ultimas.get(s.pk)
        items.append({
            "id": s.pk,
            "numero_expediente": s.numero_expediente,
            "tipo": s.tipo,
            "fecha_hecho": s.fecha_hecho,
            "estado": s.estado,
            "bien_principal": bien_principal.get(s.pk),
            "prioridad": evaluacion.prioridad if evaluacion else None,
            "puntaje": evaluacion.puntaje if evaluacion else None,
            "tareas_pendientes": pendientes.get(s.pk, 0),
        })
    # prioridad de la última evaluación (alta, media, baja, sin evaluar) y luego fecha del hecho descendente
    items.sort(key=lambda i: i["fecha_hecho"], reverse=True)
    items.sort(key=lambda i: PRIORIDAD_ORDEN.get(i["prioridad"], 3))
    hoy = fecha_local(timezone.now())
    inicio_mes = timezone.make_aware(datetime.combine(hoy.replace(day=1), time.min))
    resumen = {
        "en_analisis": sum(1 for i in items if i["estado"] == Siniestro.EN_ANALISIS),
        "prioridad_alta": sum(1 for i in items if i["estado"] == Siniestro.EN_ANALISIS and i["prioridad"] == "alta"),
        "tareas_vencen_semana": Tarea.objects.filter(siniestro_id__in=ids, vence_en__gte=hoy, vence_en__lte=hoy + timedelta(days=7))
        .exclude(estado=Tarea.HECHA).count(),
        "cerrados_mes": Cierre.objects.filter(siniestro_id__in=ids, creado_en__gte=inicio_mes).values("siniestro_id").distinct().count(),
    }
    return {"resultados": items, "resumen": resumen}


class Siniestros(APIView):
    def get(self, solicitud):
        usuario = exigir_perito(solicitud, "listar_siniestros")
        return Response(_panel(usuario))

    def post(self, solicitud):
        usuario = exigir_perito(solicitud, "crear_siniestro")
        datos = _validar_entrada(solicitud, parcial=False)
        confirmar = datos.pop("confirmar", False)
        if confirmar:
            _requisitos_de_confirmacion(datos.get("poliza"), bool(datos.get("personas") or datos.get("bienes")))
        numero = (datos.pop("numero_expediente", "") or "").strip() or None
        if numero and Siniestro.objects.filter(numero_expediente=numero).exists():
            raise serializers.ValidationError({"numero_expediente": ["Ya existe un expediente con ese número."]})
        try:
            with transaction.atomic():
                siniestro = crear_siniestro_con_datos(
                    perito=usuario, numero_expediente=numero, poliza=datos.pop("poliza", None),
                    personas=datos.pop("personas", []), bienes=datos.pop("bienes", []), **datos,
                )
                auditoria.registrar(usuario, "crear_siniestro", f"siniestro:{siniestro.pk}", siniestro_origen=siniestro)
                if confirmar:
                    _confirmar(usuario, siniestro)
        except IntegrityError:
            raise serializers.ValidationError({"numero_expediente": ["Ya existe un expediente con ese número."]})
        siniestro.refresh_from_db()
        return Response(siniestro_json(siniestro, usuario), status=201)


def _confirmar(usuario, siniestro):
    """Pasa a `en_analisis`, guarda `confirmado_en`, evalúa y recalcula los casos vinculados."""
    siniestro.estado = Siniestro.EN_ANALISIS
    siniestro.confirmado_en = timezone.now()
    siniestro.save(update_fields=["estado", "confirmado_en", "actualizado_en"])
    evaluacion = guardar_evaluacion(siniestro, "confirmacion")
    recalculados = recalcular_vinculados(siniestro)
    auditoria.registrar(
        usuario, "confirmar_siniestro", f"siniestro:{siniestro.pk}", siniestro_origen=siniestro,
        detalle={"evaluacion": evaluacion.pk, "casos_recalculados": [e.siniestro_id for e in recalculados]},
    )


# --------------------------------------------------------------------------
# Detalle, edición y confirmación
# --------------------------------------------------------------------------
class DetalleSiniestro(APIView):
    def get(self, solicitud, pk):
        siniestro = siniestro_del_espacio(solicitud, pk, "ver_expediente")
        auditoria.registrar(solicitud.user, "ver_expediente", f"siniestro:{siniestro.pk}", siniestro_origen=siniestro)
        return Response(siniestro_json(siniestro, solicitud.user))

    def patch(self, solicitud, pk):
        siniestro = siniestro_del_espacio(solicitud, pk, "modificar_siniestro")
        exigir_responsable(solicitud, siniestro, "modificar_siniestro")
        if siniestro.estado != Siniestro.BORRADOR:
            raise serializers.ValidationError({"detalle": "Solo un borrador se puede editar."})
        datos = _validar_entrada(solicitud, parcial=True)
        datos.pop("confirmar", None)
        numero = (datos.pop("numero_expediente", None) or "").strip()
        if numero and numero != siniestro.numero_expediente:
            if Siniestro.objects.filter(numero_expediente=numero).exists():
                raise serializers.ValidationError({"numero_expediente": ["Ya existe un expediente con ese número."]})
            siniestro.numero_expediente = numero
        with transaction.atomic():
            if "poliza" in datos:
                siniestro.poliza = guardar_poliza(datos.pop("poliza"), siniestro.poliza)
            personas, bienes = datos.pop("personas", None), datos.pop("bienes", None)
            for campo, valor in datos.items():
                setattr(siniestro, campo, valor)
            siniestro.save()
            if personas is not None:
                reemplazar_personas(siniestro, personas)
            if bienes is not None:
                reemplazar_bienes(siniestro, bienes)
            auditoria.registrar(solicitud.user, "modificar_siniestro", f"siniestro:{siniestro.pk}", siniestro_origen=siniestro)
        siniestro.refresh_from_db()
        return Response(siniestro_json(siniestro, solicitud.user))


class Confirmar(APIView):
    def post(self, solicitud, pk):
        siniestro = siniestro_del_espacio(solicitud, pk, "confirmar_siniestro")
        exigir_responsable(solicitud, siniestro, "confirmar_siniestro")
        if siniestro.estado != Siniestro.BORRADOR:
            raise serializers.ValidationError({"detalle": "Solo un borrador se puede confirmar."})
        hay_vinculos = Participacion.objects.filter(siniestro=siniestro).exists() or BienAfectado.objects.filter(siniestro=siniestro).exists()
        _requisitos_de_confirmacion(siniestro.poliza, hay_vinculos)
        with transaction.atomic():
            _confirmar(solicitud.user, siniestro)
        siniestro.refresh_from_db()
        return Response(siniestro_json(siniestro, solicitud.user))


# --------------------------------------------------------------------------
# Análisis: evaluación, coincidencias y resumen
# --------------------------------------------------------------------------
class UltimaEvaluacion(APIView):
    def get(self, solicitud, pk):
        siniestro = siniestro_del_espacio(solicitud, pk, "ver_evaluacion")
        exigir_confirmado(solicitud, siniestro, "ver_evaluacion")
        evaluacion = siniestro.evaluaciones.select_related("conjunto").order_by("-creada_en", "-id").first()
        if evaluacion is None:
            raise no_encontrado("El siniestro todavía no tiene evaluación.", "ver_evaluacion", f"siniestro:{siniestro.pk}", siniestro.pk)
        return Response(resultado_de_evaluacion(evaluacion))


class Evaluaciones(APIView):
    def get(self, solicitud, pk):
        siniestro = siniestro_del_espacio(solicitud, pk, "ver_evaluaciones")
        exigir_confirmado(solicitud, siniestro, "ver_evaluaciones")
        evaluaciones = siniestro.evaluaciones.select_related("conjunto").order_by("-creada_en", "-id")
        return Response([
            {"id": e.pk, "version": e.conjunto.version, "creada_en": e.creada_en, "motivo": e.motivo,
             "puntaje": e.puntaje, "prioridad": e.prioridad}
            for e in evaluaciones
        ])


class Recalcular(APIView):
    def post(self, solicitud, pk):
        siniestro = siniestro_del_espacio(solicitud, pk, "recalcular")
        exigir_responsable(solicitud, siniestro, "recalcular")
        exigir_confirmado(solicitud, siniestro, "recalcular")
        evaluacion = guardar_evaluacion(siniestro, "recalculo")
        auditoria.registrar(solicitud.user, "recalcular", f"siniestro:{siniestro.pk}", siniestro_origen=siniestro,
                            detalle={"evaluacion": evaluacion.pk})
        return Response(resultado_de_evaluacion(evaluacion))


class Coincidencias(APIView):
    def get(self, solicitud, pk):
        siniestro = siniestro_del_espacio(solicitud, pk, "ver_coincidencias")
        exigir_confirmado(solicitud, siniestro, "ver_coincidencias")
        try:
            pagina = int(solicitud.query_params.get("pagina", 1))
        except ValueError:
            pagina = 1
        cuerpo = resultados_de_coincidencias(siniestro, pagina)
        auditoria.registrar(solicitud.user, "ver_coincidencias", f"siniestro:{siniestro.pk}", siniestro_origen=siniestro,
                            detalle={"total": cuerpo["total"]})
        return Response(cuerpo)


class ResumenAntecedente(APIView):
    def get(self, solicitud, pk, antecedente_pk):
        accion = "ver_resumen_antecedente"
        origen = siniestro_del_espacio(solicitud, pk, accion)
        exigir_confirmado(solicitud, origen, accion)
        resumen = construir_resumen(origen, antecedente_pk)
        if resumen is None:
            raise no_encontrado(
                "El antecedente no coincide con el siniestro de origen.", accion, f"siniestro:{antecedente_pk}", origen.pk
            )
        auditoria.registrar(solicitud.user, accion, f"siniestro:{antecedente_pk}", siniestro_origen=origen)
        return Response(resumen)
