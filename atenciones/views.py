import os

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core import auditoria
from core.models import Rol
from core.permissions import rol_de_usuario
from core.validators import normalizar_rut, rut_es_valido
from core.views import MantenedorViewSet
from metas.models import Item
from organizacion.models import Area
from organizacion.paginacion import PaginacionMantenedor
from personas.models import Funcionario
from territorio.models import Territorio, Vecino

from . import reglas, verificacion
from .models import Actividad, Evidencia, SubAtencion, TipoAtencion
from .serializers import (
    ActividadSerializer,
    EvidenciaSerializer,
    HistorialVerificacionSerializer,
    SubAtencionSerializer,
    TipoAtencionSerializer,
    VerificarSerializer,
)


class TipoAtencionViewSet(MantenedorViewSet):
    queryset = TipoAtencion.objects.all()
    serializer_class = TipoAtencionSerializer
    pagination_class = PaginacionMantenedor  # page_size=100 para llenar los select
    search_fields = ["nombre"]
    filterset_fields = ["area", "activo"]
    campo_estado = "activo"
    valor_inactivo = False


class SubAtencionFiltro(filters.FilterSet):
    """?area= filtra por el área del tipo de atención (igual que en /api/tipos-atencion/)."""

    area = filters.ChoiceFilter(field_name="tipo_atencion__area", choices=Area.NOMBRES)

    class Meta:
        model = SubAtencion
        fields = ["area", "tipo_atencion", "activo"]


class SubAtencionViewSet(MantenedorViewSet):
    queryset = SubAtencion.objects.select_related("tipo_atencion").all()
    serializer_class = SubAtencionSerializer
    pagination_class = PaginacionMantenedor
    search_fields = ["nombre", "tipo_atencion__nombre"]
    filterset_class = SubAtencionFiltro
    campo_estado = "activo"
    valor_inactivo = False


# --- Actividades (SCRUM-62) -----------------------------------------------

ROLES_QUE_REGISTRAN = (
    Rol.ADMINISTRADOR,
    Rol.DELEGADO_TERRITORIAL,
    Rol.ENCARGADO_AREA,
    Rol.FUNCIONARIO,
)
ROLES_QUE_CONSULTAN = ROLES_QUE_REGISTRAN + (Rol.JEFE_DELEGACIONES, Rol.ALCALDESA)


tiene_ficha_activa = verificacion.tiene_ficha_activa


class PuedeRegistrarActividades(BasePermission):
    """Leer: cualquier rol con alcance. Escribir: solo roles que registran y con ficha activa.
    Sin acceso global ni delegación asignada no se entra (403)."""

    message = "No tienes permiso para registrar actividades."

    def has_permission(self, request, view):
        user = request.user
        rol = rol_de_usuario(user)  # None si es anónimo
        if rol is None or not verificacion.tiene_alcance(user):
            return False
        if request.method in SAFE_METHODS:
            if getattr(view, "action", None) == "opciones":
                return rol in ROLES_QUE_REGISTRAN and tiene_ficha_activa(user)
            return rol in ROLES_QUE_CONSULTAN
        if request.method == "POST":
            return rol in ROLES_QUE_REGISTRAN and tiene_ficha_activa(user)
        # PUT/PATCH: además del rol, solo el autor con ficha activa edita (validar_edicion
        # responde 403 o 409); DELETE: el ViewSet responde 405.
        return True


class PuedeVerificar(BasePermission):
    """Delegado, Encargado de área, Jefe de delegaciones y Administrador (el alcance se ve
    por actividad en atenciones/verificacion.py)."""

    message = "Tu rol no puede verificar actividades."

    def has_permission(self, request, view):
        user = request.user
        return rol_de_usuario(user) in verificacion.ROLES_VERIFICADORES and (
            verificacion.tiene_alcance(user)
        )


class PuedeConsultarEvidencias(BasePermission):
    message = "No tienes permiso para ver evidencias."

    def has_permission(self, request, view):
        user = request.user
        return rol_de_usuario(user) in ROLES_QUE_CONSULTAN and verificacion.tiene_alcance(user)


