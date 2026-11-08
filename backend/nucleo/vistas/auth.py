"""Autenticación: sesión, ingreso, salida, restablecimiento y perfil de contacto."""
from django.contrib.auth import login, logout
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as ErrorValidacionDjango
from django.db import transaction
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .. import auditoria, correos
from ..autenticacion import SesionTolerante
from ..models import Usuario
from ..serializadores import usuario_json
from ..sesiones import cerrar_sesiones

MAXIMO_INTENTOS = 5
ERROR_INGRESO = "El correo o la contraseña no son correctos."
ENLACE_INVALIDO = "El enlace no es válido o venció."
HASH_FALSO = make_password("contraseña-de-relleno")  # iguala el tiempo de respuesta cuando el correo no existe


def _texto(datos, clave):
    valor = datos.get(clave) if hasattr(datos, "get") else None
    return valor if isinstance(valor, str) else ""


class Sesion(APIView):
    """Estado de la sesión. Siempre entrega la cookie CSRF y nunca responde 401."""

    authentication_classes = [SesionTolerante]
    permission_classes = [AllowAny]

    def get(self, solicitud):
        get_token(solicitud._request)
        usuario = solicitud.user
        if usuario.is_authenticated:
            return Response({"autenticado": True, "usuario": usuario_json(usuario)})
        return Response({"autenticado": False, "usuario": None})


class Ingresar(APIView):
    permission_classes = [AllowAny]

    def post(self, solicitud):
        email = _texto(solicitud.data, "email").strip().lower()
        password = _texto(solicitud.data, "password")
        with transaction.atomic():
            usuario = Usuario.objects.select_for_update().filter(email=email).first() if email else None
            habilitado = usuario is not None and usuario.activo and usuario.bloqueado_en is None
            if usuario is None:
                check_password(password, HASH_FALSO)
            if habilitado and usuario.check_password(password):
                usuario.intentos_fallidos = 0
                usuario.save(update_fields=["intentos_fallidos"])
                login(solicitud._request, usuario, backend="django.contrib.auth.backends.ModelBackend")
                auditoria.registrar(usuario, "ingreso", f"usuario:{usuario.id}")
                return Response({"usuario": usuario_json(usuario)})
            self._registrar_fallo(usuario, habilitado, email)
        return Response({"detalle": ERROR_INGRESO}, status=400)

    @staticmethod
    def _registrar_fallo(usuario, habilitado, email):
        bloqueada_ahora = False
        if habilitado:
            usuario.intentos_fallidos += 1
            if usuario.intentos_fallidos >= MAXIMO_INTENTOS:
                usuario.bloqueado_en = timezone.now()
                bloqueada_ahora = True
            usuario.save(update_fields=["intentos_fallidos", "bloqueado_en"])
        auditoria.rechazar(
            usuario,
            "ingreso_fallido",
            f"usuario:{usuario.id}" if usuario else f"correo:{email[:120]}",
            detalle={"intentos": usuario.intentos_fallidos} if usuario else {},
        )
        if bloqueada_ahora:
            auditoria.registrar(usuario, "bloqueo_cuenta", f"usuario:{usuario.id}", detalle={"motivo": "5 intentos fallidos"})
            correos.enviar_bloqueo(usuario)


class Salir(APIView):
    def post(self, solicitud):
        usuario = solicitud.user
        auditoria.registrar(usuario, "salida", f"usuario:{usuario.id}")
        logout(solicitud._request)
        return Response(status=204)


class Restablecer(APIView):
    """Pide el enlace de restablecimiento. Responde siempre lo mismo, exista o no el correo."""

    permission_classes = [AllowAny]

    def post(self, solicitud):
        email = _texto(solicitud.data, "email").strip().lower()
        usuario = Usuario.objects.filter(email=email, activo=True).first() if email else None
        if usuario is not None:
            correos.enviar_restablecimiento(usuario)
            auditoria.registrar(usuario, "solicitud_restablecimiento", f"usuario:{usuario.id}")
        return Response({"detalle": "Si el correo está registrado, te enviamos un enlace para restablecer la contraseña."})


def usuario_del_enlace(uid, token):
    """Devuelve el usuario si el enlace es válido (token vigente, de un solo uso y cuenta activa)."""
    try:
        pk = force_str(urlsafe_base64_decode(uid))
        usuario = Usuario.objects.filter(pk=int(pk), activo=True).first()
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
        return None
    if usuario is None or not default_token_generator.check_token(usuario, token):
        return None
    return usuario


class Enlace(APIView):
    permission_classes = [AllowAny]

    def get(self, solicitud):
        usuario = usuario_del_enlace(solicitud.query_params.get("uid", ""), solicitud.query_params.get("token", ""))
        return Response({"valido": usuario is not None, "email": usuario.email if usuario else None})


class DefinirContrasena(APIView):
    """Primer ingreso y restablecimiento: define la contraseña con un enlace de un solo uso."""

    permission_classes = [AllowAny]

    def post(self, solicitud):
        usuario = usuario_del_enlace(_texto(solicitud.data, "uid"), _texto(solicitud.data, "token"))
        if usuario is None:
            return Response({"detalle": ENLACE_INVALIDO}, status=400)
        password = _texto(solicitud.data, "password")
        try:
            validate_password(password, usuario)
        except ErrorValidacionDjango as error:
            return Response({"password": list(error.messages)}, status=400)
        era_primer_ingreso = not usuario.has_usable_password()
        usuario.set_password(password)
        usuario.intentos_fallidos = 0
        usuario.bloqueado_en = None
        usuario.save(update_fields=["password", "intentos_fallidos", "bloqueado_en"])
        cerrar_sesiones(usuario)
        auditoria.registrar(
            usuario, "primer_ingreso" if era_primer_ingreso else "restablecimiento_contrasena", f"usuario:{usuario.id}"
        )
        return Response({"detalle": "Contraseña actualizada. Ya podés ingresar."})


class PerfilEntrada(serializers.Serializer):
    contacto_email = serializers.EmailField(required=False, allow_blank=True, max_length=254,
                                            error_messages={"invalid": "Ingresá un correo válido."})
    contacto_visible = serializers.BooleanField(required=False)


class Perfil(APIView):
    def get(self, solicitud):
        return Response(usuario_json(solicitud.user))

    def patch(self, solicitud):
        entrada = PerfilEntrada(data=solicitud.data)
        entrada.is_valid(raise_exception=True)
        usuario = solicitud.user
        antes = {"contacto_email": usuario.contacto_email, "contacto_visible": usuario.contacto_visible}
        for campo, valor in entrada.validated_data.items():
            setattr(usuario, campo, valor)
        usuario.save(update_fields=list(entrada.validated_data) or None)
        despues = {"contacto_email": usuario.contacto_email, "contacto_visible": usuario.contacto_visible}
        auditoria.registrar(usuario, "perfil_contacto", f"usuario:{usuario.id}", detalle={"antes": antes, "despues": despues})
        return Response(usuario_json(usuario))
