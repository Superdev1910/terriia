from decimal import ROUND_HALF_UP, Decimal
from django.db.models import Sum
from datetime import datetime, time, timedelta
from django.utils import timezone

UMBRAL_CUMPLIDA = Decimal("80")
TOPE_CUMPLIMIENTO = Decimal("120")  # Tope computable único (120%) de todo el sistema
_CENTESIMAS = Decimal("0.01")


def _decimal(valor):
    return valor if isinstance(valor, Decimal) else Decimal(str(valor))


def calcular_cumplimiento(valor_objetivo, avance_real, ponderador=None):
    objetivo = _decimal(valor_objetivo)
    avance = _decimal(avance_real)
    if objetivo <= 0:
        raise ValueError("La meta debe ser mayor a cero.")
    if avance < 0:
        raise ValueError("El avance real no puede ser negativo.")

    bruto = avance / objetivo * 100
    resultado = {
        "porcentaje": min(bruto, TOPE_CUMPLIMIENTO).quantize(_CENTESIMAS, ROUND_HALF_UP),
        "cumplida": bruto >= UMBRAL_CUMPLIDA,
    }
    if ponderador is not None:
        ponderado = _decimal(ponderador) * resultado["porcentaje"] / 100
        resultado["ponderado"] = ponderado.quantize(_CENTESIMAS, ROUND_HALF_UP)
    return resultado


def ajuste_felicitaciones_reclamos(funcionario, periodo):
    from .models import FelicitacionReclamo

    total = FelicitacionReclamo.objects.filter(
        funcionario=funcionario, fecha__gte=periodo.fecha_inicio, fecha__lte=periodo.fecha_termino
    ).aggregate(total=Sum("impacto_pct"))["total"]
    return total or Decimal("0")


def cumplimiento_ponderado_total(ponderados, ajuste=0):
    total = sum((_decimal(p) for p in ponderados), Decimal("0")) + _decimal(ajuste)
    return total.quantize(_CENTESIMAS, ROUND_HALF_UP)


def _limites_del_periodo(periodo):
    inicio = timezone.make_aware(datetime.combine(periodo.fecha_inicio, time.min))
    fin = timezone.make_aware(datetime.combine(periodo.fecha_termino + timedelta(days=1), time.min))
    return inicio, fin


def avance_actual(funcionario, item, periodo):
    from atenciones.models import Actividad

    if item.tipo_meta != item.CONTEO:
        return None
    inicio, fin = _limites_del_periodo(periodo)
    return Actividad.objects.filter(
        funcionario=funcionario,
        item=item,
        tipo_registro=Actividad.ACTIVIDAD,
        estado_verificacion=Actividad.VERIF_APROBADA,
        pondera=True,
        fecha__gte=inicio,
        fecha__lt=fin,
    ).count()


def cumplimiento_funcionario(funcionario, periodo):
    from .models import MetaIndividual

    metas = MetaIndividual.objects.filter(
        funcionario=funcionario, meta_delegacion__periodo=periodo
    ).select_related("meta_delegacion__item")
    filas, ponderados = [], []
    for meta in metas:
        item = meta.meta_delegacion.item
        avance = avance_actual(funcionario, item, periodo)
        fila = {
            "item": item.nombre,
            "tipo_meta": item.tipo_meta,
            "ponderador": item.ponderador,
            "meta": meta.valor_objetivo,
            "avance": avance,
            "porcentaje": None,
            "cumplida": None,
            "ponderado": None,
        }
        if avance is not None:
            resultado = calcular_cumplimiento(meta.valor_objetivo, avance, item.ponderador)
            fila.update(resultado)
            ponderados.append(resultado["ponderado"])
        filas.append(fila)
    ajuste = ajuste_felicitaciones_reclamos(funcionario, periodo)
    return {
        "actividades": filas,
        "ajuste": ajuste,
        "total": cumplimiento_ponderado_total(ponderados, ajuste),
        "completo": all(fila["avance"] is not None for fila in filas),
    }
