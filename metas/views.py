from decimal import Decimal
from django.db import transaction
from django.db.models import Count, DecimalField, Max, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import status, views
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from core import auditoria
from atenciones.verificacion import acceso_global
from core.models import Rol
from core.permissions import (
    IsAdministradorODelegado,
    IsAdministradorODelegadoLectura,
    rol_de_usuario,
)
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from .models import (
    Item,
    Periodo,
    MetaDelegacion,
    MetaIndividual,
    RecalibracionMeta,
    FelicitacionReclamo,
)
from core.views import MantenedorViewSet
from atenciones.models import Actividad
from organizacion.models import Area, Delegacion
from personas.models import Funcionario
from .models import Item, MetaDelegacion, MetaIndividual, Periodo, RecalibracionMeta
from .serializers import (
    ItemSerializer,
    MetaDelegacionSerializer,
    MetaIndividualSerializer,
    PeriodoSerializer,
    RecalibracionMetaSerializer,
    FelicitacionReclamoSerializer,
)
from .cumplimiento import _limites_del_periodo
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


class FelicitacionReclamoViewSet(MantenedorViewSet):
    queryset = FelicitacionReclamo.objects.select_related("funcionario", "usuario_autoriza")
    serializer_class = FelicitacionReclamoSerializer
    search_fields = ["motivo", "funcionario__nombre", "funcionario__identificador_inst"]
    filterset_fields = {
        "funcionario": ["exact"],
        "funcionario__delegacion": ["exact"],
        "tipo": ["exact"],
        "fecha": ["gte", "lte"],
    }
    http_method_names = ["get", "post", "head", "options"]


def _periodo_del_dashboard(request):
    """Período pedido en ?periodo= (400 si no es numérico, 404 si no existe) o el vigente."""
    valor = request.query_params.get("periodo")
    if valor:
        try:
            pk = int(valor) if valor.isdecimal() else None
        except ValueError:
            pk = None
        if pk is None:
            raise ValidationError({"periodo": "Debe ser un número."})
        try:
            return Periodo.objects.get(pk=pk)
        except Periodo.DoesNotExist:
            raise NotFound("El período no existe.")
    periodo = Periodo.objects.filter(estado="vigente").first()
    if not periodo:
        raise ValidationError({"error": "No hay un período vigente activo."})
    return periodo


