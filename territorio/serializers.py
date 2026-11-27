from django.utils import timezone
from rest_framework import serializers

from organizacion.models import Delegacion

from .models import JuntaVecinos, MiembroJunta, Territorio, Vecino


class VecinoSerializer(serializers.ModelSerializer):
    delegacion_nombre = serializers.CharField(source="delegacion.nombre", read_only=True)
    juntas = serializers.SerializerMethodField()

    def get_juntas(self, obj):
        return ", ".join(
            m.junta.nombre for m in obj.membresias.all() if m.estado == MiembroJunta.ACTIVO
        )

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
            "delegacion",
            "delegacion_nombre",
            "juntas",
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
    delegacion_nombre = serializers.CharField(source="territorio.delegacion.nombre", read_only=True)
    activa = serializers.BooleanField(default=True, required=False)
    presidente_vecino = serializers.SerializerMethodField()
    total_miembros = serializers.SerializerMethodField()

    def _activos(self, obj):
        # miembros_activos lo deja el Prefetch de la vista; si falta, se consulta.
        if hasattr(obj, "miembros_activos"):
            return obj.miembros_activos
        return list(obj.miembros.filter(estado=MiembroJunta.ACTIVO).select_related("vecino"))

    def get_presidente_vecino(self, obj):
        for miembro in self._activos(obj):
            if miembro.cargo == MiembroJunta.PRESIDENTE:
                return f"{miembro.vecino.nombres} {miembro.vecino.apellidos}"
        return None

    def get_total_miembros(self, obj):
        return len(self._activos(obj))

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
            "presidente_vecino",
            "total_miembros",
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


class MiembroJuntaSerializer(serializers.ModelSerializer):
    vecino_nombre = serializers.SerializerMethodField()
    vecino_rut = serializers.CharField(source="vecino.rut", read_only=True)
    junta_nombre = serializers.CharField(source="junta.nombre", read_only=True)
    cargo_display = serializers.CharField(source="get_cargo_display", read_only=True)
    estado = serializers.ChoiceField(
        choices=MiembroJunta.ESTADOS, default=MiembroJunta.ACTIVO, required=False
    )

    class Meta:
        model = MiembroJunta
        fields = [
            "id_miembro_junta",
            "junta",
            "junta_nombre",
            "vecino",
            "vecino_nombre",
            "vecino_rut",
            "cargo",
            "cargo_display",
            "fecha_ingreso",
            "fecha_salida",
            "estado",
        ]
        validators = []

    def get_vecino_nombre(self, obj):
        return f"{obj.vecino.nombres} {obj.vecino.apellidos}"

    def validate(self, attrs):
        actual = self.instance
        if actual is not None:
            for campo in ("junta", "vecino"):
                if campo in attrs and attrs[campo] != getattr(actual, campo):
                    raise serializers.ValidationError(
                        {campo: "No se puede cambiar; registre una nueva membresía."}
                    )

        def valor(campo, defecto=None):
            return attrs.get(campo, getattr(actual, campo, defecto))

        candidato = MiembroJunta(
            pk=actual.pk if actual else None,
            junta=valor("junta"),
            vecino=valor("vecino"),
            cargo=valor("cargo", MiembroJunta.SOCIO),
            fecha_ingreso=valor("fecha_ingreso") or timezone.localdate(),
            fecha_salida=valor("fecha_salida"),
            estado=valor("estado", MiembroJunta.ACTIVO),
        )
        # Reactivar: se limpia la fecha de salida salvo que se envíe una.
        if (
            actual
            and actual.estado == MiembroJunta.INACTIVO
            and candidato.estado == MiembroJunta.ACTIVO
            and "fecha_salida" not in attrs
        ):
            candidato.fecha_salida = None
            attrs["fecha_salida"] = None
        # Desactivar sin fecha de salida: se completa con hoy.
        if candidato.estado == MiembroJunta.INACTIVO and not candidato.fecha_salida:
            candidato.fecha_salida = max(timezone.localdate(), candidato.fecha_ingreso)
            attrs["fecha_salida"] = candidato.fecha_salida
        if candidato.estado == MiembroJunta.ACTIVO and not candidato.junta.activa:
            raise serializers.ValidationError(
                {"junta": "No se pueden agregar miembros a una junta inactiva."}
            )
        errores = candidato.errores_reglas()
        if errores:
            raise serializers.ValidationError(errores)
        return attrs
