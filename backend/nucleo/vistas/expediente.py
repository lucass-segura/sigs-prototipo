"""Contenido privado del expediente: documentos, notas y tareas (HU-05, HU-06, HU-07). Solo del perito responsable."""
import os
import uuid
from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import auditoria
from ..models import Documento, Nota, Tarea, TareaCambio, Usuario
from ..permisos import exigir_responsable, no_encontrado, prohibido, siniestro_del_espacio
from ..serializadores import persona_simple


def _del_responsable(solicitud, pk, accion):
    """Siniestro del espacio (404 si no) y exige ser el perito responsable (403 si no)."""
    siniestro = siniestro_del_espacio(solicitud, pk, accion)
    exigir_responsable(solicitud, siniestro, accion)
    return siniestro


# --------------------------------------------------------------------------
# Documentos
# --------------------------------------------------------------------------
def documento_json(documento):
    return {
        "id": documento.id,
        "tipo": documento.tipo,
        "nombre_original": documento.nombre_original,
        "estado": documento.estado,
        "recibido_en": documento.recibido_en,
        "tamanio": documento.tamanio,
    }


class Documentos(APIView):
    def get(self, solicitud, pk):
        siniestro = _del_responsable(solicitud, pk, "listar_documentos")
        return Response([documento_json(d) for d in siniestro.documentos.order_by("-recibido_en", "-id")])

    def post(self, solicitud, pk):
        siniestro = _del_responsable(solicitud, pk, "subir_documento")
        tipo = str(solicitud.data.get("tipo", "")).strip()
        archivo = solicitud.FILES.get("archivo")
        errores = {}
        if not tipo:
            errores["tipo"] = ["El tipo de documento es obligatorio."]
        if archivo is None:
            errores["archivo"] = ["Falta el archivo."]
        elif archivo.size == 0:
            errores["archivo"] = ["El archivo está vacío."]
        elif archivo.size > settings.DOCUMENTO_TAMANIO_MAXIMO:
            errores["archivo"] = [f"El archivo supera los {settings.DOCUMENTO_TAMANIO_MAXIMO // (1024 * 1024)} MB."]
        if errores:
            raise serializers.ValidationError(errores)
        # El nombre en disco es un UUID: el nombre original nunca forma parte de la ruta.
        carpeta = Path(settings.DOCUMENTOS_DIR) / str(siniestro.pk)
        carpeta.mkdir(parents=True, exist_ok=True)
        nombre = uuid.uuid4().hex
        with open(carpeta / nombre, "wb") as destino:
            for trozo in archivo.chunks():
                destino.write(trozo)
        documento = Documento.objects.create(
            siniestro=siniestro, tipo=tipo[:60], archivo_ref=f"{siniestro.pk}/{nombre}", estado="recibido",
            nombre_original=os.path.basename(archivo.name or "")[:250], tipo_contenido=(archivo.content_type or "")[:120],
            tamanio=archivo.size, subido_por=solicitud.user,
        )
        auditoria.registrar(solicitud.user, "subir_documento", f"documento:{documento.pk}", siniestro_origen=siniestro)
        return Response(documento_json(documento), status=201)


class DescargarDocumento(APIView):
    """Descarga con verificación de permiso. Para cualquiera que no sea el responsable el documento «no existe»."""

    def get(self, solicitud, pk):
        accion = "descargar_documento"
        documento = Documento.objects.select_related("siniestro").filter(pk=pk).first()
        usuario = solicitud.user
        if (
            documento is None
            or usuario.rol != Usuario.PERITO
            or documento.siniestro.espacio_id != usuario.espacio_id
            or documento.siniestro.perito_id != usuario.id
        ):
            raise no_encontrado("No se encontró el documento.", accion, f"documento:{pk}")
        base = Path(settings.DOCUMENTOS_DIR).resolve()
        ruta = (base / documento.archivo_ref).resolve()
        if base not in ruta.parents or not ruta.is_file():
            raise no_encontrado("No se encontró el documento.", accion, f"documento:{pk}")
        auditoria.registrar(usuario, accion, f"documento:{documento.pk}", siniestro_origen=documento.siniestro)
        respuesta = FileResponse(
            open(ruta, "rb"), as_attachment=True, filename=documento.nombre_original or f"documento-{documento.pk}",
            content_type=documento.tipo_contenido or "application/octet-stream",
        )
        respuesta["X-Content-Type-Options"] = "nosniff"
        return respuesta


# --------------------------------------------------------------------------
# Notas
# --------------------------------------------------------------------------
def nota_json(nota):
    return {"id": nota.id, "texto": nota.texto, "creada_en": nota.creada_en, "autor": persona_simple(nota.autor)}


class NotaEntrada(serializers.Serializer):
    texto = serializers.CharField(error_messages={"required": "La nota no puede estar vacía.", "blank": "La nota no puede estar vacía."})


