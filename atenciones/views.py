from django_filters import rest_framework as filters
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Rol
from core.permissions import rol_de_usuario
from core.validators import normalizar_rut, rut_es_valido
from core.views import MantenedorViewSet
from metas.models import Item
from organizacion.models import Area
from organizacion.paginacion import PaginacionMantenedor
from territorio.models import Territorio, Vecino

from .models import Actividad, SubAtencion, TipoAtencion
from .reglas import vecino_pertenece_a_delegacion
from .serializers import ActividadSerializer, SubAtencionSerializer, TipoAtencionSerializer


class TipoAtencionViewSet(MantenedorViewSet):
    queryset = TipoAtencion.objects.all()
    serializer_class = TipoAtencionSerializer
    pagination_class = PaginacionMantenedor  # page_size=100 para llenar los select
    search_fields = ["nombre"]
    filterset_fields = ["area", "activo"]
    campo_estado = "activo"
    valor_inactivo = False


class SubAtencionFiltro(filters.FilterSet):
    """?area= filtra por el área del tipo de atención (igual que en /api/tipos-atencion/)."""

    area = filters.ChoiceFilter(field_name="tipo_atencion__area", choices=Area.NOMBRES)

    class Meta:
        model = SubAtencion
        fields = ["area", "tipo_atencion", "activo"]


class SubAtencionViewSet(MantenedorViewSet):
    queryset = SubAtencion.objects.select_related("tipo_atencion").all()
    serializer_class = SubAtencionSerializer
    pagination_class = PaginacionMantenedor
    search_fields = ["nombre", "tipo_atencion__nombre"]
    filterset_class = SubAtencionFiltro
    campo_estado = "activo"
    valor_inactivo = False


# --- Actividades (SCRUM-62) -----------------------------------------------

ROLES_QUE_REGISTRAN = (
    Rol.ADMINISTRADOR,
    Rol.DELEGADO_TERRITORIAL,
    Rol.ENCARGADO_AREA,
    Rol.FUNCIONARIO,
)
ROLES_QUE_CONSULTAN = ROLES_QUE_REGISTRAN + (Rol.JEFE_DELEGACIONES, Rol.ALCALDESA)


def tiene_ficha_activa(user):
    return bool(user.funcionario_id) and user.funcionario.estado == "activo"


class PuedeRegistrarActividades(BasePermission):
    """Leer: cualquier rol con alcance. Escribir: solo roles que registran y con ficha activa."""

    message = "No tienes permiso para registrar actividades."

    def has_permission(self, request, view):
        user = request.user
        rol = rol_de_usuario(user)  # None si es anónimo
        if request.method in SAFE_METHODS:
            if getattr(view, "action", None) == "opciones":
                return rol in ROLES_QUE_REGISTRAN and tiene_ficha_activa(user)
            return rol in ROLES_QUE_CONSULTAN
        if request.method != "POST":
            return rol is not None  # PUT/PATCH/DELETE: el ViewSet responde 405
        return rol in ROLES_QUE_REGISTRAN and tiene_ficha_activa(user)


def filtrar_por_alcance(queryset, user, lookup):
    """Admin y usuarios sin delegación (acceso global) ven todo; el resto, su delegación."""
    if rol_de_usuario(user) == Rol.ADMINISTRADOR or user.delegacion_id is None:
        return queryset
    return queryset.filter(**{lookup: user.delegacion_id})


class ActividadFiltro(filters.FilterSet):
    desde = filters.DateFilter(field_name="fecha", lookup_expr="date__gte")
    hasta = filters.DateFilter(field_name="fecha", lookup_expr="date__lte")
    mis_registros = filters.BooleanFilter(method="filtrar_mis_registros")

    class Meta:
        model = Actividad
        fields = ["tipo_registro", "estado", "estado_verificacion", "pondera", "item", "area"]

    def filtrar_mis_registros(self, queryset, nombre, valor):
        if valor:
            return queryset.filter(funcionario_id=self.request.user.funcionario_id)
        return queryset


class ActividadViewSet(MantenedorViewSet):
    """Alta y consulta de actividades. No se borran ni se editan desde la API (405)."""

    permission_classes = [PuedeRegistrarActividades]
    queryset = Actividad.objects.select_related(
        "funcionario", "item", "vecino", "territorio", "area", "tipo_atencion", "sub_atencion"
    )
    serializer_class = ActividadSerializer
    filterset_class = ActividadFiltro
    search_fields = ["codigo", "descripcion", "vecino__rut", "vecino__nombres", "vecino__apellidos"]
    ordering_fields = ["fecha", "fecha_registro", "codigo"]
    http_method_names = ["get", "post", "head", "options"]
    # TODO(Fernando): permitir editar/anular con rol y delegación cuando se defina el flujo.

    def get_queryset(self):
        # super(MantenedorViewSet, self): se salta el alcance genérico y usa el de actividades.
        user = self.request.user
        queryset = filtrar_por_alcance(
            super(MantenedorViewSet, self).get_queryset(), user, "funcionario__delegacion_id"
        )
        if rol_de_usuario(user) == Rol.FUNCIONARIO:
            return queryset.filter(funcionario_id=user.funcionario_id)  # solo lo propio
        return queryset

    @action(detail=False, methods=["get"])
    def opciones(self, request):
        """Catálogos que el usuario puede usar al registrar (según su cargo y delegación)."""
        funcionario = request.user.funcionario
        delegacion_id = funcionario.delegacion_id
        return Response(
            {
                "items": list(
                    Item.objects.filter(cargo_id=funcionario.cargo_id, activo=True)
                    .order_by("nombre")
                    .values("id_item", "nombre")
                ),
                "areas": [
                    {"id_area": a.id_area, "nombre": a.nombre, "texto": a.get_nombre_display()}
                    for a in Area.objects.filter(delegacion_id=delegacion_id, estado="activa")
                ],
                "territorios": list(
                    Territorio.objects.filter(delegacion_id=delegacion_id, activo=True)
                    .order_by("nombre")
                    .values("id_territorio", "nombre")
                ),
                "tipos_atencion": list(
                    TipoAtencion.objects.filter(activo=True).values(
                        "id_tipo_atencion", "area", "nombre"
                    )
                ),
                "sub_atenciones": list(
                    SubAtencion.objects.filter(activo=True, tipo_atencion__activo=True).values(
                        "id_sub_atencion", "tipo_atencion", "nombre"
                    )
                ),
            }
        )


class BuscarVecinoView(APIView):
    """GET /api/vecinos/buscar/?rut= para autocompletar el formulario de actividades."""

    permission_classes = [PuedeRegistrarActividades]

    def get(self, request):
        rut = normalizar_rut(request.query_params.get("rut", ""))
        if not rut_es_valido(rut):
            return Response(
                {"error": "RUT inválido.", "campo": "rut"}, status=status.HTTP_400_BAD_REQUEST
            )
        vecino = Vecino.objects.filter(rut=rut, estado=Vecino.ACTIVO).first()
        delegacion_id = request.user.delegacion_id
        if vecino and rol_de_usuario(request.user) != Rol.ADMINISTRADOR and delegacion_id:
            if not vecino_pertenece_a_delegacion(vecino, delegacion_id):
                vecino = None  # no se revela que existe en otra delegación
        if vecino is None:
            return Response(
                {"error": "No hay un vecino con ese RUT en tu delegación.", "campo": "rut"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "id_vecino": vecino.id_vecino,
                "rut": vecino.rut,
                "nombres": vecino.nombres,
                "apellidos": vecino.apellidos,
                "telefono": vecino.telefono,
                "direccion": vecino.direccion,
            }
        )
