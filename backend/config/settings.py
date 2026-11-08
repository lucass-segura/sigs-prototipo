"""Configuración de Django para el prototipo SIGS."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(nombre, por_defecto=False):
    valor = os.environ.get(nombre)
    if valor is None:
        return por_defecto
    return valor.strip().lower() in ("1", "true", "si", "sí", "yes")


def env_lista(nombre, por_defecto):
    return [v.strip() for v in os.environ.get(nombre, por_defecto).split(",") if v.strip()]


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "clave-local-insegura-solo-para-el-prototipo")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_lista("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1") + ["backend"]
CSRF_TRUSTED_ORIGINS = env_lista("CSRF_TRUSTED_ORIGINS", "http://localhost,http://127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "rest_framework",
    "nucleo",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "sigs"),
        "USER": os.environ.get("DB_USER", "sigs_app"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "sigs_app"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "nucleo.Usuario"

# Política de contraseña (sección Seguridad del TFG)
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        "OPTIONS": {"user_attributes": ("email", "nombre")},
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "nucleo.validadores.ComplejidadValidator"},
]

# Enlaces de primer ingreso y restablecimiento: un solo uso y vencen en 1 hora
PASSWORD_RESET_TIMEOUT = 3600

# Sesión: cookie HttpOnly, se cierra tras 60 minutos sin actividad
SESSION_COOKIE_AGE = 3600
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_NAME = "sigs_sesion"
CSRF_COOKIE_HTTPONLY = False  # el frontend la lee para enviar X-CSRFToken
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_NAME = "csrftoken"
CSRF_FAILURE_VIEW = "nucleo.vistas.base.csrf_fallido"

SECURE_COOKIES = env_bool("SECURE_COOKIES", False)
SESSION_COOKIE_SECURE = SECURE_COOKIES
CSRF_COOKIE_SECURE = SECURE_COOKIES
if SECURE_COOKIES:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LANGUAGE_CODE = "es-ar"
TIME_ZONE = "America/Argentina/Buenos_Aires"
USE_I18N = True
USE_TZ = True

# Correo: Mailpit en local
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "1025"))
EMAIL_USE_TLS = False
DEFAULT_FROM_EMAIL = "SIGS <no-responder@sigs.test>"
APP_URL = os.environ.get("APP_URL", "http://localhost").rstrip("/")

# Documentos privados: volumen sin URL pública. Solo se descargan por la API.
DOCUMENTOS_DIR = os.environ.get("DOCUMENTOS_DIR", str(BASE_DIR / "documentos"))
DOCUMENTO_TAMANIO_MAXIMO = 15 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["nucleo.autenticacion.SesionAutenticacion"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "EXCEPTION_HANDLER": "nucleo.permisos.manejar_excepcion",
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
