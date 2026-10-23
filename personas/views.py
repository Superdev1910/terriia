from core.views import MantenedorViewSet

from .models import Usuario, Funcionario
from .serializers import UsuarioSerializer, FuncionarioSerializer


class UsuarioViewSet(MantenedorViewSet):
    queryset = Usuario.objects.select_related("rol", "funcionario", "delegacion").all()
    serializer_class = UsuarioSerializer
    search_fields = ["email", "rut", "first_name", "last_name"]
    filterset_fields = ["estado", "rol", "delegacion"]
    campo_estado = "estado"


class FuncionarioViewSet(MantenedorViewSet):
    queryset = Funcionario.objects.select_related("cargo", "delegacion").all()
    serializer_class = FuncionarioSerializer
    search_fields = ["identificador_inst", "nombre"]
    filterset_fields = ["estado", "delegacion", "cargo"]
    campo_estado = "estado"
