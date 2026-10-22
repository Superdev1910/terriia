"""Pantallas HTML de los mantenedores de organización (solo Administrador).

Las pantallas solo pintan la interfaz; los datos y los permisos reales viven en la API
(/api/delegaciones/, /api/areas/, /api/cargos/), que valida el rol en el servidor.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from core.permissions import tiene_rol
from core.models import Rol

LOGIN_URL = "/ingresar/"  # pantalla de inicio de sesión del sitio (publico.py)

MENU = [
    ("org_inicio", "Inicio", "bi-house-door"),
    ("org_delegaciones", "Delegaciones", "bi-buildings"),
    ("org_areas", "Áreas", "bi-diagram-3"),
    ("org_cargos", "Cargos", "bi-person-badge"),
]


def solo_administrador(vista):
    @wraps(vista)
    def envoltura(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), LOGIN_URL)
        if not tiene_rol(request.user, Rol.ADMINISTRADOR):
            raise PermissionDenied
        return vista(request, *args, **kwargs)

    return envoltura


def contexto_usuario(request, activa):
    u = request.user
    delegacion = getattr(u, "delegacion", None)  # campo pendiente en usuario (HU19)
    return {
        "menu": MENU,
        "activa": activa,
        "nombre_usuario": u.get_full_name() or u.email,
        "rol_usuario": u.rol.nombre if getattr(u, "rol_id", None) else "Superusuario",
        "delegacion_codigo": delegacion.codigo if delegacion else None,
        "delegacion_nombre": delegacion.nombre if delegacion else "Acceso global",
    }


def _pagina(request, activa, plantilla="organizacion/mantenedor.html", extra=None):
    contexto = contexto_usuario(request, activa)
    contexto.update(extra or {})
    return render(request, plantilla, contexto)


@solo_administrador
@ensure_csrf_cookie
def inicio(request):
    return _pagina(request, "org_inicio", "organizacion/inicio.html")


@solo_administrador
@ensure_csrf_cookie
def delegaciones(request):
    return _pagina(request, "org_delegaciones", extra={"entidad": "delegaciones"})


@solo_administrador
@ensure_csrf_cookie
def areas(request):
    return _pagina(request, "org_areas", extra={"entidad": "areas"})


@solo_administrador
@ensure_csrf_cookie
def cargos(request):
    return _pagina(request, "org_cargos", extra={"entidad": "cargos"})
