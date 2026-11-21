"""Flujo de verificación de actividades y reglas de las evidencias (SCRUM-123).

Estados: pendiente -> aprobada | rechazada | antecedentes; antecedentes -> pendiente cuando el
autor edita. Aprobada y rechazada son finales. Las funciones lanzan excepciones de DRF
(403 / 409 / 400) para que la API responda sin código extra.
"""

from django.db import transaction
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from core import auditoria
from core.models import Rol
from core.permissions import rol_de_usuario

from .models import Actividad, HistorialVerificacion

PENDIENTE = Actividad.VERIF_PENDIENTE
APROBADA = Actividad.VERIF_APROBADA
RECHAZADA = Actividad.VERIF_RECHAZADA
ANTECEDENTES = Actividad.VERIF_ANTECEDENTES

# Cambios permitidos por quien verifica. El paso antecedentes -> pendiente lo hace el autor.
TRANSICIONES = {PENDIENTE: {APROBADA, RECHAZADA, ANTECEDENTES}}
ESTADOS_EDITABLES = (PENDIENTE, ANTECEDENTES)
EXIGEN_OBSERVACION = (RECHAZADA, ANTECEDENTES)
ACCIONES = {
    "aprobar": APROBADA,
    "rechazar": RECHAZADA,
    "antecedentes": ANTECEDENTES,
    APROBADA: APROBADA,
    RECHAZADA: RECHAZADA,
}

ROLES_VERIFICADORES = (
    Rol.DELEGADO_TERRITORIAL,
    Rol.ENCARGADO_AREA,
    Rol.JEFE_DELEGACIONES,
    Rol.ADMINISTRADOR,
)
ROLES_GLOBALES = (Rol.JEFE_DELEGACIONES, Rol.ADMINISTRADOR)


class Conflicto(APIException):
    status_code = 409
    default_detail = "La operación no es válida para el estado actual."
    default_code = "conflicto"


def es_autor(usuario, actividad):
    return bool(usuario.funcionario_id) and actividad.funcionario_id == usuario.funcionario_id


def en_alcance(usuario, actividad):
    """Misma delegación del autor; Administrador y usuarios sin delegación ven todo."""
    if rol_de_usuario(usuario) == Rol.ADMINISTRADOR or usuario.delegacion_id is None:
        return True
    return usuario.delegacion_id == actividad.funcionario.delegacion_id


def puede_verificar(usuario, actividad):
    """Delegado y Encargado de su delegación; Jefe de delegaciones y Administrador, de todas.
    Nadie verifica lo propio."""
    rol = rol_de_usuario(usuario)
    if rol not in ROLES_VERIFICADORES or es_autor(usuario, actividad):
        return False
    if rol in ROLES_GLOBALES:
        return True
    return usuario.delegacion_id == actividad.funcionario.delegacion_id


def puede_gestionar_evidencias(usuario, actividad):
    """Subir o quitar evidencias: el autor o un verificador con alcance sobre la actividad."""
    if es_autor(usuario, actividad):
        return True
    rol = rol_de_usuario(usuario)
    return rol in ROLES_VERIFICADORES and en_alcance(usuario, actividad)


def puede_ver(usuario, actividad):
    """Ver la actividad y descargar sus evidencias (el Funcionario, solo las propias)."""
    if rol_de_usuario(usuario) == Rol.FUNCIONARIO:
        return es_autor(usuario, actividad)
    return en_alcance(usuario, actividad)


def validar_modificable(actividad):
    if actividad.estado_verificacion == APROBADA:
        raise Conflicto("La actividad está aprobada y no se puede modificar.")


def validar_edicion(usuario, actividad):
    """Edita solo el autor y solo en pendiente o antecedentes (409 si ya no es editable)."""
    validar_modificable(actividad)
    if not es_autor(usuario, actividad):
        raise PermissionDenied("Solo el autor puede editar la actividad.")
    if actividad.estado_verificacion not in ESTADOS_EDITABLES:
        raise Conflicto("Una actividad rechazada no se puede editar.")


def _registrar_cambio(usuario, actividad, anterior, nuevo, observacion):
    HistorialVerificacion.objects.create(
        actividad=actividad,
        usuario=usuario,
        estado_anterior=anterior,
        estado_nuevo=nuevo,
        observacion=observacion,
    )


def verificar(usuario, actividad, accion, observacion=""):
    """Aplica una transición de quien verifica. Devuelve la actividad actualizada."""
    if not puede_verificar(usuario, actividad):
        raise PermissionDenied("No puedes verificar esta actividad.")
    nuevo = ACCIONES.get(str(accion or "").strip().lower())
    if nuevo is None:
        raise ValidationError({"accion": "Use aprobar, rechazar o antecedentes."})
    observacion = (observacion or "").strip()
    with transaction.atomic():
        # Se relee con bloqueo: dos verificadores a la vez no pueden pisarse.
        actividad = Actividad.objects.select_for_update().get(pk=actividad.pk)
        anterior = actividad.estado_verificacion
        if nuevo not in TRANSICIONES.get(anterior, set()):
            raise Conflicto(f"No se puede pasar de {anterior} a {nuevo}.")
        if nuevo in EXIGEN_OBSERVACION and not observacion:
            raise ValidationError({"observacion": "La observación es obligatoria."})
        actividad.estado_verificacion = nuevo
        actividad.save(update_fields=["estado_verificacion"])
        _registrar_cambio(usuario, actividad, anterior, nuevo, observacion)
        auditoria.registrar(
            usuario,
            "verificar",
            actividad,
            anterior={"estado_verificacion": anterior},
            nuevo={"estado_verificacion": nuevo, "observacion": observacion},
        )
    return actividad


def reabrir_por_edicion(usuario, actividad):
    """antecedentes -> pendiente cuando el autor edita (se llama dentro de la transacción)."""
    if actividad.estado_verificacion != ANTECEDENTES:
        return
    actividad.estado_verificacion = PENDIENTE
    actividad.save(update_fields=["estado_verificacion"])
    _registrar_cambio(usuario, actividad, ANTECEDENTES, PENDIENTE, "Corregida por el autor.")