class PuedeBuscarVecino(BasePermission):
    """Autocompletado por RUT: solo roles que registran actividades, con alcance."""

    message = "No tienes permiso para buscar vecinos."

    def has_permission(self, request, view):
        user = request.user
        return rol_de_usuario(user) in ROLES_QUE_REGISTRAN and verificacion.tiene_alcance(user)


def filtrar_por_alcance(queryset, user, lookup):
    """Admin, Jefe de delegaciones y Alcaldesa ven todo; el resto, su delegación; sin
    delegación (y sin acceso global) no ve nada."""
    if verificacion.acceso_global(user):
        return queryset
    if user.delegacion_id is None:
        return queryset.none()
    return queryset.filter(**{lookup: user.delegacion_id})


def actividad_conflicto(exc):
    """El bloqueo del modelo (actividad aprobada) lanza ValidationError de Django: nunca 500."""
    if isinstance(exc, DjangoValidationError):
        return verificacion.Conflicto(exc.messages[0])
    return exc


class ActividadFiltro(filters.FilterSet):
    desde = filters.DateFilter(field_name="fecha", lookup_expr="date__gte")
    hasta = filters.DateFilter(field_name="fecha", lookup_expr="date__lte")
    mis_registros = filters.BooleanFilter(method="filtrar_mis_registros")
    no_propias = filters.BooleanFilter(method="filtrar_no_propias")

    class Meta:
        model = Actividad
        fields = ["tipo_registro", "estado", "estado_verificacion", "pondera", "item", "area"]

    def filtrar_no_propias(self, queryset, nombre, valor):
        if valor:
            return queryset.exclude(funcionario_id=self.request.user.funcionario_id)
        return queryset

    def filtrar_mis_registros(self, queryset, nombre, valor):
        if valor:
            return queryset.filter(funcionario_id=self.request.user.funcionario_id)
        return queryset


