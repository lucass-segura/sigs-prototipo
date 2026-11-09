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
from ..archivos import TEXTO, es_png, previsualizable_por_declaracion, tipo_para_servir_en_linea
from ..croquis import validar_escena
from ..models import Documento, Nota, Tarea, TareaCambio, Usuario
from ..permisos import exigir_perito, no_encontrado, prohibido, siniestro_asignado
from ..serializadores import persona_simple


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
        # Tipo seguro declarado al subir (la firma se comprueba al pedir la vista previa) o `None`.
        "previsualizable": previsualizable_por_declaracion(documento.tipo_contenido),
        # `true` si es un croquis del editor, que se puede reabrir (S29).
        "tiene_escena": documento.escena is not None,
    }


class Documentos(APIView):
    def get(self, solicitud, pk):
        siniestro = siniestro_asignado(solicitud, pk, "listar_documentos")
        return Response([documento_json(d) for d in siniestro.documentos.order_by("-recibido_en", "-id")])

    def post(self, solicitud, pk):
        siniestro = siniestro_asignado(solicitud, pk, "subir_documento")
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


def documento_propio(solicitud, pk, accion):
    """Documento y ruta del archivo, solo para el perito asignado. Para cualquier otro el documento «no existe»."""
    documento = Documento.objects.select_related("siniestro").filter(pk=pk).first()
    usuario = solicitud.user
    if documento is None or usuario.rol != Usuario.PERITO or documento.siniestro.perito_id != usuario.id:
        raise no_encontrado("No se encontró el documento.", accion, f"documento:{pk}")
    base = Path(settings.DOCUMENTOS_DIR).resolve()
    ruta = (base / documento.archivo_ref).resolve()
    if base not in ruta.parents or not ruta.is_file():
        raise no_encontrado("No se encontró el documento.", accion, f"documento:{pk}")
    return documento, ruta


class DescargarDocumento(APIView):
    """Descarga con verificación de permiso. Para cualquiera que no sea el responsable el documento «no existe»."""

    def get(self, solicitud, pk):
        accion = "descargar_documento"
        usuario = solicitud.user
        documento, ruta = documento_propio(solicitud, pk, accion)
        auditoria.registrar(usuario, accion, f"documento:{documento.pk}", siniestro_origen=documento.siniestro)
        respuesta = FileResponse(
            open(ruta, "rb"), as_attachment=True, filename=documento.nombre_original or f"documento-{documento.pk}",
            content_type=documento.tipo_contenido or "application/octet-stream",
        )
        respuesta["X-Content-Type-Options"] = "nosniff"
        return respuesta


class GuardarCroquis(APIView):
    """Guarda un croquis (S29): el PNG exportado es el archivo del documento y la escena JSON queda en `documento.escena`.

    Cada guardado crea un documento nuevo, también al editar uno existente (`basado_en`): nada se pisa.
    """

    def post(self, solicitud, pk):
        siniestro = siniestro_asignado(solicitud, pk, "subir_croquis")
        errores = {}
        imagen = solicitud.FILES.get("imagen")
        contenido = b""
        if imagen is None or imagen.size == 0:
            errores["imagen"] = ["Falta la imagen del croquis."]
        elif imagen.size > settings.CROQUIS_IMAGEN_MAXIMO:
            errores["imagen"] = [f"La imagen supera los {settings.CROQUIS_IMAGEN_MAXIMO // (1024 * 1024)} MB."]
        else:
            contenido = imagen.read()
            if not es_png(contenido):
                errores["imagen"] = ["La imagen del croquis tiene que ser un PNG."]
        escena = None
        try:
            escena = validar_escena(str(solicitud.data.get("escena", "")))
        except serializers.ValidationError as e:
            errores.update(e.detail)
        base = None
        crudo = solicitud.data.get("basado_en")
        if crudo not in (None, ""):
            try:
                base = Documento.objects.filter(pk=int(crudo), siniestro=siniestro, escena__isnull=False).first()
            except (TypeError, ValueError):
                base = None
            if base is None:
                errores["basado_en"] = ["El croquis original no existe en este expediente."]
        if errores:
            raise serializers.ValidationError(errores)
        carpeta = Path(settings.DOCUMENTOS_DIR) / str(siniestro.pk)
        carpeta.mkdir(parents=True, exist_ok=True)
        nombre = uuid.uuid4().hex
        (carpeta / nombre).write_bytes(contenido)
        ahora = timezone.now()
        documento = Documento.objects.create(
            siniestro=siniestro, tipo="Croquis", archivo_ref=f"{siniestro.pk}/{nombre}", estado="recibido", recibido_en=ahora,
            nombre_original=f"croquis-{timezone.localtime(ahora):%Y%m%d-%H%M%S}.png", tipo_contenido="image/png",
            tamanio=len(contenido), subido_por=solicitud.user, escena=escena,
        )
        detalle = {"basado_en": base.pk} if base else None
        auditoria.registrar(solicitud.user, "subir_croquis", f"documento:{documento.pk}", siniestro_origen=siniestro, detalle=detalle)
        return Response(documento_json(documento), status=201)


