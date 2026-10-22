from rest_framework import serializers

from organizacion.models import Delegacion

from .models import JuntaVecinos, Territorio, Vecino


class VecinoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vecino
        fields = [
            "id_vecino",
            "rut",
            "nombres",
            "apellidos",
            "telefono",
            "direccion",
            "estado",
        ]
        extra_kwargs = {"rut": {"validators": []}}

    def validate_rut(self, value):
        from core.validators import normalizar_rut, rut_es_valido

        rut = normalizar_rut(value)
        if not rut_es_valido(rut):
            raise serializers.ValidationError("RUT inválido.")
        qs = Vecino.objects.filter(rut=rut)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un vecino con este RUT.")
        return rut

    def validate(self, attrs):
        for field in ("nombres", "apellidos"):
            value = attrs.get(field, getattr(self.instance, field, ""))
            if not value or not value.strip():
                raise serializers.ValidationError({field: "Este campo es obligatorio."})
            attrs[field] = value.strip()
        return attrs


class TerritorioSerializer(serializers.ModelSerializer):
    delegacion_nombre = serializers.CharField(source="delegacion.nombre", read_only=True)
    delegacion_codigo = serializers.CharField(source="delegacion.codigo", read_only=True)
    activo = serializers.BooleanField(default=True, required=False)

    class Meta:
        model = Territorio
        fields = [
            "id_territorio",
            "delegacion",
            "delegacion_codigo",
            "delegacion_nombre",
            "nombre",
            "es_formal",
            "activo",
        ]
        validators = []

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("El nombre es obligatorio.")
        return value

    def validate(self, attrs):
        delegacion = attrs.get("delegacion", getattr(self.instance, "delegacion", None))
        if delegacion and delegacion.estado != Delegacion.ACTIVA:
            raise serializers.ValidationError(
                {"delegacion": "No se puede asociar un territorio a una delegación inactiva."}
            )
        nombre = attrs.get("nombre", getattr(self.instance, "nombre", ""))
        qs = Territorio.objects.filter(delegacion=delegacion, nombre__iexact=nombre)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                {"nombre": "La delegación ya tiene un territorio con ese nombre."}
            )
        return attrs


class JuntaVecinosSerializer(serializers.ModelSerializer):
    territorio_nombre = serializers.CharField(source="territorio.nombre", read_only=True)
    delegacion_nombre = serializers.CharField(
        source="territorio.delegacion.nombre", read_only=True
    )
    activa = serializers.BooleanField(default=True, required=False)

    class Meta:
        model = JuntaVecinos
        fields = [
            "id_junta_vecinos",
            "territorio",
            "territorio_nombre",
            "delegacion_nombre",
            "numero_registro",
            "nombre",
            "direccion",
            "presidente",
            "telefono",
            "email",
            "activa",
        ]
        validators = []

    def validate_numero_registro(self, value):
        value = value.strip() if value else None
        if not value:
            return None
        qs = JuntaVecinos.objects.filter(numero_registro__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe una junta con ese número de registro.")
        return value

    def validate(self, attrs):
        territorio = attrs.get("territorio", getattr(self.instance, "territorio", None))
        if territorio and not territorio.activo:
            raise serializers.ValidationError(
                {"territorio": "No se puede asociar una junta a un territorio inactivo."}
            )
        nombre = attrs.get("nombre", getattr(self.instance, "nombre", ""))
        if not nombre or not nombre.strip():
            raise serializers.ValidationError({"nombre": "El nombre es obligatorio."})
        attrs["nombre"] = nombre.strip()
        return attrs
