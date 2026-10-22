from django.db import transaction
from rest_framework import serializers

from core import auditoria

from .models import Area, Cargo, Delegacion


def _contador(obj, anotado, calcular):
    """Usa el valor calculado en la consulta del listado; si no viene, lo calcula."""
    valor = getattr(obj, anotado, None)
    return valor if valor is not None else calcular()


class DelegacionSerializer(serializers.ModelSerializer):
    total_areas = serializers.SerializerMethodField()
    areas_activas = serializers.SerializerMethodField()
    cargos_vigentes = serializers.SerializerMethodField()

    class Meta:
        model = Delegacion
        fields = [
            "id_delegacion",
            "codigo",
            "nombre",
            "ambito",
            "direccion",
            "comuna",
            "estado",
            "total_areas",
            "areas_activas",
            "cargos_vigentes",
        ]
        # La unicidad se valida a mano (sin distinguir mayúsculas) con mensajes en español.
        extra_kwargs = {"codigo": {"validators": []}, "nombre": {"validators": []}}

    def get_total_areas(self, obj):
        return _contador(obj, "n_areas", lambda: obj.areas.count())

    def get_areas_activas(self, obj):
        return _contador(
            obj, "n_areas_activas", lambda: obj.areas.filter(estado=Area.ACTIVA).count()
        )

    def get_cargos_vigentes(self, obj):
        return _contador(
            obj,
            "n_cargos_vigentes",
            lambda: Cargo.objects.filter(area__delegacion=obj, vigente=True).count(),
        )

    def _unico(self, campo, valor, etiqueta):
        existe = Delegacion.objects.filter(**{f"{campo}__iexact": valor})
        if self.instance:
            existe = existe.exclude(pk=self.instance.pk)
        if existe.exists():
            raise serializers.ValidationError(f"Ya existe una delegación con este {etiqueta}.")
        return valor

    def validate_codigo(self, valor):
        valor = valor.strip().upper()
        if not valor:
            raise serializers.ValidationError("El código es obligatorio.")
        return self._unico("codigo", valor, "código")

    def validate_nombre(self, valor):
        valor = valor.strip()
        if not valor:
            raise serializers.ValidationError("El nombre es obligatorio.")
        return self._unico("nombre", valor, "nombre")


