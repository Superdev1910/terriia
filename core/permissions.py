from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from .models import Rol

LOGIN_URL = "/ingresar/"


def solo_roles(*roles):
    def decorar(vista):
        @wraps(vista)
        def envoltura(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), LOGIN_URL)
            if rol_de_usuario(request.user) not in roles:
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltura

    return decorar


def rol_de_usuario(user):
    """Devuelve el rol efectivo; un superusuario conserva acceso de Administrador."""
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return Rol.ADMINISTRADOR
    return getattr(getattr(user, "rol", None), "nombre", None)


def tiene_rol(user, *roles):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    rol = getattr(user, "rol", None)
    return rol is not None and rol.nombre in roles


class IsAdministradorODelegado(BasePermission):
    """Administración completa o gestión operativa dentro de una delegación asignada."""

    message = "Se requiere Administrador o Delegado territorial con delegación asignada."

    def has_permission(self, request, view):
        user = request.user
        return rol_de_usuario(user) == Rol.ADMINISTRADOR or (
            rol_de_usuario(user) == Rol.DELEGADO_TERRITORIAL and bool(user.delegacion_id)
        )


class IsAdministradorODelegadoLectura(BasePermission):
    """Permite al Delegado consultar catálogos; solo el Administrador los modifica."""

    message = "Se requiere Administrador o consulta de Delegado territorial."

    def has_permission(self, request, view):
        user = request.user
        if rol_de_usuario(user) == Rol.ADMINISTRADOR:
            return True
        return (
            rol_de_usuario(user) == Rol.DELEGADO_TERRITORIAL
            and bool(user.delegacion_id)
            and request.method in ("GET", "HEAD", "OPTIONS")
        )


class IsAdministradorODelegadoOFuncionarioCrea(BasePermission):
    """Admin y Delegado gestionan; el Funcionario con delegación solo consulta y crea (POST)."""

    message = "No tiene permiso para realizar esta operación."
    METODOS_FUNCIONARIO = ("GET", "HEAD", "OPTIONS", "POST")

    def has_permission(self, request, view):
        user = request.user
        rol = rol_de_usuario(user)
        if rol == Rol.ADMINISTRADOR:
            return True
        if rol == Rol.DELEGADO_TERRITORIAL:
            return bool(user.delegacion_id)
        return (
            rol == Rol.FUNCIONARIO
            and bool(user.delegacion_id)
            and request.method in self.METODOS_FUNCIONARIO
        )


class IsAdministradorODelegadoOFuncionarioLectura(BasePermission):
    """Admin y Delegado gestionan; el Funcionario con delegación solo consulta."""

    message = "No tiene permiso para realizar esta operación."

    def has_permission(self, request, view):
        user = request.user
        rol = rol_de_usuario(user)
        if rol == Rol.ADMINISTRADOR:
            return True
        if rol == Rol.DELEGADO_TERRITORIAL:
            return bool(user.delegacion_id)
        return (
            rol == Rol.FUNCIONARIO
            and bool(user.delegacion_id)
            and request.method in ("GET", "HEAD", "OPTIONS")
        )


class IsFuncionario(BasePermission):
    """Un Funcionario solo usa la vista de sus datos si tiene ficha asociada."""

    message = "Se requiere un usuario Funcionario asociado a una ficha activa."

    def has_permission(self, request, view):
        user = request.user
        return (
            rol_de_usuario(user) == Rol.FUNCIONARIO
            and bool(user.funcionario_id)
            and getattr(user.funcionario, "estado", None) == "activo"
        )


class IsAdministradorODelegadoOMiPerfil(BasePermission):
    """Permite gestión al Administrador/Delegado y solo GET al Funcionario de su ficha."""

    message = "No tiene permiso para realizar esta operación."

    def has_permission(self, request, view):
        user = request.user
        rol = rol_de_usuario(user)
        if rol == Rol.ADMINISTRADOR:
            return True
        if rol == Rol.DELEGADO_TERRITORIAL:
            return bool(user.delegacion_id)
        return (
            rol == Rol.FUNCIONARIO
            and bool(user.funcionario_id)
            and getattr(user.funcionario, "estado", None) == "activo"
            and request.method in ("GET", "HEAD", "OPTIONS")
        )


class IsAdministrador(BasePermission):
    """Permiso para operaciones globales y mantenedores reservados al Administrador."""

    message = "Solo el Administrador puede usar los mantenedores."

    def has_permission(self, request, view):
        return tiene_rol(request.user, Rol.ADMINISTRADOR)


class IsOperativoCreaVecinos(BasePermission):
    """Los roles operativos pueden registrar (POST) un vecino; el resto de las operaciones
    sigue siendo solo del Administrador. La Alcaldesa no crea."""

    message = "No tienes permiso para realizar esta operación con vecinos."
    ROLES_CREAN = (
        Rol.FUNCIONARIO,
        Rol.ENCARGADO_AREA,
        Rol.DELEGADO_TERRITORIAL,
        Rol.JEFE_DELEGACIONES,
        Rol.ADMINISTRADOR,
    )

    def has_permission(self, request, view):
        if request.method == "POST":
            return rol_de_usuario(request.user) in self.ROLES_CREAN
        return tiene_rol(request.user, Rol.ADMINISTRADOR)