class ActividadViewSet(MantenedorViewSet):
    """Alta, consulta y edición (solo el autor, en pendiente o antecedentes). Sin DELETE (405).

    Las operaciones sobre un registro puntual (editar, verificar) devuelven 403 si es de otra
    delegación y 404 solo si no existe; la lectura (retrieve/list) sigue dando 404.
    """

    permission_classes = [PuedeRegistrarActividades]
    queryset = (
        Actividad.objects.select_related(
            "funcionario", "item", "vecino", "territorio", "area", "tipo_atencion", "sub_atencion"
        )
        .annotate(n_evidencias=Count("evidencias", distinct=True))
        .order_by("-fecha", "-id_actividad")
    )
    serializer_class = ActividadSerializer
    filterset_class = ActividadFiltro
    search_fields = ["codigo", "descripcion", "vecino__rut", "vecino__nombres", "vecino__apellidos"]
    ordering_fields = ["fecha", "fecha_registro", "codigo"]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        # super(MantenedorViewSet, self): se salta el alcance genérico y usa el de actividades.
        user = self.request.user
        queryset = filtrar_por_alcance(
            super(MantenedorViewSet, self).get_queryset(), user, "funcionario__delegacion_id"
        )
        if rol_de_usuario(user) == Rol.FUNCIONARIO:
            return queryset.filter(funcionario_id=user.funcionario_id)  # solo lo propio
        return queryset

    def handle_exception(self, exc):
        return super().handle_exception(actividad_conflicto(exc))

    def get_object(self):
        if self.action in ("retrieve", "historial"):
            return super().get_object()  # lectura: fuera de alcance = 404
        actividad = get_object_or_404(
            Actividad.objects.select_related("funcionario"), pk=self.kwargs["pk"]
        )
        if not verificacion.en_alcance(self.request.user, actividad):
            raise PermissionDenied("La actividad pertenece a otra delegación.")
        if self.action in ("update", "partial_update"):
            verificacion.validar_edicion(self.request.user, actividad)
            # Se vuelve a cargar con el queryset del serializer (anotaciones y relaciones).
            actividad = Actividad.objects.get(pk=actividad.pk)
        return actividad

    def perform_create(self, serializer):
        user = self.request.user
        with transaction.atomic():
            # Se bloquea la ficha del autor antes de contar: dos altas simultáneas no pueden
            # pasar ambas el tope de 7 por día.
            funcionario = Funcionario.objects.select_for_update().get(pk=user.funcionario_id)
            try:
                reglas.validar_fecha(serializer.validated_data["fecha"], funcionario)
            except DjangoValidationError as e:
                raise ValidationError(e.message_dict)
            instancia = serializer.save()
            auditoria.registrar(user, "crear", instancia, nuevo=auditoria.foto(instancia))

    def perform_update(self, serializer):
        user = self.request.user
        with transaction.atomic():
            # Se relee con bloqueo y se revalida: una aprobación concurrente gana la carrera.
            bloqueada = Actividad.objects.select_for_update().get(pk=serializer.instance.pk)
            verificacion.validar_edicion(user, bloqueada)
            serializer.instance.estado_verificacion = bloqueada.estado_verificacion
            anterior = auditoria.foto(serializer.instance)
            instancia = serializer.save()
            verificacion.reabrir_por_edicion(user, instancia)  # antecedentes -> pendiente
            auditoria.registrar(
                user, "editar", instancia, anterior=anterior, nuevo=auditoria.foto(instancia)
            )

    @action(detail=True, methods=["post"], permission_classes=[PuedeVerificar])
    def verificar(self, request, pk=None):
        """Aprobar, rechazar o pedir antecedentes: {"accion"|"estado": ..., "observacion": ...}."""
        actividad = self.get_object()
        datos = VerificarSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        actividad = verificacion.verificar(
            request.user,
            actividad,
            datos.validated_data["accion"],
            datos.validated_data["observacion"],
        )
        return Response(
            {
                "id_actividad": actividad.pk,
                "codigo": actividad.codigo,
                "estado_verificacion": actividad.estado_verificacion,
            }
        )

    @action(detail=True, methods=["get"])
    def historial(self, request, pk=None):
        actividad = self.get_object()
        return Response(
            HistorialVerificacionSerializer(
                actividad.historial_verificacion.select_related("usuario"), many=True
            ).data
        )

    @action(detail=False, methods=["get"])
    def opciones(self, request):
        """Catálogos que el usuario puede usar al registrar (según su cargo y delegación)."""
        funcionario = request.user.funcionario
        delegacion_id = funcionario.delegacion_id
        return Response(
            {
                "items": list(
                    Item.objects.filter(cargo_id=funcionario.cargo_id, activo=True)
                    .order_by("nombre")
                    .values("id_item", "nombre")
                ),
                "areas": [
                    {"id_area": a.id_area, "nombre": a.nombre, "texto": a.get_nombre_display()}
                    for a in Area.objects.filter(delegacion_id=delegacion_id, estado="activa")
                ],
                "territorios": list(
                    Territorio.objects.filter(delegacion_id=delegacion_id, activo=True)
                    .order_by("nombre")
                    .values("id_territorio", "nombre")
                ),
                "tipos_atencion": list(
                    TipoAtencion.objects.filter(activo=True).values(
                        "id_tipo_atencion", "area", "nombre"
                    )
                ),
                "sub_atenciones": list(
                    SubAtencion.objects.filter(activo=True, tipo_atencion__activo=True).values(
                        "id_sub_atencion", "tipo_atencion", "nombre"
                    )
                ),
            }
        )


class BuscarVecinoView(APIView):
    """GET /api/vecinos/buscar/?rut= para autocompletar el formulario de actividades."""

    permission_classes = [PuedeBuscarVecino]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "buscar_vecino"

    def get(self, request):
        rut = normalizar_rut(request.query_params.get("rut", ""))
        if not rut_es_valido(rut):
            return Response(
                {"error": "RUT inválido.", "campo": "rut"}, status=status.HTTP_400_BAD_REQUEST
            )
        vecino = Vecino.objects.filter(rut=rut, estado=Vecino.ACTIVO).first()
        # Solo se muestran vecinos ya atendidos en la delegación del usuario (los "libres", sin
        # actividades, no: serían datos personales de cualquiera). El acceso global ve todo.
        # TODO(Pamela): reemplazar por vecino.delegacion cuando exista ese campo.
        if vecino and not verificacion.acceso_global(request.user):
            atendido = vecino.actividades.filter(
                funcionario__delegacion_id=request.user.delegacion_id
            )
            if not atendido.exists():
                vecino = None  # tampoco se revela que existe en otra delegación
        if vecino is None:
            return Response(
                {"error": "No hay un vecino con ese RUT en tu delegación.", "campo": "rut"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "id_vecino": vecino.id_vecino,
                "rut": vecino.rut,
                "nombres": vecino.nombres,
                "apellidos": vecino.apellidos,
                "telefono": vecino.telefono,
                "direccion": vecino.direccion,
            }
        )


class EvidenciaViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Evidencias de una actividad. El archivo no tiene URL pública: se baja por /archivo/."""

    permission_classes = [PuedeConsultarEvidencias]
    queryset = Evidencia.objects.select_related("actividad__funcionario")
    serializer_class = EvidenciaSerializer
    parser_classes = [MultiPartParser, FormParser]
    filterset_fields = ["actividad"]

    def get_queryset(self):
        user = self.request.user
        queryset = filtrar_por_alcance(
            super().get_queryset(), user, "actividad__funcionario__delegacion_id"
        )
        if rol_de_usuario(user) == Rol.FUNCIONARIO:
            return queryset.filter(actividad__funcionario_id=user.funcionario_id)
        return queryset

    def handle_exception(self, exc):
        return super().handle_exception(actividad_conflicto(exc))

    def get_object(self):
        if self.action == "retrieve":
            return super().get_object()
        evidencia = get_object_or_404(self.queryset, pk=self.kwargs["pk"])
        actividad = evidencia.actividad
        permitido = (
            verificacion.puede_gestionar_evidencias
            if self.action == "destroy"
            else verificacion.puede_ver
        )
        if not permitido(self.request.user, actividad):
            raise PermissionDenied("La evidencia pertenece a otra delegación.")
        return evidencia

    def perform_create(self, serializer):
        user = self.request.user
        actividad = serializer.validated_data["actividad"]
        if not verificacion.puede_gestionar_evidencias(user, actividad):
            raise PermissionDenied("Solo el autor o quien verifica puede subir evidencias.")
        with transaction.atomic():
            # Se relee con bloqueo: una aprobación concurrente no deja pasar la subida.
            bloqueada = Actividad.objects.select_for_update().get(pk=actividad.pk)
            verificacion.validar_modificable(bloqueada)
            maximo = settings.EVIDENCIAS_MAX_POR_ACTIVIDAD
            if bloqueada.evidencias.count() >= maximo:
                raise ValidationError(
                    {"actividad": f"La actividad ya tiene el máximo de {maximo} evidencias."}
                )
            evidencia = serializer.save(actividad=bloqueada)
            nuevo = auditoria.foto(evidencia)
            nuevo.pop("archivo", None)
            auditoria.registrar(user, "crear", evidencia, nuevo=nuevo)

    def destroy(self, request, *args, **kwargs):
        evidencia = self.get_object()
        with transaction.atomic():
            bloqueada = Actividad.objects.select_for_update().get(pk=evidencia.actividad_id)
            verificacion.validar_modificable(bloqueada)
            anterior = auditoria.foto(evidencia)
            anterior.pop("archivo", None)
            auditoria.registrar(request.user, "eliminar", evidencia, anterior=anterior)
            evidencia.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def archivo(self, request, pk=None):
        """Descarga con control de delegación. Con EVIDENCIAS_X_ACCEL_PREFIX (nginx interno)
        el envío del archivo se delega en nginx con X-Accel-Redirect."""
        evidencia = self.get_object()
        # Nombre de descarga fijado por el servidor (código verificador + extensión real):
        # el nombre original que escribió el usuario nunca llega a un encabezado.
        codigo = evidencia.codigo_verificador
        nombre = codigo + os.path.splitext(evidencia.archivo.name)[1].lower()
        prefijo = settings.EVIDENCIAS_X_ACCEL_PREFIX
        if prefijo:
            respuesta = HttpResponse(content_type=evidencia.tipo_contenido)
            destino = prefijo.rstrip("/") + "/" + evidencia.archivo.name
            respuesta["X-Accel-Redirect"] = destino
            respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
        else:
            respuesta = FileResponse(
                evidencia.archivo.open("rb"),
                as_attachment=True,
                filename=nombre,
                content_type=evidencia.tipo_contenido,
            )
        respuesta["X-Content-Type-Options"] = "nosniff"
        return respuesta
