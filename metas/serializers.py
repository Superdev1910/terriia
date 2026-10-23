from decimal import Decimal
from rest_framework import serializers
from .models import Item, Periodo


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
