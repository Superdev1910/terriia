from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from core import auditoria
from core.views import MantenedorViewSet
from core.permissions import (
    IsAdministradorODelegado,
    IsAdministradorODelegadoOFuncionarioCrea,
    IsAdministradorODelegadoOFuncionarioLectura,
    IsOperativoCreaVecinos,
)

from .models import JuntaVecinos, MiembroJunta, Territorio, Vecino
from .serializers import (
    JuntaVecinosSerializer,
    MiembroJuntaSerializer,
    TerritorioSerializer,
    VecinoSerializer,
)


class VecinoViewSet(MantenedorViewSet):
    # Vecino no tiene delegación: crear lo hacen los roles operativos (desde Registrar actividad);
    # listar, editar y desactivar siguen siendo del Administrador.
    permission_classes = [IsOperativoCreaVecinos]
    queryset = Vecino.objects.prefetch_related(
        Prefetch("membresias", queryset=MiembroJunta.objects.select_related("junta"))
    )
    serializer_class = VecinoSerializer
    search_fields = ["rut", "nombres", "apellidos", "direccion"]
    filterset_fields = ["estado"]
    ordering_fields = "__all__"
    campo_estado = "estado"
    valor_inactivo = Vecino.INACTIVO


class TerritorioViewSet(MantenedorViewSet):
    permission_classes = [IsAdministradorODelegadoOFuncionarioLectura]
    funcionario_por_delegacion = True
    delegacion_lookup = "delegacion_id"
    queryset = Territorio.objects.select_related("delegacion").all()
    serializer_class = TerritorioSerializer
    search_fields = ["nombre", "delegacion__nombre", "delegacion__codigo"]
    filterset_fields = ["activo", "es_formal", "delegacion"]
    ordering_fields = "__all__"
    campo_estado = "activo"
    valor_inactivo = False


class JuntaVecinosViewSet(MantenedorViewSet):
    permission_classes = [IsAdministradorODelegadoOFuncionarioCrea]
    funcionario_por_delegacion = True
    delegacion_lookup = "territorio__delegacion_id"
    queryset = JuntaVecinos.objects.select_related(
        "territorio", "territorio__delegacion"
    ).prefetch_related(
        Prefetch(
            "miembros",
            queryset=MiembroJunta.objects.filter(estado=MiembroJunta.ACTIVO).select_related(
                "vecino"
            ),
            to_attr="miembros_activos",
        )
    )
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


class MiembroJuntaViewSet(MantenedorViewSet):
    """Membresía y dirigencia de las juntas. DELETE = desactivar (estado inactivo + fecha_salida),
    igual que los demás mantenedores con estado; el Delegado solo ve juntas de su delegación."""

    permission_classes = [IsAdministradorODelegado]
    delegacion_lookup = "junta__territorio__delegacion_id"
    queryset = MiembroJunta.objects.select_related("junta", "vecino").all()
    serializer_class = MiembroJuntaSerializer
    search_fields = ["vecino__rut", "vecino__nombres", "vecino__apellidos", "junta__nombre"]
    filterset_fields = ["junta", "vecino", "estado", "cargo"]
    ordering_fields = "__all__"
    campo_estado = "estado"
    valor_inactivo = MiembroJunta.INACTIVO

    def destroy(self, request, *args, **kwargs):
        miembro = self.get_object()
        with transaction.atomic():
            anterior = auditoria.foto(miembro)
            miembro.estado = MiembroJunta.INACTIVO
            if not miembro.fecha_salida:
                miembro.fecha_salida = max(timezone.localdate(), miembro.fecha_ingreso)
            miembro.save(update_fields=["estado", "fecha_salida"])
            auditoria.registrar(
                request.user,
                "desactivar",
                miembro,
                anterior=anterior,
                nuevo=auditoria.foto(miembro),
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
