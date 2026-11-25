"""Pantallas HTML de los catálogos de atención (solo Administrador).

Igual que en organizacion y territorio: la pantalla solo pinta la interfaz; los datos y los
permisos reales viven en /api/tipos-atencion/ y /api/sub-atenciones/.
"""

from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from core.models import Rol
from core.permissions import rol_de_usuario, solo_roles
from organizacion.models import Area
from organizacion.pantallas import contexto_usuario, solo_administrador
from territorio.pantallas import MENU_SECCIONES

from .verificacion import ROLES_VERIFICADORES, tiene_ficha_activa


def pagina(request, activa, entidad):
    datos = contexto_usuario(request, activa)
    datos.update(
        {
            "menu_secciones": MENU_SECCIONES,  # mismo menú por secciones que territorio
            "entidad": entidad,
            "areas": [{"v": valor, "t": texto} for valor, texto in Area.NOMBRES],
        }
    )
    return render(request, "atenciones/mantenedor.html", datos)


@solo_administrador
@ensure_csrf_cookie
def tipos_atencion(request):
    return pagina(request, "atenciones_tipos", "tipos-atencion")


@solo_administrador
@ensure_csrf_cookie
def sub_atenciones(request):
    return pagina(request, "atenciones_sub_atenciones", "sub-atenciones")


# --- Ingreso de actividades (SCRUM-62): lo usan los roles que registran ---------------------

solo_quienes_registran = solo_roles(
    Rol.ADMINISTRADOR, Rol.DELEGADO_TERRITORIAL, Rol.ENCARGADO_AREA, Rol.FUNCIONARIO
)


@solo_quienes_registran
@ensure_csrf_cookie
def registrar_actividad(request):
    datos = contexto_usuario(request, "atenciones_registrar")
    datos["sin_ficha"] = not tiene_ficha_activa(request.user)  # sin ficha no se puede registrar
    return render(request, "atenciones/actividad_registrar.html", datos)


@solo_quienes_registran
@ensure_csrf_cookie
def mis_registros(request):
    return render(
        request,
        "atenciones/actividad_mis_registros.html",
        contexto_usuario(request, "atenciones_mis_registros"),
    )


@solo_roles(*ROLES_VERIFICADORES)
@ensure_csrf_cookie
def verificacion(request):
    return render(
        request,
        "atenciones/actividad_verificacion.html",
        contexto_usuario(request, "atenciones_verificacion"),
    )


# --- Seguimiento de actividades (Épica 2) --------------------------------------------------

CODIGO_ROL = {
    Rol.ADMINISTRADOR: "admin",
    Rol.DELEGADO_TERRITORIAL: "delegado",
    Rol.ENCARGADO_AREA: "encargado",
    Rol.FUNCIONARIO: "funcionario",
}


@solo_quienes_registran
@ensure_csrf_cookie
def seguimiento(request):
    datos = contexto_usuario(request, "atenciones_seguimiento")
    # Solo para decidir qué botones se muestran; el servidor valida cada acción igualmente.
    datos["rol_codigo"] = CODIGO_ROL[rol_de_usuario(request.user)]
    datos["mi_funcionario"] = request.user.funcionario_id
    return render(request, "atenciones/actividad_seguimiento.html", datos)
