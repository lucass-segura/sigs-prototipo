"""Administración: usuarios, espacios de trabajo y auditoría del espacio."""
import math

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import auditoria, correos
from ..models import Auditoria, EspacioTrabajo, Usuario
from ..permisos import exigir_rol, no_encontrado, prohibido
from ..serializadores import usuario_admin_json
from ..sesiones import cerrar_sesiones

ADMINISTRADOR = (Usuario.ADMINISTRADOR,)
SUPERADMIN = (Usuario.SUPERADMINISTRADOR,)
MENSAJE_SOLO_ADMIN = "Solo el administrador del espacio puede hacer esto."
MENSAJE_SOLO_SUPERADMIN = "Solo el superadministrador puede hacer esto."


class UsuarioEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=150, error_messages={"required": "El nombre es obligatorio.", "blank": "El nombre es obligatorio."})
    email = serializers.EmailField(error_messages={"required": "El correo es obligatorio.", "blank": "El correo es obligatorio.", "invalid": "Ingresá un correo válido."})
    rol = serializers.ChoiceField(choices=[Usuario.PERITO, Usuario.ADMINISTRADOR],
                                  error_messages={"required": "El rol es obligatorio.", "invalid_choice": "El rol tiene que ser perito o administrador."})

    def validate_email(self, valor):
        if Usuario.objects.filter(email=valor.strip().lower()).exists():
            raise serializers.ValidationError("Ya existe un usuario con ese correo.")
        return valor.strip().lower()


