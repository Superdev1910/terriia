from decimal import ROUND_HALF_UP, Decimal

UMBRAL_CUMPLIDA = Decimal("80")  
TOPE_CUMPLIMIENTO = Decimal("150")  
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