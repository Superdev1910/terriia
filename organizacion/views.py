from django.db import transaction
from django.db.models import Count, Q
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from core import auditoria
from core.permissions import IsAdministrador, IsAdministradorODelegadoLectura
from core.views import MantenedorViewSet

from .models import Area, Cargo, Delegacion
from .paginacion import PaginacionMantenedor
from .serializers import AreaSerializer, CargoSerializer, DelegacionSerializer

# --- Desactivación en cadena ------------------------------------------------------------
# Regla de negocio: al desactivar una delegación se desactivan sus áreas y los cargos de
# esas áreas; al desactivar un área, sus cargos dejan de estar vigentes. Nada se borra y cada
# registro afectado queda en auditoría. La pantalla avisa cuántos registros se verán afectados.
# Reactivar NO reactiva a los dependientes: se reactivan uno a uno, a propósito.


def _desactivar_cargos(usuario, area):
    for cargo in area.cargos.filter(vigente=True):
        anterior = auditoria.foto(cargo)
        cargo.vigente = False
        cargo.save(update_fields=["vigente"])
        auditoria.registrar(
            usuario, "desactivar", cargo, anterior=anterior, nuevo=auditoria.foto(cargo)
        )


def propagar_desactivacion_area(usuario, area):
    _desactivar_cargos(usuario, area)


def propagar_desactivacion_delegacion(usuario, delegacion):
    for area in delegacion.areas.all():
        if area.estado == Area.ACTIVA:
            anterior = auditoria.foto(area)
            area.estado = Area.INACTIVA
            area.save(update_fields=["estado"])
            auditoria.registrar(
                usuario, "desactivar", area, anterior=anterior, nuevo=auditoria.foto(area)
            )
        _desactivar_cargos(usuario, area)


class MantenedorOrganizacionViewSet(MantenedorViewSet):
    """MantenedorViewSet + paginación elegible + desactivación en cadena."""

    pagination_class = PaginacionMantenedor

    def propagar(self, usuario, instancia):
        """Desactiva a los dependientes. Las subclases con hijos lo reemplazan."""

    def destroy(self, request, *args, **kwargs):
        instancia = self.get_object()
        with transaction.atomic():
            respuesta = super().destroy(request, *args, **kwargs)
            self.propagar(request.user, instancia)
        return respuesta

    def perform_update(self, serializer):
        estaba_activo = self._esta_activo(serializer.instance)
        with transaction.atomic():
            super().perform_update(serializer)
            if estaba_activo and not self._esta_activo(serializer.instance):
                self.propagar(self.request.user, serializer.instance)

    def _esta_activo(self, instancia):
        return getattr(instancia, self.campo_estado) in (Area.ACTIVA, True)


class DelegacionViewSet(MantenedorOrganizacionViewSet):
    permission_classes = [IsAdministradorODelegadoLectura]
    delegacion_lookup = "pk"
    # Los contadores se calculan en la misma consulta del listado (sin una consulta por fila).
    queryset = Delegacion.objects.annotate(
        n_areas=Count("areas", distinct=True),
        n_areas_activas=Count("areas", filter=Q(areas__estado=Area.ACTIVA), distinct=True),
        n_cargos_vigentes=Count(
            "areas__cargos", filter=Q(areas__cargos__vigente=True), distinct=True
        ),
    ).order_by("codigo")
    serializer_class = DelegacionSerializer
    search_fields = ["codigo", "nombre", "ambito", "direccion", "comuna"]
    filterset_fields = ["estado"]
    ordering_fields = [
        "id_delegacion",
        "codigo",
        "nombre",
        "direccion",
        "comuna",
        "estado",
        "n_areas",
    ]
    campo_estado = "estado"

    def propagar(self, usuario, instancia):
        propagar_desactivacion_delegacion(usuario, instancia)

    @action(detail=True, methods=["get"])
    def detalle(self, request, pk=None):
        """La delegación con sus áreas y los cargos de cada una (panel lateral de la pantalla)."""
        delegacion = self.get_object()
        datos = DelegacionSerializer(delegacion).data
        areas = delegacion.areas.prefetch_related("cargos").order_by("prioridad")
        datos["areas"] = [
            {
                "id_area": a.id_area,
                "nombre": a.nombre,
                "nombre_texto": a.get_nombre_display(),
                "prioridad": a.prioridad,
                "estado": a.estado,
                "cargos": [
                    {"id_cargo": c.id_cargo, "nombre": c.nombre, "vigente": c.vigente}
                    for c in sorted(a.cargos.all(), key=lambda c: c.nombre.lower())
                ],
            }
            for a in areas
        ]
        return Response(datos)


class AreaViewSet(MantenedorOrganizacionViewSet):
    permission_classes = [IsAdministradorODelegadoLectura]
    delegacion_lookup = "delegacion_id"
    queryset = (
        Area.objects.select_related("delegacion")
        .annotate(n_cargos_vigentes=Count("cargos", filter=Q(cargos__vigente=True)))
        .order_by("delegacion__codigo", "prioridad")
    )
    serializer_class = AreaSerializer
    search_fields = ["nombre", "delegacion__codigo", "delegacion__nombre"]
    filterset_fields = ["estado", "delegacion", "nombre"]
    ordering_fields = ["id_area", "delegacion__codigo", "nombre", "prioridad", "estado"]
    campo_estado = "estado"

    def propagar(self, usuario, instancia):
        propagar_desactivacion_area(usuario, instancia)

    def perform_update(self, serializer):
        with transaction.atomic():
            super().perform_update(serializer)
            cambio = getattr(serializer, "intercambiada", None)
            if cambio:  # la otra área también cambió de prioridad: queda en auditoría
                otra, anterior = cambio
                auditoria.registrar(
                    self.request.user,
                    "editar",
                    otra,
                    anterior=anterior,
                    nuevo=auditoria.foto(otra),
                )


class CargoViewSet(MantenedorOrganizacionViewSet):
    permission_classes = [IsAdministradorODelegadoLectura]
    delegacion_lookup = "area__delegacion_id"
    queryset = Cargo.objects.select_related("area", "area__delegacion").all()
    serializer_class = CargoSerializer
    search_fields = ["nombre", "descripcion", "area__delegacion__nombre"]
    filterset_fields = ["vigente", "area"]
    ordering_fields = [
        "id_cargo",
        "nombre",
        "descripcion",
        "vigente",
        "area__delegacion__codigo",
    ]
    campo_estado = "vigente"


class ResumenView(APIView):
    """Cifras para la pantalla de inicio (solo Administrador)."""

    permission_classes = [IsAdministrador]

    def get(self, request):
        d = Delegacion.objects.aggregate(
            total=Count("pk"), activas=Count("pk", filter=Q(estado=Delegacion.ACTIVA))
        )
        a = Area.objects.aggregate(
            total=Count("pk"), activas=Count("pk", filter=Q(estado=Area.ACTIVA))
        )
        c = Cargo.objects.aggregate(
            total=Count("pk"),
            vigentes=Count("pk", filter=Q(vigente=True)),
            transversales=Count("pk", filter=Q(area__isnull=True)),
        )
        return Response(
            {
                "delegaciones": {**d, "inactivas": d["total"] - d["activas"]},
                "areas": {**a, "inactivas": a["total"] - a["activas"]},
                "cargos": {**c, "no_vigentes": c["total"] - c["vigentes"]},
            }
        )
