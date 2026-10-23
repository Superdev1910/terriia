"""
Configuración de TerriIA.

Todos los valores sensibles salen del archivo .env (ver .env.example).
Nunca subir el .env al repositorio.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(nombre, por_defecto=False):
    return os.getenv(nombre, str(por_defecto)).lower() in ("1", "true", "si", "yes")


def env_list(nombre, por_defecto=""):
    return [v.strip() for v in os.getenv(nombre, por_defecto).split(",") if v.strip()]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "solo-para-desarrollo-cambiar")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceros
    "rest_framework",
    "django_filters",
    # TerriIA
    "core",  # base común (Patricio)
    "organizacion",  # delegacion, area, cargo (Brian)
    "personas",  # usuario (Patricio), funcionario (Fernando)
    "territorio",  # vecino, territorio, junta_vecinos (Pamela)
    "metas",  # periodo, item (Valentina), meta_delegacion, meta (Fernando)
    "atenciones",  # tipo_atencion, sub_atencion (SCRUM-61)
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Base de datos: MariaDB en el servidor (DB_ENGINE=mysql), SQLite en local si no se define.
if os.getenv("DB_ENGINE", "sqlite") == "mysql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "terriia"),
            "USER": os.getenv("DB_USER", "terriia"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Usuario propio (tabla `usuario` del modelo físico). NO cambiar después del primer migrate.
AUTH_USER_MODEL = "personas.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "static"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "EXCEPTION_HANDLER": "core.exceptions.manejador_errores",
    # Detrás de Nginx: toma la IP real del cliente desde X-Forwarded-For (1 proxy) y evita
    # que alguien la falsifique enviando su propio encabezado.
    "NUM_PROXIES": 1,
    "DEFAULT_THROTTLE_RATES": {  # freno a la fuerza bruta (por IP)
        "login": "10/min",
        "recuperar": "12/min",
    },
}

# OpenStreetMap exige el encabezado Referer para entregar los mapas (Leaflet). El valor por
# defecto de Django ("same-origin") no lo envía a otros sitios y los mapas salen en blanco.
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# Correo (recuperar contraseña). En local los correos se imprimen en la consola del servidor;
# en el servidor se define EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend en el .env.
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "TerriIA <no-responder@laserena.cl>")

# Recuperar contraseña: vigencia del código (minutos) y errores permitidos antes de anularlo.
RECUPERACION_MINUTOS = int(os.getenv("RECUPERACION_MINUTOS", "15"))
RECUPERACION_INTENTOS = 5

# Detrás de Nginx en producción
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_HTTPONLY = True
    X_FRAME_OPTIONS = "DENY"
