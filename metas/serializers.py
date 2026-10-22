from rest_framework import serializers
from .models import Periodo


class PeriodoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Periodo
        fields = "__all__"

    def validate_dias_computables(self, valor):
        """Validación individual del campo dias_computables"""
        if valor <= 0:
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
