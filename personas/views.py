from core.views import MantenedorViewSet
from organizacion.paginacion import PaginacionMantenedor

from .models import Usuario, Funcionario
from .serializers import UsuarioSerializer, FuncionarioSerializer


class UsuarioViewSet(MantenedorViewSet):
    queryset = Usuario.objects.select_related("rol", "funcionario", "delegacion").all()
    serializer_class = UsuarioSerializer
    pagination_class = PaginacionMantenedor  # la pantalla elige 10, 20 o 50 filas
    search_fields = ["email", "rut", "first_name", "last_name", "rol__nombre", "delegacion__nombre"]
    filterset_fields = ["estado", "rol", "delegacion"]
    ordering_fields = [
        "id_usuario",
        "email",
        "rut",
        "first_name",
        "last_name",
        "rol__nombre",
        "delegacion__codigo",
        "estado",
    ]
    campo_estado = "estado"


class FuncionarioViewSet(MantenedorViewSet):
    queryset = Funcionario.objects.select_related("cargo", "delegacion").all()
    serializer_class = FuncionarioSerializer
    pagination_class = PaginacionMantenedor
    search_fields = ["identificador_inst", "nombre", "cargo__nombre", "delegacion__nombre"]
    filterset_fields = ["estado", "delegacion", "cargo"]
    ordering_fields = [
        "id_funcionario",
        "identificador_inst",
        "nombre",
        "cargo__nombre",
        "delegacion__codigo",
        "estado",
    ]
    campo_estado = "estado"