class EscenaDocumento(APIView):
    """Escena JSON de un croquis, para reabrirlo en el editor. Mismo permiso que la descarga."""

    def get(self, solicitud, pk):
        accion = "ver_escena_croquis"
        documento, _ = documento_propio(solicitud, pk, accion)
        if documento.escena is None:
            raise no_encontrado("Este documento no tiene una escena de croquis.", accion, f"documento:{pk}", documento.siniestro)
        auditoria.registrar(solicitud.user, accion, f"documento:{documento.pk}", siniestro_origen=documento.siniestro)
        respuesta = Response(documento.escena)
        respuesta["Cache-Control"] = "private, no-store"
        return respuesta


# Política de contenido de la vista previa: el archivo no puede ejecutar nada ni cargar recursos externos.
CSP_VISTA_PREVIA = "sandbox; default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"
# El visor de PDF del navegador no funciona dentro de un `sandbox`: se mantiene el resto de la política.
CSP_VISTA_PREVIA_PDF = "default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'"


class VerDocumento(APIView):
    """Vista previa en línea (S28): mismo permiso y auditoría que la descarga, solo para tipos seguros.

    El tipo se decide con el tipo guardado y con la firma del contenido. SVG, HTML, XML, scripts y todo lo demás se
    rechazan con 415 y quedan auditados: esos archivos solo se descargan como adjunto.
    """

    def get(self, solicitud, pk):
        accion = "ver_documento"
        usuario = solicitud.user
        documento, ruta = documento_propio(solicitud, pk, accion)
        tipo = tipo_para_servir_en_linea(documento.tipo_contenido, ruta)
        if tipo is None:
            auditoria.rechazar(usuario, accion, f"documento:{documento.pk}", documento.siniestro, {"estado": 415})
            respuesta = Response(
                {"detalle": "Este tipo de archivo no se puede previsualizar. Descargalo para verlo."}, status=415
            )
            respuesta["X-Content-Type-Options"] = "nosniff"
            return respuesta
        auditoria.registrar(usuario, accion, f"documento:{documento.pk}", siniestro_origen=documento.siniestro)
        respuesta = FileResponse(
            open(ruta, "rb"), as_attachment=False, filename=documento.nombre_original or f"documento-{documento.pk}",
            content_type="text/plain; charset=utf-8" if tipo == TEXTO else tipo,
        )
        respuesta["X-Content-Type-Options"] = "nosniff"
        respuesta["Content-Security-Policy"] = CSP_VISTA_PREVIA_PDF if tipo == "application/pdf" else CSP_VISTA_PREVIA
        respuesta["X-Frame-Options"] = "SAMEORIGIN"
        respuesta["Cache-Control"] = "private, no-store"
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
        siniestro = siniestro_asignado(solicitud, pk, "listar_notas")
        return Response([nota_json(n) for n in siniestro.notas.select_related("autor").order_by("-creada_en", "-id")])

    def post(self, solicitud, pk):
        siniestro = siniestro_asignado(solicitud, pk, "crear_nota")
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
        siniestro = siniestro_asignado(solicitud, pk, "listar_tareas")
        return Response([tarea_json(t) for t in siniestro.tareas.order_by("id")])

    def post(self, solicitud, pk):
        siniestro = siniestro_asignado(solicitud, pk, "crear_tarea")
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
        if tarea is None or tarea.siniestro.perito_id != usuario.id:
            raise no_encontrado("No se encontró la tarea.", accion, f"tarea:{pk}")
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
    """Tareas de los expedientes propios. Sin parámetros, solo las no hechas.

    `?estado=` acepta `pendiente`, `en_curso`, `hecha` o `todas` (S26).
    """

    def get(self, solicitud):
        usuario = exigir_perito(solicitud, "listar_tareas")
        estado = solicitud.query_params.get("estado")
        validos = [e for e, _ in Tarea.ESTADOS]
        if estado is not None and estado not in (*validos, "todas"):
            raise serializers.ValidationError({"estado": ["El estado tiene que ser pendiente, en_curso, hecha o todas."]})
        tareas = Tarea.objects.filter(siniestro__perito=usuario).select_related("siniestro")
        if estado in validos:
            tareas = tareas.filter(estado=estado)
        elif estado is None:
            tareas = tareas.exclude(estado=Tarea.HECHA)
        # las que no tienen vencimiento van al final
        tareas = sorted(tareas, key=lambda t: (t.vence_en is None, t.vence_en, t.id))
        cuerpo = []
        for t in tareas:
            datos = tarea_json(t)
            datos["siniestro"] = {"id": t.siniestro_id, "numero_expediente": t.siniestro.numero_expediente, "tipo": t.siniestro.tipo}
            cuerpo.append(datos)
        return Response(cuerpo)
