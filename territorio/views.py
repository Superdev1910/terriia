from core.views import MantenedorViewSet

from .models import JuntaVecinos, Territorio, Vecino
from .serializers import JuntaVecinosSerializer, TerritorioSerializer, VecinoSerializer


class VecinoViewSet(MantenedorViewSet):
    queryset = Vecino.objects.all()
    serializer_class = VecinoSerializer
    search_fields = ["rut", "nombres", "apellidos", "direccion"]
    filterset_fields = ["estado"]
    ordering_fields = "__all__"
    campo_estado = "estado"
    valor_inactivo = Vecino.INACTIVO


class TerritorioViewSet(MantenedorViewSet):
    queryset = Territorio.objects.select_related("delegacion").all()
    serializer_class = TerritorioSerializer
    search_fields = ["nombre", "delegacion__nombre", "delegacion__codigo"]
    filterset_fields = ["activo", "es_formal", "delegacion"]
    ordering_fields = "__all__"
    campo_estado = "activo"
    valor_inactivo = False


class JuntaVecinosViewSet(MantenedorViewSet):
    queryset = JuntaVecinos.objects.select_related("territorio", "territorio__delegacion").all()
    serializer_class = JuntaVecinosSerializer
    search_fields = [
        "numero_registro",
        "nombre",
        "direccion",
        "presidente",
        "email",
        "territorio__nombre",
    ]
    filterset_fields = ["activa", "territorio", "territorio__delegacion"]
    ordering_fields = "__all__"
    campo_estado = "activa"
    valor_inactivo = False
