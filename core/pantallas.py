"""Pantalla HTML del mantenedor de roles (solo Administrador).

Solo pinta la interfaz; los datos y los permisos reales viven en /api/roles/.
Usa el mismo menú por secciones y el mismo control de acceso que las pantallas de territorio.
"""

from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from territorio.pantallas import contexto, solo_administrador


@solo_administrador
@ensure_csrf_cookie
def roles(request):
    return render(request, "core/roles.html", contexto(request, "core_roles"))
