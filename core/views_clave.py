"""Endpoints de contraseña: recuperar (3 pasos) y cambiar con sesión iniciada."""

from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import recuperacion

CODIGO_MALO = "El código es incorrecto o ya venció."


def _error(mensaje, campo=None, codigo=status.HTTP_400_BAD_REQUEST):
    return Response({"error": mensaje, "campo": campo}, status=codigo)


def _texto(datos, nombre):
    valor = datos.get(nombre, "")
    return valor if isinstance(valor, str) else ""


def _clave_invalida(clave, usuario):
    try:
        validate_password(clave, usuario)
    except ValidationError as e:
        return " ".join(e.messages)
    return None


class _Limitada(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "recuperar"


class SolicitarCodigoView(_Limitada):
    """POST {email}: envía el código. Responde igual exista o no el correo."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = _texto(request.data, "email").strip()
        if "@" not in email:
            return _error("Escribe un correo válido.", "email")
        recuperacion.enviar_codigo(email)
        return Response(
            {"detail": "Si el correo está registrado, enviamos un código de 6 dígitos."}
        )


class VerificarCodigoView(_Limitada):
    """POST {email, codigo}: comprueba el código sin gastarlo (paso 2)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        usuario, _ = recuperacion.validar_codigo(
            _texto(request.data, "email"), _texto(request.data, "codigo")
        )
        if usuario is None:
            return _error(CODIGO_MALO, "codigo")
        return Response({"detail": "Código correcto."})


class ConfirmarRecuperacionView(_Limitada):
    """POST {email, codigo, password}: cambia la contraseña (paso 3)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        clave = _texto(request.data, "password")
        usuario, _ = recuperacion.validar_codigo(
            _texto(request.data, "email"), _texto(request.data, "codigo"), consumir=False
        )
        if usuario is None:
            return _error(CODIGO_MALO, "codigo")
        problema = _clave_invalida(clave, usuario)
        if problema:
            return _error(problema, "password")
        usuario.set_password(clave)
        usuario.save(update_fields=["password"])
        usuario.codigos_recuperacion.filter(usado=False).update(usado=True)
        return Response({"detail": "Contraseña actualizada."})


class CambiarClaveView(APIView):
    """POST {actual, nueva}: cambia la contraseña con la sesión iniciada."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        actual, nueva = _texto(request.data, "actual"), _texto(request.data, "nueva")
        if not request.user.check_password(actual):
            return _error("La contraseña actual no es correcta.", "actual")
        if actual == nueva:
            return _error("La nueva contraseña debe ser distinta de la actual.", "nueva")
        problema = _clave_invalida(nueva, request.user)
        if problema:
            return _error(problema, "nueva")
        request.user.set_password(nueva)
        request.user.save(update_fields=["password"])
        update_session_auth_hash(request, request.user)  # mantiene la sesión abierta
        return Response({"detail": "Contraseña actualizada."})
