from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import IsAdministradorODelegadoOMiPerfil, IsFuncionario
from core.views import MantenedorViewSet
from organizacion.paginacion import PaginacionMantenedor
from metas.models import MetaIndividual

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
    permission_classes = [IsAdministradorODelegadoOMiPerfil]
    delegacion_lookup = "delegacion_id"
    delegacion_related_lookups = ("cargo__area__delegacion_id",)
    funcionario_lookup = "pk"
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


class MiPerfilView(APIView):
    """Datos propios y metas asignadas del usuario con rol Funcionario."""

    permission_classes = [IsFuncionario]

    def get(self, request):
        funcionario = request.user.funcionario
        metas = (
            MetaIndividual.objects.filter(
                funcionario=funcionario,
                meta_delegacion__delegacion_id=funcionario.delegacion_id,
            )
            .select_related(
                "meta_delegacion__item",
                "meta_delegacion__periodo",
                "meta_delegacion__delegacion",
            )
            .order_by("meta_delegacion__periodo__fecha_inicio", "id_meta")
        )
        return Response(
            {
                "funcionario": {
                    "nombre": funcionario.nombre,
                    "identificador_inst": funcionario.identificador_inst,
                    "cargo": funcionario.cargo.nombre,
                    "delegacion": funcionario.delegacion.nombre,
                },
                "metas": [
                    {
                        "item": meta.meta_delegacion.item.nombre,
                        "delegacion": meta.meta_delegacion.delegacion.nombre,
                        "periodo_inicio": meta.meta_delegacion.periodo.fecha_inicio,
                        "periodo_termino": meta.meta_delegacion.periodo.fecha_termino,
                        "valor_objetivo": str(meta.valor_objetivo),
                        "unidad": meta.unidad or "",
                    }
                    for meta in metas
                ],
            }
        )
