"""Sitio público de la Municipalidad y pantallas de acceso (parte visual de Brian).

- Inicio de sesión: usa la API real de core (/api/auth/login/).
- Registro, recuperar contraseña (código al correo) y cambiar contraseña: demostración visual,
  no guardan datos ni envían correos. Los endpoints reales los debe hacer core (Patricio).
"""

from django.contrib.auth.views import redirect_to_login
from django.shortcuts import render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import ensure_csrf_cookie

from core.models import Rol
from core.permissions import tiene_rol

from .datos_directorio import DELEGACIONES
from .pantallas import LOGIN_URL

MENU_PUBLICO = [
    ("pub_inicio", "Inicio", "bi-house-door"),
    ("pub_delegaciones", "Delegaciones", "bi-buildings"),
    ("pub_servicios", "Servicios", "bi-grid"),
    ("pub_contacto", "Contacto", "bi-envelope"),
]

# Textos de ejemplo (icono, título, descripción). Se pueden cambiar sin tocar la plantilla.
SERVICIOS = [
    (
        "bi-headset",
        "Atención de público",
        "Orientación, plataformas ciudadanas y trámites en tu delegación.",
    ),
    (
        "bi-cash-coin",
        "Subsidios",
        "Información y postulación a los beneficios sociales disponibles.",
    ),
    (
        "bi-house-heart",
        "Registro Social de Hogares",
        "Apoyo para realizar y actualizar tu registro.",
    ),
    (
        "bi-people",
        "Social",
        "Apoyo a las familias del sector en distintos ámbitos del desarrollo social.",
    ),
    ("bi-person-heart", "Adulto Mayor", "Programas y actividades para las personas mayores."),
    (
        "bi-diagram-3",
        "Territorio y organizaciones",
        "Trabajo con juntas de vecinos y organizaciones comunitarias.",
    ),
    ("bi-gender-ambiguous", "Género y equidad", "Acompañamiento y orientación en temas de género."),
]


def _contexto(request, activa=None, extra=None):
    u = request.user
    contexto = {
        "menu_publico": MENU_PUBLICO,
        "activa": activa,
        "es_admin": tiene_rol(u, Rol.ADMINISTRADOR),
        "nombre_usuario": (u.get_full_name() or u.email) if u.is_authenticated else "",
    }
    contexto.update(extra or {})
    return contexto


def _pagina(request, plantilla, activa=None, extra=None):
    return render(request, plantilla, _contexto(request, activa, extra))


@ensure_csrf_cookie
def portada(request):
    return _pagina(request, "organizacion/portada.html", "pub_inicio")


@ensure_csrf_cookie
def delegaciones(request):
    extra = {"delegaciones": DELEGACIONES}
    return _pagina(request, "organizacion/directorio.html", "pub_delegaciones", extra)


@ensure_csrf_cookie
def servicios(request):
    return _pagina(
        request, "organizacion/servicios.html", "pub_servicios", {"servicios": SERVICIOS}
    )


@ensure_csrf_cookie
def contacto(request):
    extra = {"delegaciones": DELEGACIONES}
    return _pagina(request, "organizacion/contacto.html", "pub_contacto", extra)


@ensure_csrf_cookie
def ingresar(request):
    siguiente = request.GET.get("next", "")
    if not url_has_allowed_host_and_scheme(siguiente, allowed_hosts={request.get_host()}):
        siguiente = ""  # solo se acepta volver a páginas de este mismo sitio
    return render(request, "organizacion/ingresar.html", {"siguiente": siguiente})


@ensure_csrf_cookie
def registro(request):
    return render(request, "organizacion/registro.html")


@ensure_csrf_cookie
def recuperar(request):
    return render(request, "organizacion/recuperar.html")


@ensure_csrf_cookie
def cambiar_clave(request):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), LOGIN_URL)
    return render(request, "organizacion/cambiar_clave.html")