class Notas(APIView):
    def get(self, solicitud, pk):
        siniestro = _del_responsable(solicitud, pk, "listar_notas")
        return Response([nota_json(n) for n in siniestro.notas.select_related("autor").order_by("-creada_en", "-id")])

    def post(self, solicitud, pk):
        siniestro = _del_responsable(solicitud, pk, "crear_nota")
        entrada = NotaEntrada(data=solicitud.data)
        entrada.is_valid(raise_exception=True)
        nota = Nota.objects.create(siniestro=siniestro, autor=solicitud.user, texto=entrada.validated_data["texto"].strip())
        auditoria.registrar(solicitud.user, "crear_nota", f"nota:{nota.pk}", siniestro_origen=siniestro)
        return Response(nota_json(nota), status=201)


# --------------------------------------------------------------------------
# Tareas
# --------------------------------------------------------------------------
def tarea_json(tarea):
    return {
        "id": tarea.id,
        "titulo": tarea.titulo,
        "estado": tarea.estado,
        "vence_en": tarea.vence_en,
        "creada_en": tarea.creada_en,
        "cambios": [
            {
                "estado_anterior": c.estado_anterior,
                "estado_nuevo": c.estado_nuevo,
                "fecha": c.fecha,
                "usuario": persona_simple(c.usuario),
            }
            for c in tarea.cambios.select_related("usuario").all()
        ],
    }


class TareaEntrada(serializers.Serializer):
    titulo = serializers.CharField(max_length=250, error_messages={
        "required": "El título de la tarea es obligatorio.", "blank": "El título de la tarea es obligatorio."})
    vence_en = serializers.DateField(required=False, allow_null=True, error_messages={"invalid": "La fecha de vencimiento no es válida."})


class CambioEstadoEntrada(serializers.Serializer):
    estado = serializers.ChoiceField(choices=[e for e, _ in Tarea.ESTADOS], error_messages={
        "required": "El estado es obligatorio.", "invalid_choice": "El estado tiene que ser pendiente, en_curso o hecha."})


class Tareas(APIView):
    def get(self, solicitud, pk):
        siniestro = _del_responsable(solicitud, pk, "listar_tareas")
        return Response([tarea_json(t) for t in siniestro.tareas.order_by("id")])

    def post(self, solicitud, pk):
        siniestro = _del_responsable(solicitud, pk, "crear_tarea")
        entrada = TareaEntrada(data=solicitud.data)
        entrada.is_valid(raise_exception=True)
        tarea = Tarea.objects.create(siniestro=siniestro, estado=Tarea.PENDIENTE, **entrada.validated_data)
        auditoria.registrar(solicitud.user, "crear_tarea", f"tarea:{tarea.pk}", siniestro_origen=siniestro)
        return Response(tarea_json(tarea), status=201)


class DetalleTarea(APIView):
    def patch(self, solicitud, pk):
        accion = "cambiar_estado_tarea"
        usuario = solicitud.user
        if usuario.rol != Usuario.PERITO:
            raise prohibido("Solo un perito puede acceder a los expedientes.", accion, f"tarea:{pk}")
        tarea = Tarea.objects.select_related("siniestro").filter(pk=pk).first()
        if tarea is None or tarea.siniestro.espacio_id != usuario.espacio_id:
            raise no_encontrado("No se encontró la tarea.", accion, f"tarea:{pk}")
        exigir_responsable(solicitud, tarea.siniestro, accion)
        entrada = CambioEstadoEntrada(data=solicitud.data)
        entrada.is_valid(raise_exception=True)
        nuevo = entrada.validated_data["estado"]
        if nuevo != tarea.estado:
            TareaCambio.objects.create(tarea=tarea, estado_anterior=tarea.estado, estado_nuevo=nuevo, usuario=usuario, fecha=timezone.now())
            tarea.estado = nuevo
            tarea.save(update_fields=["estado"])
            auditoria.registrar(
                usuario, accion, f"tarea:{tarea.pk}", siniestro_origen=tarea.siniestro, detalle={"estado_nuevo": nuevo}
            )
        return Response(tarea_json(tarea))


class MisTareas(APIView):
    """Tareas no hechas de los expedientes propios."""

    def get(self, solicitud):
        from ..permisos import exigir_perito

        usuario = exigir_perito(solicitud, "listar_tareas")
        tareas = (
            Tarea.objects.filter(siniestro__perito=usuario).exclude(estado=Tarea.HECHA)
            .select_related("siniestro").order_by("vence_en", "id")
        )
        # las que no tienen vencimiento van al final
        tareas = sorted(tareas, key=lambda t: (t.vence_en is None, t.vence_en, t.id))
        cuerpo = []
        for t in tareas:
            datos = tarea_json(t)
            datos["siniestro"] = {"id": t.siniestro_id, "numero_expediente": t.siniestro.numero_expediente, "tipo": t.siniestro.tipo}
            cuerpo.append(datos)
        return Response(cuerpo)
