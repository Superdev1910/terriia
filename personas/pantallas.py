"""Pantallas HTML de usuarios y funcionarios.

Las pantallas solo pintan la interfaz; los datos y los permisos reales viven en la API
(/api/usuarios/, /api/funcionarios/), que valida el rol en el servidor.
"""

from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from core.models import Rol
from organizacion.pantallas import contexto_usuario, solo_administrador, solo_roles
from territorio.pantallas import menu_para_usuario


def pagina(request, activa, entidad, extra=None):
    datos = contexto_usuario(request, activa)
    datos["menu_secciones"] = menu_para_usuario(request.user)
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


@solo_roles(Rol.ADMINISTRADOR, Rol.DELEGADO_TERRITORIAL)
@ensure_csrf_cookie
def funcionarios(request):
    return pagina(request, "personas_funcionarios", "funcionarios")


@solo_roles(Rol.FUNCIONARIO)
@ensure_csrf_cookie
def mi_perfil(request):
    datos = contexto_usuario(request, "personas_mi_perfil")
    datos["menu_secciones"] = menu_para_usuario(request.user)
    return render(
        request,
        "personas/mi_perfil.html",
        datos,
    )
