"""Lógica de recuperar y cambiar contraseña (código de 6 dígitos enviado al correo)."""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import CodigoRecuperacion

ESPERA_SEGUNDOS = 60  # no se genera otro código antes de este tiempo


def _huella(usuario, codigo):
    return salted_hmac("terriia.recuperacion", f"{usuario.pk}:{codigo}").hexdigest()


def buscar_usuario(email):
    email = (email or "").strip().lower()
    if not email:
        return None
    return get_user_model().objects.filter(email=email).first()


def _activo(usuario):
    return usuario is not None and usuario.is_active


def enviar_codigo(email):
    """Genera y envía un código. No revela si el correo existe (siempre devuelve None)."""
    usuario = buscar_usuario(email)
    if not _activo(usuario):
        return
    ultimo = usuario.codigos_recuperacion.first()
    if ultimo and (timezone.now() - ultimo.creado).total_seconds() < ESPERA_SEGUNDOS:
        return
    usuario.codigos_recuperacion.filter(usado=False).update(usado=True)  # solo vale el último
    codigo = f"{secrets.randbelow(10**6):06d}"
    CodigoRecuperacion.objects.create(
        usuario=usuario,
        huella=_huella(usuario, codigo),
        vence=timezone.now() + timedelta(minutes=settings.RECUPERACION_MINUTOS),
    )
    send_mail(
        subject="Código para recuperar tu contraseña · TerriIA",
        message=(
            f"Hola,\n\nTu código de verificación es: {codigo}\n\n"
            f"Vence en {settings.RECUPERACION_MINUTOS} minutos. "
            "Si no lo pediste tú, ignora este mensaje: tu contraseña no cambia.\n\n"
            "Municipalidad de La Serena · TerriIA"
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[usuario.email],
    )


def validar_codigo(email, codigo, consumir=False):
    """Devuelve (usuario, registro) si el código es correcto; si no, (None, None)."""
    usuario = buscar_usuario(email)
    codigo = (codigo or "").strip()
    if not _activo(usuario) or not (codigo.isdigit() and len(codigo) == 6):
        return None, None
    registro = usuario.codigos_recuperacion.filter(usado=False, vence__gt=timezone.now()).first()
    if registro is None:
        return None, None
    if registro.intentos >= settings.RECUPERACION_INTENTOS:
        registro.usado = True
        registro.save(update_fields=["usado"])
        return None, None
    if not constant_time_compare(registro.huella, _huella(usuario, codigo)):
        registro.intentos += 1
        registro.save(update_fields=["intentos"])
        return None, None
    if consumir:
        registro.usado = True
        registro.save(update_fields=["usado"])
    return usuario, registro
