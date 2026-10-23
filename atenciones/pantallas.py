"""Pantallas HTML de los catálogos de atención (solo Administrador).

Igual que en organizacion y territorio: la pantalla solo pinta la interfaz; los datos y los
permisos reales viven en /api/tipos-atencion/ y /api/sub-atenciones/.
"""

from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from organizacion.models import Area
from organizacion.pantallas import contexto_usuario, solo_administrador
from territorio.pantallas import MENU_SECCIONES


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
