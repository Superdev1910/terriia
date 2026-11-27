import os

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters import rest_framework as filters
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
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

from . import reglas, seguimiento, terreno, verificacion
from .models import (
    Actividad,
    ActividadHistorial,
    Comentario,
    Evidencia,
    SubAtencion,
    TipoAtencion,
    VisitaTerreno,
)
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


class PuedeSeguimiento(BasePermission):
    """Seguimiento (Épica 2): leer lo pueden todos los roles con alcance; operar, solo los roles
    de seguimiento (la regla fina por actividad está en atenciones/seguimiento.py)."""

    message = "No tienes permiso para dar seguimiento a esta actividad."

    def has_permission(self, request, view):
        user = request.user
        if request.method in SAFE_METHODS:
            return rol_de_usuario(user) in ROLES_QUE_CONSULTAN and verificacion.tiene_alcance(user)
        return seguimiento.PuedeHacerSeguimiento().has_permission(request, view)


class PuedeVisitarTerreno(BasePermission):
    """Leer: cualquier rol con alcance. Registrar: quien verifica o un Funcionario (el
    responsable asignado); la regla fina por actividad está en atenciones/terreno.py."""

    message = "Tu rol no puede registrar visitas a terreno."

    def has_permission(self, request, view):
        user = request.user
        rol = rol_de_usuario(user)  # None si es anónimo
        if rol is None or not verificacion.tiene_alcance(user):
            return False
        if request.method in SAFE_METHODS:
            return rol in ROLES_QUE_CONSULTAN
        return rol in verificacion.ROLES_VERIFICADORES + (Rol.FUNCIONARIO,)


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


def vencidas_q():
    """HU07: compromiso ya pasado y la actividad todavía no está Realizada."""
    return Q(fecha_compromiso__lt=timezone.localdate()) & ~Q(estado=Actividad.REALIZADO)


