"""Validadores compartidos. Usar siempre estos, nunca uno propio."""

import re

from django.core.exceptions import ValidationError


def normalizar_rut(rut):
    """'12.345.678-k' -> '12345678-K'."""
    limpio = re.sub(r"[^0-9kK]", "", str(rut or "")).upper()
    if len(limpio) < 2:
        return limpio
    return f"{limpio[:-1]}-{limpio[-1]}"


def calcular_dv(cuerpo):
    suma, factor = 0, 2
    for digito in reversed(str(cuerpo)):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - (suma % 11)
    return {11: "0", 10: "K"}.get(resto, str(resto))


def rut_es_valido(rut):
    rut = normalizar_rut(rut)
    if not re.fullmatch(r"\d{7,8}-[0-9K]", rut):
        return False
    cuerpo, dv = rut.split("-")
    return calcular_dv(cuerpo) == dv


def validar_rut(rut):
    """Para validators=[validar_rut] en modelos o dentro de validate_rut en serializers."""
    if not rut_es_valido(rut):
        raise ValidationError("RUT inválido.", code="rut_invalido")
    return normalizar_rut(rut)
