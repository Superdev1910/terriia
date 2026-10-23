from django.contrib.auth import authenticate, login, logout
from django.db import models, transaction
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.decorators import method_decorator
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import auditoria
from .models import Rol
from .permissions import IsAdministrador, rol_de_usuario
from .serializers import RolSerializer


class MantenedorViewSet(viewsets.ModelViewSet):
    """
    Plantilla base de los mantenedores. Trae:
      - permiso IsAdministrador por defecto (las subclases de alcance definen excepciones)
      - listado con búsqueda (search_fields), filtro (filterset_fields) y paginación
      - registro automático en auditoria (crear / editar / desactivar)
      - "borrar" = desactivar (nunca DELETE físico)

    En la subclase se pueden definir queryset, serializer_class, search_fields,
    filterset_fields, campo_estado y los alcances delegacion_lookup/funcionario_lookup.
    """

    permission_classes = [IsAdministrador]
    delegacion_lookup = None
    delegacion_related_lookups = ()
    funcionario_lookup = None
    delegado_lectura_global = False
    campo_estado = "estado"  # nombre del campo que se desactiva
    valor_inactivo = None  # se deduce solo: False si es booleano, 'inactivo'/'inactiva' si es ENUM
    ordering_fields = "__all__"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        rol = rol_de_usuario(user)
        if rol == Rol.ADMINISTRADOR:
            return queryset
        if rol == Rol.DELEGADO_TERRITORIAL:
            if self.delegacion_lookup and user.delegacion_id:
                return queryset.filter(**{self.delegacion_lookup: user.delegacion_id})
            if self.delegado_lectura_global:
                return queryset
            return queryset.none()
        if rol == Rol.FUNCIONARIO and self.funcionario_lookup and user.funcionario_id:
            return queryset.filter(**{self.funcionario_lookup: user.funcionario_id})
        return queryset.none()

    def _validar_alcance_delegado(self, instancia):
        user = self.request.user
        if (
            rol_de_usuario(user) == Rol.DELEGADO_TERRITORIAL
            and self.delegacion_lookup
        ):
            pertenece = self.get_queryset().filter(pk=instancia.pk).exists()
            relacionados = all(
                type(instancia)._base_manager.filter(
                    pk=instancia.pk, **{lookup: user.delegacion_id}
                ).exists()
                for lookup in self.delegacion_related_lookups
            )
            if not pertenece or not relacionados:
                raise PermissionDenied(
                    "El registro y sus relaciones deben pertenecer a tu delegación."
                )

    # --- auditoría -------------------------------------------------------
    def perform_create(self, serializer):
        with transaction.atomic():
            instancia = serializer.save()
            self._validar_alcance_delegado(instancia)
            auditoria.registrar(
                self.request.user, "crear", instancia, nuevo=auditoria.foto(instancia)
            )

    def perform_update(self, serializer):
        with transaction.atomic():
            anterior = auditoria.foto(serializer.instance)
            instancia = serializer.save()
            self._validar_alcance_delegado(instancia)
            auditoria.registrar(
                self.request.user,
                "editar",
                instancia,
                anterior=anterior,
                nuevo=auditoria.foto(instancia),
            )

    # --- desactivar en vez de borrar -----------------------------------
    def _valor_inactivo(self, modelo):
        if self.valor_inactivo is not None:
            return self.valor_inactivo
        campo = modelo._meta.get_field(self.campo_estado)
        if isinstance(campo, models.BooleanField):
            return False
        for valor, _ in campo.choices or []:
            if str(valor).lower().startswith("inactiv"):
                return valor
        raise ValueError(
            f"No se pudo deducir el valor inactivo de {modelo.__name__}.{self.campo_estado}; "
            "define valor_inactivo en el ViewSet."
        )

    def destroy(self, request, *args, **kwargs):
        instancia = self.get_object()
        with transaction.atomic():
            anterior = auditoria.foto(instancia)
            setattr(instancia, self.campo_estado, self._valor_inactivo(type(instancia)))
            instancia.save(update_fields=[self.campo_estado])
            auditoria.registrar(
                request.user,
                "desactivar",
                instancia,
                anterior=anterior,
                nuevo=auditoria.foto(instancia),
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class RolViewSet(MantenedorViewSet):
    """
    Mantenedor de roles. Sin DELETE: se desactiva con PATCH {"activo": false}, así pasa por
    RolSerializer, que impide renombrar o desactivar los 6 roles del sistema.
    Un rol desactivado no bloquea el login de quienes ya lo tienen (el login solo mira
    usuario.estado); lo que ya no se puede es asignarlo (UsuarioSerializer.validate_rol).
    """

    # order_by explícito: con GROUP BY (annotate + Count) Django no aplica Meta.ordering.
    queryset = Rol.objects.annotate(cantidad_usuarios=models.Count("usuario")).order_by("id_rol")
    serializer_class = RolSerializer
    search_fields = ["nombre", "descripcion"]
    filterset_fields = ["activo"]
    campo_estado = "activo"
    http_method_names = ["get", "post", "put", "patch", "head", "options"]


# --- Sesión (login con django.contrib.auth) --------------------------------


def datos_usuario(user):
    return {
        "id_usuario": user.pk,
        "email": user.email,
        "rut": user.rut,
        "nombre": user.get_full_name(),
        "rol": user.rol.nombre if user.rol_id else None,
    }


@method_decorator(ensure_csrf_cookie, name="get")
class LoginView(APIView):
    """GET entrega la cookie CSRF; POST {email, password} inicia sesión."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def get(self, request):
        return Response({"detail": "Enviar POST con email y password."})

    def post(self, request):
        email, clave = request.data.get("email"), request.data.get("password")
        if (
            not isinstance(email, str)
            or not isinstance(clave, str)
            or not email.strip()
            or not clave
        ):
            return Response(
                {"error": "Escribe tu correo y tu contraseña.", "campo": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = authenticate(request, username=email.strip().lower(), password=clave)
        if user is None:
            return Response(
                {"error": "Email o contraseña incorrectos.", "campo": None},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(datos_usuario(user))


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class YoView(APIView):
    """Datos del usuario con sesión iniciada."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(datos_usuario(request.user))