class DashboardFuncionarioView(views.APIView):
    """
    Endpoint para obtener el semáforo y cumplimiento individual de un funcionario.
    Ruta: GET /api/metas/dashboard/funcionario/<int:funcionario_id>/
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, funcionario_id):
        usuario = request.user
        try:
            funcionario = Funcionario.objects.get(pk=funcionario_id)
        except Funcionario.DoesNotExist:
            raise NotFound("El funcionario no existe.")
        rol = rol_de_usuario(usuario)
        if acceso_global(usuario):
            permitido = True
        elif rol == Rol.FUNCIONARIO:
            permitido = usuario.funcionario_id == funcionario.pk
        elif rol in (Rol.DELEGADO_TERRITORIAL, Rol.ENCARGADO_AREA):
            permitido = (
                usuario.delegacion_id is not None
                and usuario.delegacion_id == funcionario.delegacion_id
            )
        else:
            permitido = False
        if not permitido:
            raise PermissionDenied("No tiene permiso para ver este funcionario.")

        periodo = _periodo_del_dashboard(request)
        resultado = CalculoMetasService.calcular_cumplimiento_funcionario(
            funcionario_id=funcionario.pk, periodo_id=periodo.pk
        )
        return Response(resultado, status=status.HTTP_200_OK)


class DashboardDelegacionView(views.APIView):
    """Endpoint consolidado por delegación (HU13)."""

    permission_classes = [IsAuthenticated]

    def get(self, request, delegacion_id):
        usuario = request.user
        if not Delegacion.objects.filter(pk=delegacion_id).exists():
            raise NotFound("La delegación no existe.")
        if not acceso_global(usuario):
            es_responsable = rol_de_usuario(usuario) in (
                Rol.DELEGADO_TERRITORIAL,
                Rol.ENCARGADO_AREA,
            )
            if not (es_responsable and usuario.delegacion_id == delegacion_id):
                raise PermissionDenied("No tiene permiso para ver esta delegación.")

        periodo = _periodo_del_dashboard(request)

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


def _delegacion_del_dashboard(request):
    """Delegación pedida en ?delegacion= (400 si no es numérica, 404 si no existe) o None."""
    valor = request.query_params.get("delegacion")
    if not valor:
        return None
    if not valor.isascii() or not valor.isdecimal():
        raise ValidationError({"delegacion": "Debe ser un número."})
    try:
        return Delegacion.objects.get(pk=int(valor))
    except Delegacion.DoesNotExist:
        raise NotFound("La delegación no existe.")


def _serie(etiquetas, conteos):
    return [
        {"clave": clave, "etiqueta": etiqueta, "cantidad": conteos.get(clave, 0)}
        for clave, etiqueta in etiquetas
    ]


def _indicadores_actividad(total, ultimo, periodo, hoy):
    """Fecha y días desde el último ingreso, total y promedio diario dentro del período."""
    dias_periodo = max((min(hoy, periodo.fecha_termino) - periodo.fecha_inicio).days + 1, 1)
    return {
        "total_ingresos": total,
        "fecha_ultimo_ingreso": ultimo,
        "dias_desde_ultimo_ingreso": max((hoy - ultimo).days, 0) if ultimo else None,
        "promedio_ingresos_diarios": round(total / dias_periodo, 2),
    }


def _volumenes_por_delegacion(periodo, delegacion_ids):
    """Solicitudes (Actividad) del período por estado y área, solo agregados (3 consultas)."""
    inicio, fin = _limites_del_periodo(periodo)
    base = Actividad.objects.filter(
        fecha__gte=inicio, fecha__lt=fin, funcionario__delegacion_id__in=delegacion_ids
    ).order_by()
    por_estado, por_area, totales = {}, {}, {}
    for fila in base.values("funcionario__delegacion_id", "estado").annotate(n=Count("pk")):
        por_estado.setdefault(fila["funcionario__delegacion_id"], {})[fila["estado"]] = fila["n"]
    for fila in base.values("funcionario__delegacion_id", "area__nombre").annotate(n=Count("pk")):
        clave = fila["area__nombre"] or ""
        por_area.setdefault(fila["funcionario__delegacion_id"], {})[clave] = fila["n"]
    for fila in base.values("funcionario__delegacion_id").annotate(
        n=Count("pk"), ultimo=Max("fecha")
    ):
        ultimo = fila["ultimo"]
        totales[fila["funcionario__delegacion_id"]] = (
            fila["n"],
            timezone.localtime(ultimo).date() if ultimo else None,
        )
    return por_estado, por_area, totales


def _armar_volumen(por_estado, por_area):
    areas = Area.NOMBRES + [("", "Sin área")]
    return {
        "total": sum(por_estado.values()),
        "por_estado": _serie(Actividad.ESTADOS, por_estado),
        "por_area": _serie(areas, por_area),
    }


class DashboardEjecutivoView(views.APIView):
    """Dashboard ejecutivo agregado, sin registros individuales."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if rol_de_usuario(request.user) not in (Rol.ADMINISTRADOR, Rol.ALCALDESA):
            raise PermissionDenied("No tiene permiso para ver el dashboard ejecutivo.")

        periodo = _periodo_del_dashboard(request)
        delegacion_filtrada = _delegacion_del_dashboard(request)
        if delegacion_filtrada:
            delegaciones = [delegacion_filtrada]
        else:
            delegaciones = list(Delegacion.objects.order_by("codigo"))
        ids_delegaciones = [delegacion.pk for delegacion in delegaciones]
        funcionarios = Funcionario.objects.filter(
            estado=Funcionario.ACTIVO, delegacion_id__in=ids_delegaciones
        ).order_by("delegacion_id", "pk")
        hoy = timezone.localdate()
        vol_estado, vol_area, vol_total = _volumenes_por_delegacion(periodo, ids_delegaciones)
        global_estado, global_area = {}, {}
        total_global_ingresos, ultimo_global = 0, None
        sumas = {delegacion.pk: Decimal("0.00") for delegacion in delegaciones}
        cantidades = {delegacion.pk: 0 for delegacion in delegaciones}

        computables = CalculoMetasService.calcular_computable_por_funcionario(
            periodo, [funcionario.pk for funcionario in funcionarios]
        )
        for funcionario in funcionarios:
            # Mismo redondeo a 2 decimales que el cálculo individual
            sumas[funcionario.delegacion_id] += Decimal(
                str(round(float(computables[funcionario.pk]), 2))
            )
            cantidades[funcionario.delegacion_id] += 1

        porcentaje_esperado = CalculoMetasService.calcular_porcentaje_esperado(periodo)
        resumen_delegaciones = []
        suma_global = Decimal("0.00")
        cantidad_global = 0

        for delegacion in delegaciones:
            cantidad = cantidades[delegacion.pk]
            cumplimiento = sumas[delegacion.pk] / cantidad if cantidad else Decimal("0.00")
            suma_global += sumas[delegacion.pk]
            cantidad_global += cantidad
            for clave, n in vol_estado.get(delegacion.pk, {}).items():
                global_estado[clave] = global_estado.get(clave, 0) + n
            for clave, n in vol_area.get(delegacion.pk, {}).items():
                global_area[clave] = global_area.get(clave, 0) + n
            total_d, ultimo_d = vol_total.get(delegacion.pk, (0, None))
            total_global_ingresos += total_d
            if ultimo_d and (ultimo_global is None or ultimo_d > ultimo_global):
                ultimo_global = ultimo_d
            resumen_delegaciones.append(
                {
                    "delegacion_id": delegacion.pk,
                    "codigo": delegacion.codigo,
                    "nombre": delegacion.nombre,
                    "cumplimiento_pct": round(float(cumplimiento), 2),
                    "porcentaje_esperado": round(float(porcentaje_esperado), 2),
                    "color_semaforo": CalculoMetasService.calcular_color_semaforo(
                        cumplimiento, porcentaje_esperado
                    ),
                    "volumen": _armar_volumen(
                        vol_estado.get(delegacion.pk, {}), vol_area.get(delegacion.pk, {})
                    ),
                    "indicadores_actividad": _indicadores_actividad(
                        total_d, ultimo_d, periodo, hoy
                    ),
                }
            )

        cumplimiento_global = suma_global / cantidad_global if cantidad_global else Decimal("0.00")
        return Response(
            {
                "periodo": {
                    "id": periodo.pk,
                    "fecha_inicio": periodo.fecha_inicio,
                    "fecha_termino": periodo.fecha_termino,
                },
                "cumplimiento_global_pct": round(float(cumplimiento_global), 2),
                "porcentaje_esperado": round(float(porcentaje_esperado), 2),
                "delegacion_filtro": delegacion_filtrada.pk if delegacion_filtrada else None,
                "volumen_global": _armar_volumen(global_estado, global_area),
                "indicadores_actividad_global": _indicadores_actividad(
                    total_global_ingresos, ultimo_global, periodo, hoy
                ),
                "delegaciones": resumen_delegaciones,
            },
            status=status.HTTP_200_OK,
        )
