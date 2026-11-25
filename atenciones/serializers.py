import os

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from core.models import Rol

from . import evidencias, reglas, verificacion
from .models import (
    Actividad,
    Evidencia,
    HistorialVerificacion,
    SubAtencion,
    TipoAtencion,
)


def limpiar_nombre(value):
    value = value.strip()
    if not value:
        raise serializers.ValidationError("El nombre es obligatorio.")
    return value


def nombre_repetido(qs, nombre, instancia):
    """True si qs ya tiene ese nombre sin distinguir mayúsculas.

    Se compara en Python porque en SQLite nombre__iexact solo ignora mayúsculas en letras sin
    tilde («GESTIÓN» pasaría como distinto de «Gestión»). Los catálogos son cortos.
    """
    if instancia:
        qs = qs.exclude(pk=instancia.pk)
    buscado = nombre.casefold()
    return any(n.casefold() == buscado for n in qs.values_list("nombre", flat=True))


class TipoAtencionSerializer(serializers.ModelSerializer):
    area_nombre = serializers.CharField(source="get_area_display", read_only=True)
    activo = serializers.BooleanField(default=True, required=False)

    class Meta:
        model = TipoAtencion
        fields = ["id_tipo_atencion", "area", "area_nombre", "nombre", "activo"]
        validators = []  # el duplicado se revisa en validate() sin distinguir mayúsculas

    def validate_nombre(self, value):
        return limpiar_nombre(value)

    def validate(self, attrs):
        area = attrs.get("area", getattr(self.instance, "area", None))
        nombre = attrs.get("nombre", getattr(self.instance, "nombre", ""))
        if nombre_repetido(TipoAtencion.objects.filter(area=area), nombre, self.instance):
            raise serializers.ValidationError(
                {"nombre": "El área ya tiene un tipo de atención con ese nombre."}
            )
        return attrs


class SubAtencionSerializer(serializers.ModelSerializer):
    tipo_atencion_nombre = serializers.CharField(source="tipo_atencion.nombre", read_only=True)
    area = serializers.CharField(source="tipo_atencion.area", read_only=True)
    area_nombre = serializers.CharField(source="tipo_atencion.get_area_display", read_only=True)
    activo = serializers.BooleanField(default=True, required=False)

    class Meta:
        model = SubAtencion
        fields = [
            "id_sub_atencion",
            "tipo_atencion",
            "tipo_atencion_nombre",
            "area",
            "area_nombre",
            "nombre",
            "activo",
        ]
        validators = []  # el duplicado se revisa en validate() sin distinguir mayúsculas

    def validate_nombre(self, value):
        return limpiar_nombre(value)

    def validate(self, attrs):
        tipo = attrs.get("tipo_atencion", getattr(self.instance, "tipo_atencion", None))
        # Solo se revisa al asignar un tipo: una sub atención ya creada bajo un tipo que
        # después se desactivó se puede seguir editando o desactivando.
        cambia_tipo = self.instance is None or self.instance.tipo_atencion_id != tipo.pk
        if cambia_tipo and not tipo.activo:
            raise serializers.ValidationError(
                {"tipo_atencion": "No se puede asociar una sub atención a un tipo inactivo."}
            )
        nombre = attrs.get("nombre", getattr(self.instance, "nombre", ""))
        if nombre_repetido(SubAtencion.objects.filter(tipo_atencion=tipo), nombre, self.instance):
            raise serializers.ValidationError(
                {"nombre": "El tipo de atención ya tiene una sub atención con ese nombre."}
            )
        return attrs


