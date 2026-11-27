from datetime import date
from decimal import Decimal
from django.db.models import Count, Sum
from atenciones.models import Actividad
from .cumplimiento import TOPE_CUMPLIMIENTO, _limites_del_periodo
from .models import Item, MetaDelegacion, MetaIndividual, Periodo


class CalculoMetasService:
    """Servicio para calcular el cumplimiento de metas y evaluar el semáforo diario."""

    TOPE_MAXIMO_COMPUTABLE = TOPE_CUMPLIMIENTO  # alias del tope único (metas/cumplimiento.py)
    FACTOR_SEMAFORO_AMBAR = Decimal("0.80")

    @staticmethod
    def calcular_porcentaje_esperado(periodo, fecha_evaluacion=None):
        if fecha_evaluacion is None:
            fecha_evaluacion = date.today()

        dias_totales = (
            periodo.dias_computables or (periodo.fecha_termino - periodo.fecha_inicio).days + 1
        )
        dias_transcurridos = max(0, (fecha_evaluacion - periodo.fecha_inicio).days + 1)
        dias_transcurridos = min(dias_transcurridos, dias_totales)

        if dias_totales > 0:
            return (Decimal(dias_transcurridos) / Decimal(dias_totales)) * Decimal("100.00")
        return Decimal("0.00")

    @classmethod
    def calcular_color_semaforo(cls, cumplimiento, porcentaje_esperado):
        if cumplimiento >= porcentaje_esperado:
            return "verde"
        if cumplimiento >= (porcentaje_esperado * cls.FACTOR_SEMAFORO_AMBAR):
            return "ambar"
        return "rojo"

    @classmethod
    def consolidar_items(cls, filas):
        """
        Aplica la fórmula de cumplimiento a filas (meta, item, avance_aprobado).
        Devuelve (items_calculados, cumplimiento_bruto, cumplimiento_computable con tope).
        """
        items_calculados = []
        cumplimiento_bruto_total = Decimal("0.00")

        for meta, item, avance_aprobado in filas:
            valor_objetivo = meta.valor_objetivo or Decimal("0.00")

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

        # Tope máximo computable (150%)
        cumplimiento_computable = min(cumplimiento_bruto_total, cls.TOPE_MAXIMO_COMPUTABLE)
        return items_calculados, cumplimiento_bruto_total, cumplimiento_computable

    @classmethod
    def calcular_computable_por_funcionario(cls, periodo, funcionario_ids):
        """
        Versión masiva (2 consultas en total) de calcular_cumplimiento_funcionario.
        Devuelve {funcionario_id: cumplimiento_computable (Decimal sin redondear)}.
        """
        funcionario_ids = list(funcionario_ids)
        inicio, fin = _limites_del_periodo(periodo)
        metas_por_funcionario = {pk: [] for pk in funcionario_ids}
        metas = MetaIndividual.objects.filter(
            funcionario_id__in=funcionario_ids, meta_delegacion__periodo=periodo
        ).select_related("meta_delegacion", "meta_delegacion__item")
        for meta in metas:
            metas_por_funcionario[meta.funcionario_id].append(meta)

        avances = {
            (fila["funcionario_id"], fila["item_id"]): fila["total"]
            for fila in Actividad.objects.filter(
                funcionario_id__in=funcionario_ids,
                tipo_registro=Actividad.ACTIVIDAD,
                estado_verificacion=Actividad.VERIF_APROBADA,
                pondera=True,
                fecha__gte=inicio,
                fecha__lt=fin,
            )
            .values("funcionario_id", "item_id")
            .annotate(total=Count("pk"))
        }

        resultado = {}
        for pk in funcionario_ids:
            filas = [
                (
                    meta,
                    meta.meta_delegacion.item,
                    avances.get((pk, meta.meta_delegacion.item_id), 0),
                )
                for meta in metas_por_funcionario[pk]
                if meta.meta_delegacion.item
            ]
            resultado[pk] = cls.consolidar_items(filas)[2]
        return resultado

    @classmethod
    def calcular_cumplimiento_funcionario(
        cls, funcionario_id, periodo_id, fecha_evaluacion=None, periodo=None
    ):
        """
        Calcula el avance de un funcionario para un período dado:
        - Solo considera actividades aprobadas (estado de verificación aprobada, pondera).
        - Pondera según el peso del ítem en el cargo.
        - Aplica el tope máximo computable (150%).
        """
        if fecha_evaluacion is None:
            fecha_evaluacion = date.today()

        if periodo is None:
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

        filas = []
        for meta in metas:
            meta_del = getattr(meta, "meta_delegacion", None)
            item = getattr(meta_del, "item", None) if meta_del else getattr(meta, "item", None)
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
            filas.append((meta, item, avance_aprobado))

        items_calculados, cumplimiento_bruto_total, cumplimiento_computable = cls.consolidar_items(
            filas
        )

        # 3. Evaluar el Semáforo Diario (Esperado vs. Real)
        pct_esperado = cls.calcular_porcentaje_esperado(periodo, fecha_evaluacion)
        color_semaforo = cls.calcular_color_semaforo(cumplimiento_computable, pct_esperado)

        return {
            "funcionario_id": funcionario_id,
            "periodo_id": periodo_id,
            "cumplimiento_bruto": round(float(cumplimiento_bruto_total), 2),
            "cumplimiento_computable": round(float(cumplimiento_computable), 2),
            "porcentaje_esperado": round(float(pct_esperado), 2),
            "color_semaforo": color_semaforo,
            "items": items_calculados,
        }