class Usuarios(APIView):
    def get(self, solicitud):
        admin = exigir_rol(solicitud, ADMINISTRADOR, MENSAJE_SOLO_ADMIN, "listar_usuarios")
        usuarios = Usuario.objects.filter(espacio_id=admin.espacio_id).select_related("espacio").order_by("nombre", "id")
        return Response({"resultados": [usuario_admin_json(u) for u in usuarios]})

    def post(self, solicitud):
        admin = exigir_rol(solicitud, ADMINISTRADOR, MENSAJE_SOLO_ADMIN, "alta_usuario")
        entrada = UsuarioEntrada(data=solicitud.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        usuario = Usuario.objects.create_user(email=datos["email"], nombre=datos["nombre"], rol=datos["rol"], espacio=admin.espacio)
        correos.enviar_primer_ingreso(usuario)
        auditoria.registrar(admin, "alta_usuario", f"usuario:{usuario.id}", detalle={"rol": usuario.rol})
        return Response(usuario_admin_json(usuario), status=201)


def _usuario_objetivo(solicitud, pk, accion, roles):
    """El administrador solo alcanza a los usuarios de su espacio; el superadministrador (si se permite) a todos."""
    actor = exigir_rol(solicitud, roles, MENSAJE_SOLO_ADMIN, accion)
    usuario = Usuario.objects.select_related("espacio").filter(pk=pk).first()
    if usuario is None or (actor.rol == Usuario.ADMINISTRADOR and usuario.espacio_id != actor.espacio_id):
        raise no_encontrado("No se encontró el usuario.", accion, f"usuario:{pk}")
    if usuario.id == actor.id:
        raise prohibido("No podés hacer esto sobre tu propia cuenta.", accion, f"usuario:{pk}")
    return actor, usuario


class BajaUsuario(APIView):
    def post(self, solicitud, pk):
        actor, usuario = _usuario_objetivo(solicitud, pk, "baja_usuario", ADMINISTRADOR)
        usuario.activo = False
        usuario.save(update_fields=["activo"])
        cerrar_sesiones(usuario)
        auditoria.registrar(actor, "baja_usuario", f"usuario:{usuario.id}")
        return Response(usuario_admin_json(usuario))


class BloquearUsuario(APIView):
    """«Bloquear y cerrar sesiones»: para cuentas comprometidas."""

    def post(self, solicitud, pk):
        actor, usuario = _usuario_objetivo(solicitud, pk, "bloquear_cuenta", ADMINISTRADOR + SUPERADMIN)
        usuario.bloqueado_en = timezone.now()
        usuario.save(update_fields=["bloqueado_en"])
        sesiones = cerrar_sesiones(usuario)
        auditoria.registrar(
            actor, "bloquear_cuenta", f"usuario:{usuario.id}", detalle={"sesiones_cerradas": sesiones}, espacio_id=usuario.espacio_id
        )
        return Response(usuario_admin_json(usuario))


class ReenviarEnlace(APIView):
    def post(self, solicitud, pk):
        actor, usuario = _usuario_objetivo(solicitud, pk, "reenviar_enlace", ADMINISTRADOR)
        if usuario.has_usable_password():
            correos.enviar_restablecimiento(usuario)
        else:
            correos.enviar_primer_ingreso(usuario)
        auditoria.registrar(actor, "reenviar_enlace", f"usuario:{usuario.id}")
        return Response({"detalle": "Enviamos un enlace nuevo."})


class EspacioEntrada(serializers.Serializer):
    nombre = serializers.CharField(max_length=150, error_messages={"required": "El nombre es obligatorio.", "blank": "El nombre es obligatorio."})
    admin_nombre = serializers.CharField(max_length=150, error_messages={"required": "El nombre del administrador es obligatorio.", "blank": "El nombre del administrador es obligatorio."})
    admin_email = serializers.EmailField(error_messages={"required": "El correo del administrador es obligatorio.", "blank": "El correo del administrador es obligatorio.", "invalid": "Ingresá un correo válido."})

    def validate_nombre(self, valor):
        if EspacioTrabajo.objects.filter(nombre__iexact=valor.strip()).exists():
            raise serializers.ValidationError("Ya existe un espacio con ese nombre.")
        return valor.strip()

    def validate_admin_email(self, valor):
        if Usuario.objects.filter(email=valor.strip().lower()).exists():
            raise serializers.ValidationError("Ya existe un usuario con ese correo.")
        return valor.strip().lower()


class Espacios(APIView):
    def get(self, solicitud):
        exigir_rol(solicitud, SUPERADMIN, MENSAJE_SOLO_SUPERADMIN, "listar_espacios")
        espacios = EspacioTrabajo.objects.order_by("nombre")
        cantidades = {}
        for espacio_id in Usuario.objects.values_list("espacio_id", flat=True):
            cantidades[espacio_id] = cantidades.get(espacio_id, 0) + 1
        return Response({"resultados": [
            {"id": e.id, "nombre": e.nombre, "creado_en": e.creado_en, "cantidad_usuarios": cantidades.get(e.id, 0)} for e in espacios
        ]})

    def post(self, solicitud):
        superadmin = exigir_rol(solicitud, SUPERADMIN, MENSAJE_SOLO_SUPERADMIN, "crear_espacio")
        entrada = EspacioEntrada(data=solicitud.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        with transaction.atomic():
            espacio = EspacioTrabajo.objects.create(nombre=datos["nombre"])
            admin = Usuario.objects.create_user(
                email=datos["admin_email"], nombre=datos["admin_nombre"], rol=Usuario.ADMINISTRADOR, espacio=espacio
            )
        correos.enviar_primer_ingreso(admin)
        auditoria.registrar(superadmin, "crear_espacio", f"espacio:{espacio.id}", espacio_id=espacio.id)
        return Response(
            {"id": espacio.id, "nombre": espacio.nombre, "creado_en": espacio.creado_en, "cantidad_usuarios": 1,
             "administrador": usuario_admin_json(admin)},
            status=201,
        )


def auditoria_json(registro):
    usuario = registro.usuario
    origen = registro.siniestro_origen
    return {
        "id": registro.id,
        "fecha": registro.fecha,
        "usuario": {"id": usuario.id, "nombre": usuario.nombre, "email": usuario.email} if usuario else None,
        "accion": registro.accion,
        "objeto": registro.objeto,
        "resultado": registro.resultado,
        "siniestro_origen": {"id": origen.id, "numero_expediente": origen.numero_expediente} if origen else None,
    }


TAMANIO_PAGINA_AUDITORIA = 50


class ListaAuditoria(APIView):
    def get(self, solicitud):
        admin = exigir_rol(solicitud, ADMINISTRADOR, MENSAJE_SOLO_ADMIN, "listar_auditoria")
        base = Auditoria.objects.filter(espacio_id=admin.espacio_id)
        registros = base
        parametros = solicitud.query_params
        if parametros.get("usuario"):
            try:
                registros = registros.filter(usuario_id=int(parametros["usuario"]))
            except ValueError:
                registros = registros.none()
        if parametros.get("accion"):
            registros = registros.filter(accion=parametros["accion"])
        if parametros.get("resultado"):
            registros = registros.filter(resultado=parametros["resultado"])
        total = registros.count()
        paginas = max(1, math.ceil(total / TAMANIO_PAGINA_AUDITORIA))
        try:
            pagina = min(max(1, int(parametros.get("pagina", 1))), paginas)
        except ValueError:
            pagina = 1
        inicio = (pagina - 1) * TAMANIO_PAGINA_AUDITORIA
        pagina_registros = registros.select_related("usuario", "siniestro_origen").order_by("-fecha", "-id")[inicio:inicio + TAMANIO_PAGINA_AUDITORIA]
        return Response({
            "resultados": [auditoria_json(r) for r in pagina_registros],
            "total": total,
            "pagina": pagina,
            "paginas": paginas,
            "acciones": sorted(base.values_list("accion", flat=True).distinct()),
        })


class DetalleAuditoria(APIView):
    """Los registros de auditoría solo se leen: PUT, PATCH y DELETE se rechazan (y se auditan)."""

    def get(self, solicitud, pk):
        admin = exigir_rol(solicitud, ADMINISTRADOR, MENSAJE_SOLO_ADMIN, "ver_auditoria")
        registro = Auditoria.objects.select_related("usuario", "siniestro_origen").filter(pk=pk, espacio_id=admin.espacio_id).first()
        if registro is None:
            raise no_encontrado("No se encontró el registro de auditoría.", "ver_auditoria", f"auditoria:{pk}")
        return Response(auditoria_json(registro))

    def _rechazar(self, pk, accion):
        raise prohibido("Los registros de auditoría no se pueden modificar ni borrar.", accion, f"auditoria:{pk}")

    def put(self, solicitud, pk):
        self._rechazar(pk, "modificar_auditoria")

    def patch(self, solicitud, pk):
        self._rechazar(pk, "modificar_auditoria")

    def delete(self, solicitud, pk):
        self._rechazar(pk, "borrar_auditoria")