class AreaSerializer(serializers.ModelSerializer):
    delegacion_nombre = serializers.CharField(source="delegacion.nombre", read_only=True)
    delegacion_codigo = serializers.CharField(source="delegacion.codigo", read_only=True)
    nombre_texto = serializers.CharField(source="get_nombre_display", read_only=True)
    cargos_vigentes = serializers.SerializerMethodField()

    class Meta:
        model = Area
        fields = [
            "id_area",
            "delegacion",
            "delegacion_codigo",
            "delegacion_nombre",
            "nombre",
            "nombre_texto",
            "prioridad",
            "estado",
            "cargos_vigentes",
        ]
        # Las validaciones de unicidad se hacen a mano para devolver mensajes claros.
        validators = []

    def get_cargos_vigentes(self, obj):
        return _contador(obj, "n_cargos_vigentes", lambda: obj.cargos.filter(vigente=True).count())

    def validate_prioridad(self, valor):
        if not 1 <= valor <= 4:
            raise serializers.ValidationError("La prioridad debe estar entre 1 y 4.")
        return valor

    def validate(self, datos):
        delegacion = datos.get("delegacion", getattr(self.instance, "delegacion", None))
        nombre = datos.get("nombre", getattr(self.instance, "nombre", None))
        prioridad = datos.get("prioridad", getattr(self.instance, "prioridad", None))
        estado = datos.get("estado", getattr(self.instance, "estado", Area.ACTIVA))

        # Relación inactiva (CAT-05): no se crea ni se mueve un área a una delegación inactiva,
        # ni se reactiva un área cuya delegación sigue inactiva.
        if delegacion is not None and delegacion.estado != Delegacion.ACTIVA:
            cambia = self.instance is None or delegacion.pk != self.instance.delegacion_id
            if cambia:
                raise serializers.ValidationError(
                    {
                        "delegacion": "La delegación está inactiva: no se pueden crear áreas "
                        "en ella. Reactive la delegación primero."
                    }
                )
            if estado == Area.ACTIVA:
                raise serializers.ValidationError(
                    {
                        "estado": "No se puede activar el área mientras su delegación esté "
                        "inactiva. Reactive la delegación primero."
                    }
                )

        otras = Area.objects.filter(delegacion=delegacion)
        if self.instance:
            otras = otras.exclude(pk=self.instance.pk)
        if otras.filter(nombre=nombre).exists():
            raise serializers.ValidationError({"nombre": "La delegación ya tiene esa área."})
        if otras.filter(prioridad=prioridad).exists():
            # Al editar un área de la misma delegación la prioridad se INTERCAMBIA con la del
            # área que la tenía (update). Al crear, o al mover un área de delegación, se rechaza.
            misma_delegacion = self.instance and delegacion.pk == self.instance.delegacion_id
            if not misma_delegacion:
                raise serializers.ValidationError(
                    {"prioridad": "Esa prioridad ya está usada en la delegación."}
                )
        return datos

    def update(self, instancia, datos):
        """Si la nueva prioridad la tenía otra área de la delegación, las dos se intercambian.

        Las 4 áreas nacen con las 4 prioridades, así que sin intercambio no se podría reordenar
        nunca. Se usa 0 como valor temporal por la restricción única (delegación, prioridad).
        """
        self.intercambiada = None
        nueva = datos.get("prioridad", instancia.prioridad)
        vieja = instancia.prioridad
        with transaction.atomic():
            otra = None
            if nueva != vieja:
                otra = (
                    Area.objects.filter(delegacion=instancia.delegacion, prioridad=nueva)
                    .exclude(pk=instancia.pk)
                    .first()
                )
            if otra is not None:
                anterior = auditoria.foto(otra)
                otra.prioridad = 0
                otra.save(update_fields=["prioridad"])
            instancia = super().update(instancia, datos)
            if otra is not None:
                otra.prioridad = vieja
                otra.save(update_fields=["prioridad"])
                self.intercambiada = (otra, anterior)
        return instancia


class CargoSerializer(serializers.ModelSerializer):
    area_texto = serializers.SerializerMethodField()
    transversal = serializers.SerializerMethodField()

    class Meta:
        model = Cargo
        fields = [
            "id_cargo",
            "area",
            "area_texto",
            "transversal",
            "nombre",
            "descripcion",
            "vigente",
        ]
        validators = []

    def get_area_texto(self, obj):
        return str(obj.area) if obj.area_id else "Transversal"

    def get_transversal(self, obj):
        return obj.area_id is None

    def validate_nombre(self, valor):
        valor = valor.strip()
        if not valor:
            raise serializers.ValidationError("El nombre es obligatorio.")
        return valor

    def validate(self, datos):
        area = datos.get("area", getattr(self.instance, "area", None))
        nombre = datos.get("nombre", getattr(self.instance, "nombre", None))
        vigente = datos.get("vigente", self.instance.vigente if self.instance else True)

        # Relación inactiva (CAT-05): un cargo no se crea ni se mueve a un área inactiva
        # (o de una delegación inactiva), ni se marca vigente mientras el área siga inactiva.
        if area is not None and (
            area.estado != Area.ACTIVA or area.delegacion.estado != Delegacion.ACTIVA
        ):
            cambia = self.instance is None or area.pk != self.instance.area_id
            if cambia:
                raise serializers.ValidationError(
                    {
                        "area": "El área está inactiva (o su delegación): no se pueden "
                        "crear cargos en ella. Reactívela primero."
                    }
                )
            if vigente:
                raise serializers.ValidationError(
                    {
                        "vigente": "No se puede marcar como vigente un cargo cuya área está "
                        "inactiva. Reactive el área primero."
                    }
                )

        existe = Cargo.objects.filter(area=area, nombre__iexact=nombre)
        if self.instance:
            existe = existe.exclude(pk=self.instance.pk)
        if existe.exists():
            raise serializers.ValidationError(
                {"nombre": "Ya existe un cargo con este nombre en el área."}
            )
        return datos