class ActividadFiltro(filters.FilterSet):
    desde = filters.DateFilter(field_name="fecha", lookup_expr="date__gte")
    hasta = filters.DateFilter(field_name="fecha", lookup_expr="date__lte")
    mis_registros = filters.BooleanFilter(method="filtrar_mis_registros")
    no_propias = filters.BooleanFilter(method="filtrar_no_propias")
    vencida = filters.BooleanFilter(method="filtrar_vencida")  # HU07

    class Meta:
        model = Actividad
        fields = [
            "tipo_registro",
            "estado",
            "estado_verificacion",
            "pondera",
            "item",
            "area",
            "prioridad",
            "responsable",
        ]

    def filtrar_vencida(self, queryset, nombre, valor):
        return queryset.filter(vencidas_q()) if valor else queryset.exclude(vencidas_q())

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
            "funcionario__delegacion",
            "item",
            "vecino",
            "territorio",
            "area",
            "tipo_atencion",
            "sub_atencion",
            "responsable",
        )
        .annotate(
            n_evidencias=Count("evidencias", distinct=True),
            n_comentarios=Count("comentarios", distinct=True),
        )
        .prefetch_related("visitas_terreno")
        .order_by("-fecha", "-id_actividad")
    )
    serializer_class = ActividadSerializer
    pagination_class = PaginacionMantenedor  # acepta page_size (hasta 100)
    filterset_class = ActividadFiltro
    search_fields = [
        "codigo",
        "descripcion",
        "accion",
        "vecino__rut",
        "vecino__nombres",
        "vecino__apellidos",
        "funcionario__nombre",
        "responsable__nombre",
        "item__nombre",
    ]
    ordering_fields = [
        "fecha",
        "fecha_registro",
        "codigo",
        "estado",
        "prioridad",
        "fecha_compromiso",
        "funcionario__nombre",
        "item__nombre",
    ]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        # super(MantenedorViewSet, self): se salta el alcance genérico y usa el de actividades.
        user = self.request.user
        # El Tubo es consultable por toda la delegación; escribir lo limitan get_object y seguimiento.
        return filtrar_por_alcance(
            super(MantenedorViewSet, self).get_queryset(), user, "funcionario__delegacion_id"
        )

    def handle_exception(self, exc):
        return super().handle_exception(actividad_conflicto(exc))

    def get_object(self):
        # visitas_terreno: otra delegación = 404; el 403 por rol o por no ser el responsable lo
        # da terreno.
        lectura = self.action in (
            "retrieve",
            "historial",
            "historial_seguimiento",
            "visitas_terreno",
        ) or (
            self.action in ("comentarios", "opciones_seguimiento") and self.request.method == "GET"
        )
        if lectura:
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

    # --- Seguimiento (Épica 2, HU02 a HU08) -------------------------------------------

    def _respuesta(self, actividad, codigo=status.HTTP_200_OK):
        """Devuelve la actividad ya actualizada (con sus anotaciones y campos calculados)."""
        actividad = self.get_queryset().get(pk=actividad.pk)
        return Response(self.get_serializer(actividad).data, status=codigo)

    def _auditar(self, evento, actividad, anterior):
        auditoria.registrar(
            self.request.user,
            evento,
            actividad,
            anterior=anterior,
            nuevo=auditoria.foto(actividad),
        )

    @action(detail=True, methods=["post"], permission_classes=[PuedeSeguimiento])
    def asignar(self, request, pk=None):
        """HU02: {"area", "prioridad", "responsable"?}. Solo Administrador o Delegado."""
        actividad = self.get_object()
        seguimiento.exigir_gestor(request.user, actividad)
        seguimiento.exigir_abierta(actividad)
        datos = seguimiento.AsignarSerializer(data=request.data, context={"actividad": actividad})
        datos.is_valid(raise_exception=True)
        with transaction.atomic():
            actividad = Actividad.objects.select_for_update().get(pk=actividad.pk)
            seguimiento.exigir_abierta(actividad)
            terreno.validar_asignacion(actividad)
            anterior = auditoria.foto(actividad)
            seguimiento.aplicar(
                actividad,
                area=datos.validated_data["area"],
                prioridad=datos.validated_data["prioridad"],
                responsable=datos.validated_data.get("responsable"),
            )
            self._auditar("asignar", actividad, anterior)
        return self._respuesta(actividad)

    @action(
        detail=True,
        methods=["post"],
        url_path="cambiar-estado",
        permission_classes=[PuedeSeguimiento],
    )
    def cambiar_estado(self, request, pk=None):
        """HU03 (+ HU05): {"estado", "motivo_atraso"?}. Si está vencida el motivo es obligatorio."""
        actividad = self.get_object()
        seguimiento.exigir_participante(request.user, actividad)
        seguimiento.exigir_abierta(actividad)
        ahora = timezone.now()
        with transaction.atomic():
            actividad = Actividad.objects.select_for_update().get(pk=actividad.pk)
            seguimiento.exigir_abierta(actividad)
            datos = seguimiento.CambiarEstadoSerializer(
                data=request.data, context={"actividad": actividad}
            )
            datos.is_valid(raise_exception=True)
            nuevo = datos.validated_data["estado"]
            terreno.validar_cambio_estado(actividad, nuevo)
            motivo = datos.validated_data.get("motivo_atraso")
            anterior = auditoria.foto(actividad)
            previo = actividad.estado
            campos = {"estado": nuevo, "fecha_estado": ahora, "usuario_cambio": request.user}
            if motivo:
                seguimiento.registrar_cambio(
                    request.user, actividad, "motivo_atraso", actividad.motivo_atraso, motivo, ahora
                )
                campos["motivo_atraso"] = motivo
            seguimiento.registrar_cambio(request.user, actividad, "estado", previo, nuevo, ahora)
            seguimiento.aplicar(actividad, **campos)
            self._auditar("cambiar_estado", actividad, anterior)
        return self._respuesta(actividad)

    @action(
        detail=True,
        methods=["post"],
        url_path="fecha-compromiso",
        permission_classes=[PuedeSeguimiento],
    )
    def fecha_compromiso(self, request, pk=None):
        """HU06 (+ HU05): {"fecha_compromiso", "motivo_atraso"?}; cada cambio queda en el historial."""
        actividad = self.get_object()
        seguimiento.exigir_participante(request.user, actividad)
        seguimiento.exigir_abierta(actividad)
        ahora = timezone.now()
        with transaction.atomic():
            actividad = Actividad.objects.select_for_update().get(pk=actividad.pk)
            seguimiento.exigir_abierta(actividad)
            datos = seguimiento.FechaCompromisoSerializer(
                data=request.data, context={"actividad": actividad}
            )
            datos.is_valid(raise_exception=True)
            nueva = datos.validated_data["fecha_compromiso"]
            motivo = datos.validated_data.get("motivo_atraso")
            anterior = auditoria.foto(actividad)
            campos = {"fecha_compromiso": nueva}
            if motivo:
                seguimiento.registrar_cambio(
                    request.user, actividad, "motivo_atraso", actividad.motivo_atraso, motivo, ahora
                )
                campos["motivo_atraso"] = motivo
            seguimiento.registrar_cambio(
                request.user,
                actividad,
                "fecha_compromiso",
                actividad.fecha_compromiso,
                nueva.isoformat(),
                ahora,
            )
            seguimiento.aplicar(actividad, **campos)
            self._auditar("fecha_compromiso", actividad, anterior)
        return self._respuesta(actividad)

    @action(
        detail=True,
        methods=["post"],
        url_path="motivo-atraso",
        permission_classes=[PuedeSeguimiento],
    )
    def motivo_atraso(self, request, pk=None):
        """HU05: registrar o corregir el motivo de una actividad vencida."""
        actividad = self.get_object()
        seguimiento.exigir_participante(request.user, actividad)
        verificacion.validar_modificable(actividad)
        datos = seguimiento.MotivoAtrasoSerializer(
            data=request.data, context={"actividad": actividad}
        )
        datos.is_valid(raise_exception=True)
        motivo = datos.validated_data["motivo_atraso"]
        with transaction.atomic():
            actividad = Actividad.objects.select_for_update().get(pk=actividad.pk)
            verificacion.validar_modificable(actividad)
            anterior = auditoria.foto(actividad)
            seguimiento.registrar_cambio(
                request.user, actividad, "motivo_atraso", actividad.motivo_atraso, motivo
            )
            seguimiento.aplicar(actividad, motivo_atraso=motivo)
            self._auditar("motivo_atraso", actividad, anterior)
        return self._respuesta(actividad)

    @action(
        detail=True,
        methods=["get"],
        url_path="historial-seguimiento",
        permission_classes=[PuedeSeguimiento],
        pagination_class=None,
    )
    def historial_seguimiento(self, request, pk=None):
        """HU03, HU05 y HU06: cambios de estado, de fecha de compromiso y de motivo."""
        actividad = self.get_object()
        filas = actividad.historial_seguimiento.select_related("usuario")
        return Response(seguimiento.HistorialSeguimientoSerializer(filas, many=True).data)

    @action(
        detail=True,
        methods=["get", "post"],
        permission_classes=[PuedeSeguimiento],
        pagination_class=None,
    )
    def comentarios(self, request, pk=None):
        """HU08: GET lista, POST agrega {"texto"}. Los comentarios no se editan ni se borran."""
        actividad = self.get_object()
        if request.method == "GET":
            filas = actividad.comentarios.select_related("usuario__rol")
            return Response(seguimiento.ComentarioSerializer(filas, many=True).data)
        seguimiento.exigir_participante(request.user, actividad)
        datos = seguimiento.ComentarioSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        with transaction.atomic():
            comentario = datos.save(actividad=actividad, usuario=request.user)
            auditoria.registrar(
                request.user, "comentar", comentario, nuevo=auditoria.foto(comentario)
            )
        return Response(
            seguimiento.ComentarioSerializer(comentario).data, status=status.HTTP_201_CREATED
        )

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="visitas-terreno",
        permission_classes=[PuedeVisitarTerreno],
        parser_classes=[MultiPartParser, FormParser, JSONParser],
        pagination_class=None,
    )
    def visitas_terreno(self, request, pk=None):
        """HU29: GET lista las visitas; POST registra una (multipart, archivo opcional)."""
        actividad = self.get_object()
        if request.method == "GET":
            filas = actividad.visitas_terreno.select_related("usuario")
            return Response(terreno.VisitaTerrenoSerializer(filas, many=True).data)
        if not terreno.puede_registrar(request.user, actividad):
            raise PermissionDenied(terreno.MSJ_SIN_PERMISO)
        datos = terreno.VisitaTerrenoSerializer(data=request.data)
        datos.is_valid(raise_exception=True)
        visita = terreno.registrar_visita(request.user, actividad, datos.validated_data)
        return Response(
            terreno.VisitaTerrenoSerializer(visita).data, status=status.HTTP_201_CREATED
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="opciones-seguimiento",
        permission_classes=[PuedeSeguimiento],
        pagination_class=None,
    )
    def opciones_seguimiento(self, request, pk=None):
        """Listas del formulario de asignación y transiciones de estado posibles."""
        actividad = self.get_object()
        delegacion_id = actividad.funcionario.delegacion_id
        datos = {
            "estados": [e for e, _ in Actividad.ESTADOS],
            "transiciones": {e: sorted(sig) for e, sig in seguimiento.TRANSICIONES.items()},
            "prioridades": [{"id": v, "nombre": t} for v, t in Actividad.PRIORIDADES],
            "areas": [],
            "responsables": [],
        }
        if seguimiento.es_gestor(request.user, actividad):
            datos["areas"] = [
                {"id": a.pk, "nombre": a.get_nombre_display()}
                for a in Area.objects.filter(delegacion_id=delegacion_id, estado="activa")
            ]
            datos["responsables"] = [
                {"id": f.pk, "nombre": f.nombre, "area": f.cargo.area_id}
                for f in Funcionario.objects.filter(
                    delegacion_id=delegacion_id, estado=Funcionario.ACTIVO
                ).select_related("cargo")
            ]
        return Response(datos)

    @action(detail=False, methods=["get"], pagination_class=None)
    def resumen(self, request):
        """Cifras del encabezado: total, por estado y cuántas están vencidas (HU07)."""
        base = self.get_queryset().order_by()
        return Response(
            {
                "total": base.count(),
                "por_estado": {e: base.filter(estado=e).count() for e, _ in Actividad.ESTADOS},
                "vencidas": base.filter(vencidas_q()).count(),
            }
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
            return queryset.filter(
                Q(actividad__funcionario_id=user.funcionario_id)
                | Q(actividad__responsable_id=user.funcionario_id)
            )
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


class VisitaTerrenoViewSet(viewsets.GenericViewSet):
    """Solo la descarga del archivo de una visita: mismo acceso que leer la actividad."""

    permission_classes = [PuedeVisitarTerreno]
    queryset = VisitaTerreno.objects.select_related("actividad__funcionario")

    def get_queryset(self):
        return filtrar_por_alcance(
            super().get_queryset(), self.request.user, "actividad__funcionario__delegacion_id"
        )

    @action(detail=True, methods=["get"])
    def archivo(self, request, pk=None):
        """Misma entrega que las evidencias (X-Accel-Redirect si hay EVIDENCIAS_X_ACCEL_PREFIX)."""
        visita = get_object_or_404(self.get_queryset(), pk=pk)
        if not visita.archivo:
            return Response({"detail": "La visita no tiene archivo."}, status=404)
        nombre = f"visita-{visita.pk}" + os.path.splitext(visita.archivo.name)[1].lower()
        prefijo = settings.EVIDENCIAS_X_ACCEL_PREFIX
        if prefijo:
            respuesta = HttpResponse(content_type=visita.tipo_contenido)
            respuesta["X-Accel-Redirect"] = prefijo.rstrip("/") + "/" + visita.archivo.name
            respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
        else:
            respuesta = FileResponse(
                visita.archivo.open("rb"),
                as_attachment=True,
                filename=nombre,
                content_type=visita.tipo_contenido,
            )
        respuesta["X-Content-Type-Options"] = "nosniff"
        return respuesta
