from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from core.models import Rol

from . import reglas
from .models import Actividad, SubAtencion, TipoAtencion


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
            "estado_verificacion",
            "pondera",
            "motivo_no_pondera",
        ]
        read_only_fields = [
            "codigo",
            "funcionario",
            "fecha_registro",
            "estado",
            "estado_verificacion",
            "pondera",
            "motivo_no_pondera",
        ]

    def get_vecino_nombre(self, obj):
        return f"{obj.vecino.nombres} {obj.vecino.apellidos}" if obj.vecino_id else ""

    def validate(self, attrs):
        funcionario = self.context["request"].user.funcionario  # el autor es quien está logueado
        fecha = attrs.get("fecha") or timezone.now()
        vecino = attrs.get("vecino")
        try:
            reglas.validar_actividad(
                funcionario=funcionario,
                item=attrs.get("item"),
                fecha=fecha,
                area=attrs.get("area"),
                territorio=attrs.get("territorio"),
                vecino=vecino,
                tipo_atencion=attrs.get("tipo_atencion"),
                sub_atencion=attrs.get("sub_atencion"),
            )
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.message_dict)
        solicitante = attrs.get("delegado_solicitante")
        if attrs.get("origen") == Actividad.ORIGEN_DELEGADO and solicitante is None:
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
            contacto=attrs.get("contacto", ""),
            telefono=attrs.get("telefono", ""),
            es_coordinacion_preparatoria=attrs.get("es_coordinacion_preparatoria", False),
        )
        return attrs
