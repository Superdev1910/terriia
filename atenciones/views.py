from django_filters import rest_framework as filters

from core.views import MantenedorViewSet
from organizacion.models import Area
from organizacion.paginacion import PaginacionMantenedor

from .models import SubAtencion, TipoAtencion
from .serializers import SubAtencionSerializer, TipoAtencionSerializer


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
