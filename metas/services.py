from datetime import date
from decimal import Decimal
from django.db.models import Sum
from atenciones.models import Actividad
from .cumplimiento import _limites_del_periodo
from .models import Item, MetaDelegacion, MetaIndividual, Periodo


class CalculoMetasService:
    """Servicio para calcular el cumplimiento de metas y evaluar el semáforo diario."""

    TOPE_MAXIMO_COMPUTABLE = Decimal("120.00")  # Exigencia Evaluación 3
    # TODO(Valentina/Nicolás): unificar el tope (120 vs 150) en una sola constante

    @classmethod
    def calcular_cumplimiento_funcionario(cls, funcionario_id, periodo_id, fecha_evaluacion=None):
        """
        Calcula el avance de un funcionario para un período dado:
        - Solo considera actividades aprobadas (estado de verificación aprobada, pondera).
        - Pondera según el peso del ítem en el cargo.
        - Aplica el tope máximo computable del 120%.
        """
        if fecha_evaluacion is None:
            fecha_evaluacion = date.today()

        periodo = Periodo.objects.get(pk=periodo_id)
        inicio, fin = _limites_del_periodo(periodo)

        # 1. Obtener las metas asignadas al funcionario a través de meta_delegacion
        try:
            metas = MetaIndividual.objects.filter(
                funcionario_id=funcionario_id,
                meta_delegacion__periodo=periodo,
            ).select_related(
                "meta_delegacion",
                "meta_delegacion__item",
                "meta_delegacion__item__cargo",
            )
        except Exception:
            metas = MetaIndividual.objects.filter(funcionario_id=funcionario_id).select_related(
                "meta_delegacion", "meta_delegacion__item"
            )

        items_calculados = []
        cumplimiento_bruto_total = Decimal("0.00")

        for meta in metas:
            # Obtener el ítem a través de la relación meta_delegacion
            meta_del = getattr(meta, "meta_delegacion", None)
            item = getattr(meta_del, "item", None) if meta_del else getattr(meta, "item", None)
            valor_objetivo = meta.valor_objetivo or Decimal("0.00")

            if not item:
                continue

            # Filtrar actividades del funcionario asociadas al ítem y período
            avance_aprobado = Actividad.objects.filter(
                funcionario_id=funcionario_id,
                item=item,
                tipo_registro=Actividad.ACTIVIDAD,
                estado_verificacion=Actividad.VERIF_APROBADA,
                pondera=True,
                fecha__gte=inicio,
                fecha__lt=fin,
            ).count()

            # Porcentaje de cumplimiento del ítem individual
            if valor_objetivo > 0:
                pct_item = (Decimal(avance_aprobado) / Decimal(str(valor_objetivo))) * Decimal(
                    "100.00"
                )
            else:
                pct_item = Decimal("0.00")

            # Ponderación individual sobre el total del cargo
            ponderador = getattr(item, "ponderador", Decimal("0.00")) or Decimal("0.00")
            aporte_ponderado = (pct_item * ponderador) / Decimal("100.00")
            cumplimiento_bruto_total += aporte_ponderado

            items_calculados.append(
                {
                    "id_item": getattr(item, "id_item", getattr(item, "pk", None)),
                    "nombre_item": getattr(item, "nombre", ""),
                    "meta_objetivo": float(valor_objetivo),
                    "avance_aprobado": avance_aprobado,
                    "ponderador": float(ponderador),
                    "cumplimiento_pct": round(float(pct_item), 2),
                    "aporte_ponderado": round(float(aporte_ponderado), 2),
                }
            )

        # 2. Aplicar el tope máximo computable del 120%
        cumplimiento_computable = min(cumplimiento_bruto_total, cls.TOPE_MAXIMO_COMPUTABLE)

        # 3. Evaluar el Semáforo Diario (Esperado vs. Real)
        dias_totales = (
            periodo.dias_computables or (periodo.fecha_termino - periodo.fecha_inicio).days + 1
        )
        dias_transcurridos = max(0, (fecha_evaluacion - periodo.fecha_inicio).days + 1)
        dias_transcurridos = min(dias_transcurridos, dias_totales)

        if dias_totales > 0:
            pct_esperado = (Decimal(dias_transcurridos) / Decimal(dias_totales)) * Decimal("100.00")
        else:
            pct_esperado = Decimal("0.00")

        # Regla del Semáforo: Verde (al día o sobre el esperado), Ámbar (próximo), Rojo (retrasado)
        if cumplimiento_computable >= pct_esperado:
            color_semaforo = "verde"
        elif cumplimiento_computable >= (pct_esperado * Decimal("0.80")):
            color_semaforo = "ambar"
        else:
            color_semaforo = "rojo"

        return {
            "funcionario_id": funcionario_id,
            "periodo_id": periodo_id,
            "cumplimiento_bruto": round(float(cumplimiento_bruto_total), 2),
            "cumplimiento_computable": round(float(cumplimiento_computable), 2),
            "porcentaje_esperado": round(float(pct_esperado), 2),
            "color_semaforo": color_semaforo,
            "items": items_calculados,
        }
