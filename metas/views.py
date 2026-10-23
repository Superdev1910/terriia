from core.views import MantenedorViewSet
from .models import Item, Periodo
from .serializers import ItemSerializer, PeriodoSerializer


class PeriodoViewSet(MantenedorViewSet):
    queryset = Periodo.objects.all()
    serializer_class = PeriodoSerializer
    search_fields = ["version_parametros"]
    filterset_fields = ["estado"]
    campo_estado = "estado"
    valor_inactivo = "cerrado"


class ItemViewSet(MantenedorViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    search_fields = ["nombre", "tipo_meta"]
    filterset_fields = [
        "activo",
        "cargo",
        "tipo_meta",
        "requiere_verificacion_previa",
    ]
    campo_estado = "activo"  # Borrado lógico mediante el booleano activo