class ActividadSerializer(serializers.ModelSerializer):
    """Ingreso de actividades y gestiones sociales.

    El autor, su delegación, el código, la ponderación y los estados los fija el servidor:
    el cliente no puede enviarlos.
    """

    funcionario_nombre = serializers.CharField(source="funcionario.nombre", read_only=True)
    item_nombre = serializers.CharField(source="item.nombre", read_only=True)
    vecino_nombre = serializers.SerializerMethodField()
    vecino_rut = serializers.CharField(source="vecino.rut", read_only=True, default=None)
    territorio_nombre = serializers.CharField(
        source="territorio.nombre", read_only=True, default=None
    )
    area_nombre = serializers.CharField(
        source="area.get_nombre_display", read_only=True, default=None
    )
    tipo_atencion_nombre = serializers.CharField(
        source="tipo_atencion.nombre", read_only=True, default=None
    )
    sub_atencion_nombre = serializers.CharField(
        source="sub_atencion.nombre", read_only=True, default=None
    )
    # TODO(Brian): convertir en FK a Hito cuando exista el modelo.
    id_hito = serializers.IntegerField(source="hito_id", required=False, allow_null=True)
    fecha = serializers.DateTimeField(required=False)
    n_evidencias = serializers.IntegerField(read_only=True, default=0)
    n_comentarios = serializers.IntegerField(read_only=True, default=0)
    puede_editar = serializers.SerializerMethodField()
    # Seguimiento (Épica 2): los datos los cambian las acciones de seguimiento, no el alta.
    responsable_nombre = serializers.CharField(
        source="responsable.nombre", read_only=True, default=None
    )
    delegacion_codigo = serializers.CharField(
        source="funcionario.delegacion.codigo", read_only=True, default=None
    )
    vencida = serializers.BooleanField(source="esta_vencida", read_only=True)  # HU07
    dias_atraso = serializers.IntegerField(read_only=True)
    ultima_observacion = serializers.SerializerMethodField()

    class Meta:
        model = Actividad
        fields = [
            "id_actividad",
            "codigo",
            "tipo_registro",
            "funcionario",
            "funcionario_nombre",
            "item",
            "item_nombre",
            "vecino",
            "vecino_nombre",
            "vecino_rut",
            "territorio",
            "territorio_nombre",
            "area",
            "area_nombre",
            "tipo_atencion",
            "tipo_atencion_nombre",
            "sub_atencion",
            "sub_atencion_nombre",
            "fecha",
            "fecha_registro",
            "descripcion",
            "accion",
            "contacto",
            "telefono",
            "ingreso_a_tubo",
            "es_coordinacion_preparatoria",
            "origen",
            "delegado_solicitante",
            "id_hito",
            "prioridad",
            "estado",
            "fecha_estado",
            "responsable",
            "responsable_nombre",
            "fecha_compromiso",
            "motivo_atraso",
            "vencida",
            "dias_atraso",
            "delegacion_codigo",
            "estado_verificacion",
            "pondera",
            "motivo_no_pondera",
            "n_evidencias",
            "n_comentarios",
            "puede_editar",
            "ultima_observacion",
        ]
        read_only_fields = [
            "codigo",
            "funcionario",
            "fecha_registro",
            "estado",
            "fecha_estado",
            "responsable",
            "fecha_compromiso",
            "motivo_atraso",
            "estado_verificacion",
            "pondera",
            "motivo_no_pondera",
        ]

    def get_ultima_observacion(self, obj):
        """Lo que escribió quien verificó al pedir antecedentes o rechazar (si corresponde)."""
        if obj.estado_verificacion not in verificacion.EXIGEN_OBSERVACION:
            return ""
        ultimo = obj.historial_verificacion.filter(estado_nuevo=obj.estado_verificacion).last()
        return ultimo.observacion if ultimo else ""

    def get_puede_editar(self, obj):
        """Solo el autor y solo mientras esté pendiente o con antecedentes pedidos."""
        user = self.context["request"].user
        return (
            obj.funcionario_id == user.funcionario_id
            and obj.estado_verificacion in verificacion.ESTADOS_EDITABLES
        )

    def get_vecino_nombre(self, obj):
        return f"{obj.vecino.nombres} {obj.vecino.apellidos}" if obj.vecino_id else ""

    def validate(self, attrs):
        instancia = self.instance
        # El autor es quien está logueado; al editar sigue siendo el autor original.
        funcionario = (
            instancia.funcionario if instancia else self.context["request"].user.funcionario
        )

        def valor(campo, defecto=None):
            if campo in attrs:
                return attrs[campo]
            return getattr(instancia, campo, defecto) if instancia else defecto

        fecha = valor("fecha") or timezone.now()
        vecino = valor("vecino")
        try:
            reglas.validar_actividad(
                funcionario=funcionario,
                item=valor("item"),
                fecha=fecha,
                area=valor("area"),
                territorio=valor("territorio"),
                vecino=vecino,
                tipo_atencion=valor("tipo_atencion"),
                sub_atencion=valor("sub_atencion"),
                excluir_pk=instancia.pk if instancia else None,
                validar_fecha_registro=instancia is None or "fecha" in attrs,
            )
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)
        solicitante = valor("delegado_solicitante")
        if valor("origen") == Actividad.ORIGEN_DELEGADO and solicitante is None:
            raise serializers.ValidationError(
                {"delegado_solicitante": "Indique el delegado que solicita la actividad."}
            )
        if solicitante is not None and solicitante.rol.nombre != Rol.DELEGADO_TERRITORIAL:
            raise serializers.ValidationError(
                {"delegado_solicitante": "El solicitante debe ser un delegado territorial."}
            )
        attrs["fecha"] = fecha
        attrs["funcionario"] = funcionario
        attrs["pondera"], attrs["motivo_no_pondera"] = reglas.calcular_ponderacion(
            vecino=vecino,
            contacto=valor("contacto", ""),
            telefono=valor("telefono", ""),
            es_coordinacion_preparatoria=valor("es_coordinacion_preparatoria", False),
        )
        return attrs


class HistorialVerificacionSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = HistorialVerificacion
        fields = [
            "id_historial",
            "usuario",
            "usuario_nombre",
            "estado_anterior",
            "estado_nuevo",
            "observacion",
            "fecha",
        ]

    def get_usuario_nombre(self, obj):
        return obj.usuario.get_full_name() or obj.usuario.email


class EvidenciaSerializer(serializers.ModelSerializer):
    """No expone la ruta del archivo: se descarga por /api/evidencias/<id>/archivo/."""

    archivo = serializers.FileField(write_only=True)
    descarga = serializers.SerializerMethodField()

    class Meta:
        model = Evidencia
        fields = [
            "id_evidencia",
            "actividad",
            "archivo",
            "codigo_verificador",
            "nombre_original",
            "tipo_contenido",
            "tamano",
            "autor",
            "fecha",
            "tiene_imagen",
            "estado_revision",
            "descarga",
        ]
        read_only_fields = [
            "codigo_verificador",
            "nombre_original",
            "tipo_contenido",
            "tamano",
            "autor",
            "fecha",
            "tiene_imagen",
            "estado_revision",
        ]

    def get_descarga(self, obj):
        return f"/api/evidencias/{obj.pk}/archivo/"

    def validate_archivo(self, archivo):
        try:
            tipo, extension = evidencias.validar_archivo(archivo)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages[0])
        self._tipo = tipo
        self._nombre_original = os.path.basename(archivo.name)[:150]
        archivo.name = f"evidencia{extension}"  # la ruta final usa uuid; la extensión es la real
        return archivo

    def create(self, validated_data):
        archivo = validated_data["archivo"]
        return Evidencia.objects.create(
            actividad=validated_data["actividad"],
            archivo=archivo,
            nombre_original=self._nombre_original,
            tipo_contenido=self._tipo,
            tamano=archivo.size,
            tiene_imagen=self._tipo.startswith("image/"),
            autor=self.context["request"].user,
        )


class VerificarSerializer(serializers.Serializer):
    """Entrada de POST /api/actividades/<id>/verificar/: acción (o estado) y observación."""

    accion = serializers.CharField(required=False)
    estado = serializers.CharField(required=False)
    observacion = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        valor = (attrs.get("accion") or attrs.get("estado") or "").strip().lower()
        if valor not in verificacion.ACCIONES:
            raise serializers.ValidationError({"accion": "Use aprobar, rechazar o antecedentes."})
        # CharField convierte números a texto; aquí se exige texto de verdad.
        if not isinstance(self.initial_data.get("observacion", ""), str):
            raise serializers.ValidationError({"observacion": "La observación debe ser texto."})
        return {"accion": valor, "observacion": attrs.get("observacion", "").strip()}
