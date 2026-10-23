from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from core.models import Rol
from core.permissions import tiene_rol

LOGIN_URL = "/ingresar/"
MENU = [
    ("territorio_vecinos", "Vecinos", "bi-people"),
    ("territorio_territorios", "Territorios", "bi-map"),
    ("territorio_juntas", "Juntas de vecinos", "bi-houses"),
]
MENU_SECCIONES = [
    ("Inicio", [("org_inicio", "Inicio", "bi-house-door")]),
    (
        "Organización",
        [
            ("org_delegaciones", "Delegaciones", "bi-buildings"),
            ("org_areas", "Áreas", "bi-diagram-3"),
            ("org_cargos", "Cargos", "bi-person-badge"),
        ],
    ),
    ("Territorio", MENU),
    (
        "Metas",
        [
            ("metas_periodos", "Períodos", "bi-calendar-range"),
            ("metas_items", "Ítems", "bi-list-check"),
            ("metas_delegacion", "Metas por delegación", "bi-bullseye"),
            ("metas_individuales", "Metas individuales", "bi-person-check"),
        ],
    ),
    ("Administración", [("core_roles", "Roles", "bi-shield-lock")]),
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


def contexto(request, activa):
    usuario = request.user
    delegacion = getattr(usuario, "delegacion", None)
    return {
        "menu": MENU,
        "menu_secciones": MENU_SECCIONES,
        "activa": activa,
        "nombre_usuario": usuario.get_full_name() or usuario.email,
        "rol_usuario": usuario.rol.nombre if getattr(usuario, "rol_id", None) else "Superusuario",
        "delegacion_codigo": delegacion.codigo if delegacion else None,
        "delegacion_nombre": delegacion.nombre if delegacion else "Acceso global",
    }


def pagina(request, activa, entidad):
    datos = contexto(request, activa)
    datos["entidad"] = entidad
    return render(request, "territorio/mantenedor.html", datos)


@solo_administrador
@ensure_csrf_cookie
def vecinos(request):
    return pagina(request, "territorio_vecinos", "vecinos")


@solo_administrador
@ensure_csrf_cookie
def territorios(request):
    return pagina(request, "territorio_territorios", "territorios")


@solo_administrador
@ensure_csrf_cookie
def juntas(request):
    return pagina(request, "territorio_juntas", "juntas-vecinos")
