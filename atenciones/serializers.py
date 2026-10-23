from rest_framework import serializers

from .models import SubAtencion, TipoAtencion


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
