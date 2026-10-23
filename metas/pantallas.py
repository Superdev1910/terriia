"""Pantallas HTML de los mantenedores de metas (solo Administrador).

Las pantallas solo pintan la interfaz; los datos, las reglas y los permisos reales viven en
la API (/api/periodos/, /api/items/, /api/metas-delegacion/, /api/metas/), que valida el rol
en el servidor.
"""

from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from organizacion.pantallas import contexto_usuario, solo_administrador
from territorio.pantallas import MENU_SECCIONES  # menú lateral común, con la sección Metas


def pagina(request, activa, entidad, titulo):
    datos = contexto_usuario(request, activa)
    datos.update(menu_secciones=MENU_SECCIONES, entidad=entidad, titulo=titulo)
    return render(request, "metas/mantenedor.html", datos)


@solo_administrador
@ensure_csrf_cookie
def periodos(request):
    return pagina(request, "metas_periodos", "periodos", "Períodos")


@solo_administrador
@ensure_csrf_cookie
def items(request):
    return pagina(request, "metas_items", "items", "Ítems")


@solo_administrador
@ensure_csrf_cookie
def metas_delegacion(request):
    return pagina(request, "metas_delegacion", "metas-delegacion", "Metas por delegación")


@solo_administrador
@ensure_csrf_cookie
def metas_individuales(request):
    return pagina(request, "metas_individuales", "metas", "Metas individuales")
