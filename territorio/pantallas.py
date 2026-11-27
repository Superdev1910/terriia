from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie

from core.models import Rol
from core.permissions import rol_de_usuario, solo_roles, tiene_rol

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
        "Personas",
        [
            ("personas_mi_perfil", "Mis datos y metas", "bi-person-circle"),
            ("personas_usuarios", "Usuarios", "bi-person-gear"),
            ("personas_funcionarios", "Funcionarios", "bi-person-vcard"),
        ],
    ),
    (
        "Metas",
        [
            ("metas_dashboard_ejecutivo", "Dashboard ejecutivo", "bi-speedometer2"),
            ("metas_cumplimiento_delegacion", "Cumplimiento por delegación", "bi-bar-chart-steps"),
            ("metas_mi_cumplimiento", "Mi cumplimiento", "bi-graph-up-arrow"),
            ("metas_periodos", "Períodos", "bi-calendar-range"),
            ("metas_items", "Ítems", "bi-list-check"),
            ("metas_delegacion", "Metas por delegación", "bi-bullseye"),
            ("metas_individuales", "Metas individuales", "bi-person-check"),
            ("metas_felicitaciones", "Felicitaciones y reclamos", "bi-chat-heart"),
        ],
    ),
    ("Administración", [("core_roles", "Roles", "bi-shield-lock")]),
    (
        "Actividades",
        [
            ("atenciones_registrar", "Registrar actividad", "bi-journal-plus"),
            ("atenciones_mis_registros", "Mis registros", "bi-journal-text"),
            ("atenciones_seguimiento", "Seguimiento", "bi-clipboard-check"),
            ("atenciones_verificacion", "Verificación", "bi-patch-check"),
        ],
    ),
    (
        "Atenciones",
        [
            ("atenciones_tipos", "Tipos de atención", "bi-tags"),
            ("atenciones_sub_atenciones", "Sub atenciones", "bi-tag"),
        ],
    ),
    (
        "Reportes",
        [
            (
                "atenciones_reporte_solicitudes_resueltas",
                "Solicitudes resueltas",
                "bi-file-earmark-excel",
            )
        ],
    ),
]

PAGINAS_ACTIVIDADES = {  # SCRUM-62 y seguimiento (Épica 2)
    "atenciones_registrar",
    "atenciones_mis_registros",
    "atenciones_seguimiento",
}
PAGINAS_SOLO_NO_ADMIN = {
    "personas_mi_perfil",
    "metas_mi_cumplimiento",
}  # vistas del propio funcionario
PAGINAS_POR_ROL = {
    Rol.ENCARGADO_AREA: {
        *PAGINAS_ACTIVIDADES,
        "atenciones_verificacion",
        "metas_cumplimiento_delegacion",
    },
    Rol.JEFE_DELEGACIONES: {
        "metas_cumplimiento_delegacion",
        "atenciones_verificacion",
        "atenciones_reporte_solicitudes_resueltas",
    },
    Rol.DELEGADO_TERRITORIAL: {
        *PAGINAS_ACTIVIDADES,
        "atenciones_verificacion",
        "territorio_territorios",
        "territorio_juntas",
        "personas_funcionarios",
        "metas_delegacion",
        "metas_individuales",
        "metas_cumplimiento_delegacion",
    },
    Rol.FUNCIONARIO: {"personas_mi_perfil", "metas_mi_cumplimiento", *PAGINAS_ACTIVIDADES},
    Rol.ALCALDESA: {"metas_dashboard_ejecutivo", "metas_cumplimiento_delegacion"},
}


def menu_para_usuario(usuario):
    rol = rol_de_usuario(usuario)
    if rol == Rol.ADMINISTRADOR:
        return [
            (titulo, [item for item in paginas if item[0] not in PAGINAS_SOLO_NO_ADMIN])
            for titulo, paginas in MENU_SECCIONES
            if any(item[0] not in PAGINAS_SOLO_NO_ADMIN for item in paginas)
        ]
    permitidas = PAGINAS_POR_ROL.get(rol, set())
    return [
        (titulo, [item for item in paginas if item[0] in permitidas])
        for titulo, paginas in MENU_SECCIONES
        if any(item[0] in permitidas for item in paginas)
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
        "menu_secciones": menu_para_usuario(usuario),
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


@solo_roles(Rol.ADMINISTRADOR, Rol.DELEGADO_TERRITORIAL)
@ensure_csrf_cookie
def territorios(request):
    return pagina(request, "territorio_territorios", "territorios")


@solo_roles(Rol.ADMINISTRADOR, Rol.DELEGADO_TERRITORIAL)
@ensure_csrf_cookie
def juntas(request):
    return pagina(request, "territorio_juntas", "juntas-vecinos")
