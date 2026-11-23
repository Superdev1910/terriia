from decimal import Decimal
from django.db import transaction
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import status, views
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from core import auditoria
from core.permissions import IsAdministradorODelegado, IsAdministradorODelegadoLectura
from core.views import MantenedorViewSet
from organizacion.models import Delegacion
from personas.models import Funcionario
from .models import Item, MetaDelegacion, MetaIndividual, Periodo, RecalibracionMeta
from .serializers import (
    ItemSerializer,
    MetaDelegacionSerializer,
    MetaIndividualSerializer,
    PeriodoSerializer,
    RecalibracionMetaSerializer,
)
from .services import CalculoMetasService

SIN_BORRAR = ["get", "post", "put", "patch", "head", "options"]


class PeriodoViewSet(MantenedorViewSet):
    permission_classes = [IsAdministradorODelegadoLectura]
    delegado_lectura_global = True
    queryset = Periodo.objects.all()
    serializer_class = PeriodoSerializer
    search_fields = ["version_parametros"]
    filterset_fields = ["estado"]
    campo_estado = "estado"
    valor_inactivo = "cerrado"


class ItemViewSet(MantenedorViewSet):
    permission_classes = [IsAdministradorODelegadoLectura]
    delegacion_lookup = "cargo__area__delegacion_id"
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


class MetaDelegacionViewSet(MantenedorViewSet):
    permission_classes = [IsAdministradorODelegado]
    delegacion_lookup = "delegacion_id"
    delegacion_related_lookups = ("item__cargo__area__delegacion_id",)
    queryset = (
        MetaDelegacion.objects.select_related("item", "delegacion", "periodo")
        .annotate(
            suma_anotada=Coalesce(
                Sum("metas_individuales__valor_objetivo"),
                Value(Decimal("0")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .order_by("-periodo_id", "delegacion_id", "item_id")
    )
    serializer_class = MetaDelegacionSerializer
    search_fields = ["item__nombre", "delegacion__nombre"]
    filterset_fields = ["item", "item__cargo", "delegacion", "periodo"]
    http_method_names = SIN_BORRAR


class MetaIndividualViewSet(MantenedorViewSet):
    permission_classes = [IsAdministradorODelegado]
    delegacion_lookup = "meta_delegacion__delegacion_id"
    queryset = MetaIndividual.objects.select_related("meta_delegacion", "funcionario")
    serializer_class = MetaIndividualSerializer
    search_fields = ["funcionario__nombre", "funcionario__identificador_inst"]
    filterset_fields = [
        "meta_delegacion",
        "funcionario",
        "meta_delegacion__delegacion",
        "meta_delegacion__periodo",
    ]
    http_method_names = SIN_BORRAR

    @action(detail=True, methods=["post"], url_path="recalibrar")
    def recalibrar(self, request, pk=None):
        """HU12: ajusta la meta. Guarda motivo, fecha y usuario sin borrar el historial."""
        meta = self.get_object()
        serializer = RecalibracionMetaSerializer(
            data=request.data, context={"request": request, "meta": meta}
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            anterior = auditoria.foto(meta)
            recalibracion = serializer.save()
            meta.refresh_from_db()
            auditoria.registrar(
                request.user,
                "recalibrar",
                meta,
                anterior=anterior,
                nuevo=auditoria.foto(meta),
            )
        return Response(
            RecalibracionMetaSerializer(recalibracion).data,
            status=status.HTTP_201_CREATED,
        )


class RecalibracionMetaViewSet(MantenedorViewSet):
    """Historial de ajustes (solo lectura): se crea únicamente con /api/metas/<id>/recalibrar/."""

    queryset = RecalibracionMeta.objects.select_related("meta", "usuario")
    serializer_class = RecalibracionMetaSerializer
    search_fields = ["motivo"]
    filterset_fields = ["meta", "usuario"]
    http_method_names = ["get", "head", "options"]
    permission_classes = [IsAdministradorODelegado]
    delegacion_lookup = "meta__meta_delegacion__delegacion_id"


class DashboardFuncionarioView(views.APIView):
    """
    Endpoint para obtener el semáforo y cumplimiento individual de un funcionario.
    Ruta: GET /api/metas/dashboard/funcionario/<int:funcionario_id>/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, funcionario_id):
        periodo_id = request.query_params.get("periodo")
        if not periodo_id:
            periodo_vigente = Periodo.objects.filter(estado="vigente").first()
            if not periodo_vigente:
                return Response(
                    {"error": "No hay un período vigente activo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            periodo_id = periodo_vigente.pk

        resultado = CalculoMetasService.calcular_cumplimiento_funcionario(
            funcionario_id=funcionario_id, periodo_id=periodo_id
        )
        return Response(resultado, status=status.HTTP_200_OK)


class DashboardDelegacionView(views.APIView):
    """Endpoint consolidado por delegación (HU13 / HU22)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, delegacion_id):
        periodo_id = request.query_params.get("periodo")
        periodo = (
            Periodo.objects.get(pk=periodo_id)
            if periodo_id
            else Periodo.objects.filter(estado="vigente").first()
        )

        if not periodo:
            return Response(
                {"error": "No hay un período vigente activo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        funcionarios = Funcionario.objects.filter(delegacion_id=delegacion_id, estado="activo")
        resumen_funcionarios = []
        suma_cumplimiento = Decimal("0.00")

        for func in funcionarios:
            datos = CalculoMetasService.calcular_cumplimiento_funcionario(
                funcionario_id=func.pk, periodo_id=periodo.pk
            )
            resumen_funcionarios.append(
                {
                    "funcionario_id": func.pk,
                    "nombre": getattr(func, "nombre", getattr(func, "nombre_completo", "")),
                    "cumplimiento_computable": datos["cumplimiento_computable"],
                    "color_semaforo": datos["color_semaforo"],
                }
            )
            suma_cumplimiento += Decimal(str(datos["cumplimiento_computable"]))

        promedio_delegacion = (
            (suma_cumplimiento / len(funcionarios)) if funcionarios.exists() else Decimal("0.00")
        )

        return Response(
            {
                "delegacion_id": delegacion_id,
                "periodo_id": periodo.pk,
                "promedio_cumplimiento_delegacion": round(float(promedio_delegacion), 2),
                "total_funcionarios": len(funcionarios),
                "funcionarios": resumen_funcionarios,
            },
            status=status.HTTP_200_OK,
        )
