"""Pantallas HTML de los mantenedores de personas: usuarios y funcionarios (solo Administrador).

Las pantallas solo pintan la interfaz; los datos y los permisos reales viven en la API
(/api/usuarios/, /api/funcionarios/), que valida el rol en el servidor.
"""

from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from core.models import Rol
from organizacion.pantallas import contexto_usuario, solo_administrador
from territorio.pantallas import MENU_SECCIONES  # mismo menú lateral en todas las pantallas


def pagina(request, activa, entidad, extra=None):
    datos = contexto_usuario(request, activa)
    datos["menu_secciones"] = MENU_SECCIONES
    datos["entidad"] = entidad
    datos.update(extra or {})
    return render(request, "personas/mantenedor.html", datos)


@solo_administrador
@ensure_csrf_cookie
def usuarios(request):
    # Los roles van en la página (json_script): todavía no hay /api/roles/.
    roles = list(Rol.objects.values("id_rol", "nombre"))
    return pagina(
        request,
        "personas_usuarios",
        "usuarios",
        {"roles": roles, "id_usuario_actual": request.user.pk},
    )


@solo_administrador
@ensure_csrf_cookie
def funcionarios(request):
    return pagina(request, "personas_funcionarios", "funcionarios")
