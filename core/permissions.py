from rest_framework.permissions import BasePermission

from .models import Rol


def tiene_rol(user, *roles):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    rol = getattr(user, "rol", None)
    return rol is not None and rol.nombre in roles


class IsAdministrador(BasePermission):
    """Solo el rol Administrador (validado en el backend). Usar en todos los mantenedores."""

    message = "Solo el Administrador puede usar los mantenedores."

    def has_permission(self, request, view):
        return tiene_rol(request.user, Rol.ADMINISTRADOR)
