from decimal import Decimal
from django.db.models.aggregates import Sum
from django.db import transaction
from organizacion.models import Delegacion
from personas.models import Funcionario
from rest_framework import serializers
from .models import Item, Periodo, MetaDelegacion, MetaIndividual, RecalibracionMeta


class PeriodoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Periodo
        fields = "__all__"

    def validate_dias_computables(self, valor):
        """Validación individual del campo dias_computables"""
        if valor is not None and valor <= 0:
            raise serializers.ValidationError(
                "Los días computables deben ser un valor positivo mayor a cero."
            )
        return valor

    def validate(self, datos):
        """Validaciones generales y de negocio para el período"""
        # Se obtienen los datos actuales o de la instancia existente (si es edición)
        fecha_inicio = datos.get("fecha_inicio", getattr(self.instance, "fecha_inicio", None))
        fecha_termino = datos.get("fecha_termino", getattr(self.instance, "fecha_termino", None))
        estado = datos.get("estado", getattr(self.instance, "estado", None))

        # 1. Regla de negocio: la fecha de término debe ser posterior a la de inicio
        if fecha_inicio and fecha_termino and fecha_termino <= fecha_inicio:
            raise serializers.ValidationError(
                {"fecha_termino": "La fecha de término debe ser posterior a la fecha de inicio."}
            )

        # 2. Regla de negocio: unicidad de período en estado 'vigente'
        if estado == "vigente":
            existe_vigente = Periodo.objects.filter(estado="vigente")
            if self.instance:
                existe_vigente = existe_vigente.exclude(pk=self.instance.pk)
            if existe_vigente.exists():
                raise serializers.ValidationError(
                    {"estado": "Ya existe un período registrado con estado 'vigente'."}
                )

        return datos


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = "__all__"

    def validate_ponderador(self, valor):
        if valor <= 0 or valor > 100:
            raise serializers.ValidationError(
                "El ponderador debe ser mayor a 0 y menor o igual a 100."
            )
        return valor

    def validate(self, datos):
        requiere_verif = datos.get(
            "requiere_verificacion_previa",
            getattr(self.instance, "requiere_verificacion_previa", False),
        )
        radio = datos.get(
            "radio_tolerancia_metros",
            getattr(self.instance, "radio_tolerancia_metros", None),
        )

        # Regla 1 (HU29): Si requiere verificación previa, radio_tolerancia_metros es obligatorio y > 0
        if requiere_verif:
            if radio is None or radio <= 0:
                raise serializers.ValidationError(
                    {
                        "radio_tolerancia_metros": (
                            "Si requiere verificación previa, el radio de tolerancia "
                            "en metros es obligatorio y mayor a 0."
                        )
                    }
                )

        # Regla 2: La suma de ponderadores para un mismo cargo no puede exceder el 100%
        cargo = datos.get("cargo", getattr(self.instance, "cargo", None))
        ponderador = datos.get("ponderador", getattr(self.instance, "ponderador", Decimal("0.00")))
        activo = datos.get("activo", getattr(self.instance, "activo", True))

        if cargo and activo and ponderador:
            qs = Item.objects.filter(cargo=cargo, activo=True)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            suma_existente = sum(i.ponderador for i in qs)
            if (suma_existente + Decimal(str(ponderador))) > Decimal("100.00"):
                raise serializers.ValidationError(
                    {
                        "ponderador": (
                            f"La suma de ponderadores para este cargo superaría el 100% "
                            f"(acumulado actual: {suma_existente}%)."
                        )
                    }
                )

        return datos


def _asignado(meta_delegacion):
    suma = meta_delegacion.metas_individuales.aggregate(total=Sum("valor_objetivo"))["total"]
    return suma or Decimal("0")


class MetaDelegacionSerializer(serializers.ModelSerializer):
    suma_metas = serializers.SerializerMethodField()
    saldo_por_asignar = serializers.SerializerMethodField()

    class Meta:
        model = MetaDelegacion
        fields = [
            "id_meta_delegacion",
            "item",
            "delegacion",
            "periodo",
            "valor_objetivo_total",
            "suma_metas",
            "saldo_por_asignar",
        ]
        validators = []  # la unicidad se valida en validate() con mensaje en español

    def _suma(self, obj):
        suma = getattr(obj, "suma_anotada", None)
        return _asignado(obj) if suma is None else suma

    def get_suma_metas(self, obj):
        return f"{self._suma(obj):.2f}"

    def get_saldo_por_asignar(self, obj):
        return f"{obj.valor_objetivo_total - self._suma(obj):.2f}"

    def validate_valor_objetivo_total(self, valor):
        if valor <= 0:
            raise serializers.ValidationError("El valor objetivo total debe ser mayor a cero.")
        return valor

    def validate_item(self, item):
        if self.instance is None and not item.activo:
            raise serializers.ValidationError("El ítem seleccionado no está activo.")
        return item

    def validate_delegacion(self, delegacion):
        if self.instance is None and delegacion.estado != Delegacion.ACTIVA:
            raise serializers.ValidationError("La delegación seleccionada está inactiva.")
        return delegacion

    def validate(self, datos):
        if self.instance:
            for campo in ("item", "delegacion", "periodo"):
                if campo in datos and datos[campo] != getattr(self.instance, campo):
                    raise serializers.ValidationError(
                        {campo: "No se puede cambiar una vez creada la meta de la delegación."}
                    )
            nuevo = datos.get("valor_objetivo_total")
            if (
                nuevo is not None
                and nuevo != self.instance.valor_objetivo_total
                and self.instance.metas_individuales.exists()
            ):
                raise serializers.ValidationError(
                    {
                        "valor_objetivo_total": "Ya tiene metas individuales: "
                        "para ajustar el valor recalibra una meta individual."
                    }
                )
            return datos
        if MetaDelegacion.objects.filter(
            item=datos["item"], delegacion=datos["delegacion"], periodo=datos["periodo"]
        ).exists():
            raise serializers.ValidationError(
                {"item": "Ya existe una meta de esta delegación para este ítem y período."}
            )
        return datos


class MetaIndividualSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetaIndividual
        fields = ["id_meta", "meta_delegacion", "funcionario", "valor_objetivo", "unidad"]
        validators = []  # la unicidad se valida en validate() con mensaje en español

    def validate_valor_objetivo(self, valor):
        if valor <= 0:
            raise serializers.ValidationError("El valor objetivo debe ser mayor a cero.")
        return valor

    def validate(self, datos):
        if self.instance:
            # El valor solo cambia por recalibración; así el historial nunca se salta.
            for campo in ("meta_delegacion", "funcionario"):
                if campo in datos and datos[campo] != getattr(self.instance, campo):
                    raise serializers.ValidationError(
                        {campo: "No se puede cambiar una vez asignada la meta."}
                    )
            if (
                "valor_objetivo" in datos
                and datos["valor_objetivo"] != self.instance.valor_objetivo
            ):
                raise serializers.ValidationError(
                    {
                        "valor_objetivo": "El valor solo se cambia recalibrando la meta "
                        "(queda registrado el motivo)."
                    }
                )
            return datos

        meta_delegacion = datos["meta_delegacion"]
        funcionario = datos["funcionario"]
        valor = datos["valor_objetivo"]
        if funcionario.estado != Funcionario.ACTIVO:
            raise serializers.ValidationError({"funcionario": "El funcionario está inactivo."})
        if funcionario.delegacion_id != meta_delegacion.delegacion_id:
            raise serializers.ValidationError(
                {"funcionario": "El funcionario no pertenece a la delegación de esta meta."}
            )
        if meta_delegacion.metas_individuales.filter(funcionario=funcionario).exists():
            raise serializers.ValidationError(
                {"funcionario": "El funcionario ya tiene una meta asignada para este ítem."}
            )
        saldo = meta_delegacion.valor_objetivo_total - _asignado(meta_delegacion)
        if valor > saldo:
            raise serializers.ValidationError(
                {
                    "valor_objetivo": "La suma de las metas individuales no puede superar el "
                    f"valor objetivo total de la delegación (saldo disponible: {saldo:.2f})."
                }
            )
        return datos


class RecalibracionMetaSerializer(serializers.ModelSerializer):
    usuario_email = serializers.CharField(source="usuario.email", read_only=True)

    class Meta:
        model = RecalibracionMeta
        fields = [
            "id_recalibracion",
            "meta",
            "valor_objetivo_anterior",
            "valor_objetivo_nuevo",
            "motivo",
            "usuario",
            "usuario_email",
            "fecha",
        ]
        read_only_fields = ["meta", "valor_objetivo_anterior", "usuario", "fecha"]

    def validate_valor_objetivo_nuevo(self, valor):
        if valor <= 0:
            raise serializers.ValidationError("El nuevo valor objetivo debe ser mayor a cero.")
        meta = self.context.get("meta")
        if meta is not None and valor == meta.valor_objetivo:
            raise serializers.ValidationError("El nuevo valor es igual al valor actual de la meta.")
        return valor

    def validate_motivo(self, valor):
        valor = valor.strip()
        if not valor:
            raise serializers.ValidationError("El motivo del ajuste es obligatorio.")
        return valor

    def create(self, datos):
        """Registra el ajuste y actualiza la meta y el total de su delegación (misma diferencia)."""
        with transaction.atomic():
            md_id = self.context["meta"].meta_delegacion_id
            meta_delegacion = MetaDelegacion.objects.select_for_update().get(pk=md_id)
            meta = MetaIndividual.objects.select_for_update().get(pk=self.context["meta"].pk)
            anterior, nuevo = meta.valor_objetivo, datos["valor_objetivo_nuevo"]
            recalibracion = RecalibracionMeta.objects.create(
                meta=meta,
                valor_objetivo_anterior=anterior,
                valor_objetivo_nuevo=nuevo,
                motivo=datos["motivo"],
                usuario=self.context["request"].user,
            )
            meta.valor_objetivo = nuevo
            meta.save(update_fields=["valor_objetivo"])
            meta_delegacion.valor_objetivo_total += nuevo - anterior
            meta_delegacion.save(update_fields=["valor_objetivo_total"])
        return recalibracion
