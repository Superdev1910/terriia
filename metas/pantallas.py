"""Pantallas HTML de los mantenedores de metas.

Las pantallas solo pintan la interfaz; los datos, las reglas y los permisos reales viven en
la API (/api/periodos/, /api/items/, /api/metas-delegacion/, /api/metas/), que valida el rol
en el servidor.
"""

from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from core.models import Rol
from core.permissions import rol_de_usuario
from organizacion.models import Delegacion
from .models import Periodo
from organizacion.pantallas import contexto_usuario, solo_administrador, solo_roles
from territorio.pantallas import menu_para_usuario


def pagina(request, activa, entidad, titulo):
    datos = contexto_usuario(request, activa)
    datos.update(menu_secciones=menu_para_usuario(request.user), entidad=entidad, titulo=titulo)
    return render(request, "metas/mantenedor.html", datos)


@solo_administrador
@ensure_csrf_cookie
def periodos(request):
    return pagina(request, "metas_periodos", "periodos", "Períodos")


@solo_administrador
@ensure_csrf_cookie
def items(request):
    return pagina(request, "metas_items", "items", "Ítems")


@solo_roles(Rol.ADMINISTRADOR, Rol.DELEGADO_TERRITORIAL)
@ensure_csrf_cookie
def metas_delegacion(request):
    return pagina(request, "metas_delegacion", "metas-delegacion", "Metas por delegación")


@solo_roles(Rol.ADMINISTRADOR, Rol.DELEGADO_TERRITORIAL)
@ensure_csrf_cookie
def metas_individuales(request):
    return pagina(request, "metas_individuales", "metas", "Metas individuales")


@solo_roles(Rol.ADMINISTRADOR, Rol.ALCALDESA)
@ensure_csrf_cookie
def dashboard_ejecutivo(request):
    datos = contexto_usuario(request, "metas_dashboard_ejecutivo")
    datos["menu_secciones"] = menu_para_usuario(request.user)
    return render(request, "metas/dashboard_ejecutivo.html", datos)


@solo_administrador
@ensure_csrf_cookie
def felicitaciones(request):
    return pagina(
        request, "metas_felicitaciones", "felicitaciones-reclamos", "Felicitaciones y reclamos"
    )


ROLES_CUMPLIMIENTO_DELEGACION = (
    Rol.ADMINISTRADOR,
    Rol.JEFE_DELEGACIONES,
    Rol.ALCALDESA,
    Rol.DELEGADO_TERRITORIAL,
    Rol.ENCARGADO_AREA,
)


def _periodos_para_pantalla():
    """Períodos para el selector (la API de períodos no está abierta a todos los roles)."""
    return [
        {
            "id": p.pk,
            "texto": f"{p.fecha_inicio:%d-%m-%Y} a {p.fecha_termino:%d-%m-%Y}"
            + (" (vigente)" if p.estado == Periodo.VIGENTE else ""),
            "vigente": p.estado == Periodo.VIGENTE,
        }
        for p in Periodo.objects.order_by("-fecha_inicio", "-pk")
    ]


def _pagina_cumplimiento(request, activa, modo, delegaciones, funcionario_id=None):
    datos = contexto_usuario(request, activa)
    datos.update(
        menu_secciones=menu_para_usuario(request.user),
        config_cumplimiento={
            "modo": modo,
            "periodos": _periodos_para_pantalla(),
            "delegaciones": delegaciones,
            "funcionario_id": funcionario_id,
            "nombre": request.user.get_full_name() or request.user.email,
        },
    )
    return render(request, "metas/cumplimiento.html", datos)


@solo_roles(*ROLES_CUMPLIMIENTO_DELEGACION)
@ensure_csrf_cookie
def cumplimiento_delegacion(request):
    """Globales eligen entre todas las delegaciones; Delegado y Encargado quedan fijos en la suya."""
    usuario = request.user
    if rol_de_usuario(usuario) in (Rol.DELEGADO_TERRITORIAL, Rol.ENCARGADO_AREA):
        propias = Delegacion.objects.filter(pk=usuario.delegacion_id)
    else:
        propias = Delegacion.objects.all()
    delegaciones = [
        {"id": d.pk, "texto": f"{d.codigo} · {d.nombre}"} for d in propias.order_by("codigo")
    ]
    return _pagina_cumplimiento(
        request, "metas_cumplimiento_delegacion", "delegacion", delegaciones
    )


@solo_roles(Rol.FUNCIONARIO)
@ensure_csrf_cookie
def mi_cumplimiento(request):
    return _pagina_cumplimiento(
        request,
        "metas_mi_cumplimiento",
        "propio",
        [],
        funcionario_id=request.user.funcionario_id,
    )
