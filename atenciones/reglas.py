"""Reglas de negocio del ingreso de actividades (SCRUM-62).

Las usan el serializer (API) y Actividad.clean() (modelo), así hay una sola fuente de verdad.
Reciben objetos ya cargados (no ids) y lanzan django.core.exceptions.ValidationError con un
dict {campo: mensaje}; el serializer lo convierte en un 400.
"""

from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import Rol
from core.validators import normalizar_rut

MAX_ACTIVIDADES_POR_DIA = 7


def _local(fecha):
    if timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha)
    return timezone.localtime(fecha)


def limite_semana(fecha):
    """Instante desde el cual ya no se puede registrar en la semana (lunes a domingo) de `fecha`.

    La semana termina el domingo a medianoche y se cierra SEMANA_CIERRE_DIAS_GRACIA días después.
    """
    dia = _local(fecha).date()
    domingo = dia + timedelta(days=6 - dia.weekday())
    cierre = domingo + timedelta(days=1 + settings.SEMANA_CIERRE_DIAS_GRACIA)
    return timezone.make_aware(datetime.combine(cierre, time.min))


def validar_fecha(fecha, funcionario, excluir_pk=None, ahora=None):
    """Fecha futura, semana cerrada y tope de actividades por funcionario y día."""
    ahora = ahora or timezone.now()
    if fecha > ahora:
        raise ValidationError({"fecha": "La fecha no puede ser futura."})
    if ahora >= limite_semana(fecha):
        raise ValidationError(
            {"fecha": "La semana de esa fecha ya está cerrada: no se puede registrar en ella."}
        )
    dia = _local(fecha).date()
    inicio = timezone.make_aware(datetime.combine(dia, time.min))
    del_dia = funcionario.actividades.filter(
        fecha__gte=inicio, fecha__lt=inicio + timedelta(days=1)
    )
    if excluir_pk:
        del_dia = del_dia.exclude(pk=excluir_pk)
    if del_dia.count() >= MAX_ACTIVIDADES_POR_DIA:
        raise ValidationError(
            {
                "fecha": f"Máximo {MAX_ACTIVIDADES_POR_DIA} actividades por funcionario al día "
                "(ya se alcanzó el tope)."
            }
        )


def vecino_pertenece_a_delegacion(vecino, delegacion_id):
    """Con vecino.delegacion definida, manda ella. Si es nula (vecinos antiguos sin actividades),
    se deduce de sus actividades: es de la delegación si ya fue atendido en ella; si nunca fue
    atendido en ninguna, está libre."""
    if vecino.delegacion_id is not None:
        return vecino.delegacion_id == delegacion_id
    registros = vecino.actividades.all()
    if not registros.exists():
        return True
    return registros.filter(funcionario__delegacion_id=delegacion_id).exists()


def validar_consistencia(
    funcionario,
    item,
    area=None,
    territorio=None,
    vecino=None,
    tipo_atencion=None,
    sub_atencion=None,
):
    errores = {}
    delegacion_id = funcionario.delegacion_id
    if item is not None:
        if item.cargo_id != funcionario.cargo_id:
            errores["item"] = "El ítem no pertenece al cargo del funcionario."
        elif not item.activo:
            errores["item"] = "El ítem está inactivo."
    if area is not None:
        if area.delegacion_id != delegacion_id:
            errores["area"] = "El área no es válida para tu delegación."
        elif area.estado != "activa":
            errores["area"] = "El área está inactiva."
    if territorio is not None:
        if territorio.delegacion_id != delegacion_id:
            errores["territorio"] = "El territorio no es válido para tu delegación."
        elif not territorio.activo:
            errores["territorio"] = "El territorio está inactivo."
    if vecino is not None:
        if vecino.estado != "activo":
            errores["vecino"] = "El vecino no es válido para tu delegación."
        elif not vecino_pertenece_a_delegacion(vecino, delegacion_id):
            errores["vecino"] = "El vecino no es válido para tu delegación."
    if tipo_atencion is not None:
        if not tipo_atencion.activo:
            errores["tipo_atencion"] = "El tipo de atención está inactivo."
        elif area is not None and tipo_atencion.area != area.nombre:
            errores["tipo_atencion"] = "El tipo de atención no corresponde al área elegida."
    if sub_atencion is not None:
        if tipo_atencion is None or sub_atencion.tipo_atencion_id != tipo_atencion.pk:
            errores["sub_atencion"] = "La sub atención no pertenece al tipo de atención."
        elif not sub_atencion.activo:
            errores["sub_atencion"] = "La sub atención está inactiva."
    if errores:
        raise ValidationError(errores)


def validar_actividad(
    funcionario,
    item,
    fecha,
    area=None,
    territorio=None,
    vecino=None,
    tipo_atencion=None,
    sub_atencion=None,
    excluir_pk=None,
    ahora=None,
    validar_fecha_registro=True,
):
    # TODO(Patricio): confirmar con el cliente si se puede editar un registro de una semana
    # cerrada. Hoy, al editar sin cambiar la fecha, no se vuelve a exigir el cierre de semana.
    if validar_fecha_registro:
        validar_fecha(fecha, funcionario, excluir_pk=excluir_pk, ahora=ahora)
    validar_consistencia(funcionario, item, area, territorio, vecino, tipo_atencion, sub_atencion)


def es_delegado(vecino):
    """True si el RUT del vecino es el de un usuario con rol Delegado territorial."""
    if vecino is None:
        return False
    from personas.models import Usuario

    return Usuario.objects.filter(
        rut=normalizar_rut(vecino.rut), rol__nombre=Rol.DELEGADO_TERRITORIAL
    ).exists()


def calcular_ponderacion(vecino, contacto="", telefono="", es_coordinacion_preparatoria=False):
    """Devuelve (pondera, motivo). Si no pondera, el motivo explica por qué."""
    if es_coordinacion_preparatoria:
        return False, "Es una coordinación preparatoria."
    if es_delegado(vecino):
        return False, "El vecino atendido es el delegado territorial."
    nombre = (contacto or "").strip() or (
        f"{vecino.nombres} {vecino.apellidos}".strip() if vecino else ""
    )
    fono = (telefono or "").strip() or ((vecino.telefono or "").strip() if vecino else "")
    if not nombre:
        return False, "Falta el nombre de la persona atendida."
    if not fono:
        return False, "Falta el teléfono de la persona atendida."
    return True, ""
