from core.views import MantenedorViewSet
from .models import Periodo
from .serializers import PeriodoSerializer


class PeriodoViewSet(MantenedorViewSet):
    queryset = Periodo.objects.all()
    serializer_class = PeriodoSerializer
    search_fields = ["version_parametros"]
    filterset_fields = ["estado"]
    campo_estado = "estado"
    valor_inactivo = "cerrado"
