"""Seguimiento de actividades (Épica 2, HU02, HU03, HU05, HU06 y HU08).

Quién puede hacer qué (siempre se valida en el servidor; el menú solo es presentación):
  - Administrador: todo, en todas las delegaciones.
  - Delegado territorial: todo dentro de su delegación (la del funcionario autor).
  - Autor o responsable de la actividad (Funcionario o Encargado de área con ficha activa):
    cambia estado, fecha de compromiso y motivo de atraso, y comenta.
  - Jefe de delegaciones y Alcaldesa: solo consultan (no usan estas operaciones).
Una actividad aprobada en la verificación no se modifica (misma regla que el ingreso); una
actividad Realizada queda cerrada para el seguimiento. Comentar no modifica la actividad.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission

from core.models import Rol
from core.permissions import rol_de_usuario
from organizacion.models import Area
from personas.models import Funcionario

from . import verificacion
from .models import Actividad, ActividadHistorial, Comentario

# HU03: Realizado es final; Ingresado solo es el punto de partida.
TRANSICIONES = {
    Actividad.INGRESADO: {Actividad.PENDIENTE, Actividad.EN_PROCESO, Actividad.REALIZADO},
    Actividad.PENDIENTE: {Actividad.EN_PROCESO, Actividad.REALIZADO},
    Actividad.EN_PROCESO: {Actividad.PENDIENTE, Actividad.REALIZADO},
    Actividad.REALIZADO: set(),
}

MIN_MOTIVO = 10  # HU05: un motivo de atraso no puede ser un "ok" o un punto
MAX_MOTIVO = 255
MAX_COMENTARIO = 1000

ROLES_SEGUIMIENTO = (
    Rol.ADMINISTRADOR,
    Rol.DELEGADO_TERRITORIAL,
    Rol.ENCARGADO_AREA,
    Rol.FUNCIONARIO,
)


class PuedeHacerSeguimiento(BasePermission):
    """Roles que dan seguimiento, con alcance (delegación o acceso global)."""

    message = "Tu rol no puede dar seguimiento a las actividades."

    def has_permission(self, request, view):
        user = request.user
        return rol_de_usuario(user) in ROLES_SEGUIMIENTO and verificacion.tiene_alcance(user)


def es_gestor(usuario, actividad):
    """Administrador, o Delegado de la delegación de la actividad."""
    rol = rol_de_usuario(usuario)
    if rol == Rol.ADMINISTRADOR:
        return True
    return (
        rol == Rol.DELEGADO_TERRITORIAL
        and usuario.delegacion_id is not None
        and usuario.delegacion_id == actividad.funcionario.delegacion_id
    )


def es_participante(usuario, actividad):
    """Autor o responsable de la actividad (con ficha activa)."""
    return verificacion.tiene_ficha_activa(usuario) and usuario.funcionario_id in (
        actividad.funcionario_id,
        actividad.responsable_id,
    )


def exigir_gestor(usuario, actividad):
    if not es_gestor(usuario, actividad):
        raise PermissionDenied(
            "Solo el Administrador o el Delegado de la delegación pueden asignar."
        )


def exigir_participante(usuario, actividad):
    if not (es_gestor(usuario, actividad) or es_participante(usuario, actividad)):
        raise PermissionDenied("Solo el autor, el responsable o la jefatura pueden hacerlo.")


def exigir_abierta(actividad):
    """Aprobada: no se modifica. Realizada: cerrada para el seguimiento."""
    verificacion.validar_modificable(actividad)
    if actividad.estado == Actividad.REALIZADO:
        raise ValidationError({"estado": "La actividad ya está realizada y no admite más cambios."})


def limpiar(valor):
    return (valor or "").strip()


def validar_motivo(valor):
    valor = limpiar(valor)
    if len(valor) < MIN_MOTIVO:
        raise serializers.ValidationError(
            f"Explica el motivo del atraso (al menos {MIN_MOTIVO} caracteres)."
        )
    if len(valor) > MAX_MOTIVO:
        raise serializers.ValidationError(f"Máximo {MAX_MOTIVO} caracteres.")
    return valor


def registrar_cambio(usuario, actividad, campo, anterior, nuevo, ahora=None):
    """Una fila de actividad_historial (HU03, HU05, HU06)."""
    return ActividadHistorial.objects.create(
        actividad=actividad,
        campo=campo,
        valor_anterior=None if anterior in (None, "") else str(anterior),
        valor_nuevo=str(nuevo),
        usuario=usuario,
        fecha_cambio=ahora or timezone.now(),
    )


def aplicar(actividad, **campos):
    """Guarda campos de la actividad; el bloqueo de aprobadas del modelo responde 409."""
    for campo, valor in campos.items():
        setattr(actividad, campo, valor)
    try:
        actividad.save(update_fields=list(campos))
    except DjangoValidationError as error:
        raise verificacion.Conflicto(error.messages[0])


# --- Serializers de entrada -------------------------------------------------------------


class AsignarSerializer(serializers.Serializer):
    """HU02: área, prioridad y responsable (opcional)."""

    area = serializers.PrimaryKeyRelatedField(queryset=Area.objects.all())
    prioridad = serializers.ChoiceField(choices=Actividad.PRIORIDADES)
    responsable = serializers.PrimaryKeyRelatedField(
        queryset=Funcionario.objects.select_related("cargo"), required=False, allow_null=True
    )

    def validate(self, attrs):
        actividad = self.context["actividad"]
        delegacion_id = actividad.funcionario.delegacion_id
        area, responsable = attrs["area"], attrs.get("responsable")
        if area.delegacion_id != delegacion_id:
            raise serializers.ValidationError(
                {"area": "El área debe ser de la delegación de la actividad."}
            )
        if area.estado != "activa":
            raise serializers.ValidationError({"area": "El área está inactiva."})
        tipo = actividad.tipo_atencion
        if tipo and tipo.area != area.nombre:
            raise serializers.ValidationError(
                {"area": "El área no corresponde al tipo de atención de la actividad."}
            )
        if responsable:
            if responsable.estado != Funcionario.ACTIVO:
                raise serializers.ValidationError({"responsable": "El responsable está inactivo."})
            if responsable.delegacion_id != delegacion_id:
                raise serializers.ValidationError(
                    {"responsable": "El responsable debe ser de la delegación de la actividad."}
                )
            area_cargo = responsable.cargo.area_id
            if area_cargo is not None and area_cargo != area.pk:
                raise serializers.ValidationError(
                    {"responsable": "El cargo del responsable no pertenece al área elegida."}
                )
        return attrs


class MotivoOpcionalMixin(serializers.Serializer):
    """HU05: si la actividad está vencida hace falta un motivo (nuevo o ya registrado)."""

    motivo_atraso = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)

    def validar_motivo_si_vencida(self, attrs):
        actividad = self.context["actividad"]
        motivo = limpiar(attrs.get("motivo_atraso"))
        if motivo:
            try:
                attrs["motivo_atraso"] = validar_motivo(motivo)
            except serializers.ValidationError as error:
                raise serializers.ValidationError({"motivo_atraso": error.detail})
        elif actividad.esta_vencida and not limpiar(actividad.motivo_atraso):
            raise serializers.ValidationError(
                {
                    "motivo_atraso": "La actividad está vencida: indica el motivo del atraso "
                    f"(al menos {MIN_MOTIVO} caracteres)."
                }
            )
        else:
            attrs.pop("motivo_atraso", None)
        return attrs


class CambiarEstadoSerializer(MotivoOpcionalMixin):
    """HU03 (+ HU05 si la actividad está vencida)."""

    estado = serializers.ChoiceField(choices=Actividad.ESTADOS)

    def validate(self, attrs):
        actividad = self.context["actividad"]
        nuevo = attrs["estado"]
        if nuevo == actividad.estado:
            raise serializers.ValidationError({"estado": "La actividad ya está en ese estado."})
        if nuevo not in TRANSICIONES[actividad.estado]:
            raise serializers.ValidationError(
                {"estado": f"No se puede pasar de «{actividad.estado}» a «{nuevo}»."}
            )
        return self.validar_motivo_si_vencida(attrs)


class FechaCompromisoSerializer(MotivoOpcionalMixin):
    """HU06 (+ HU05 si la actividad ya está vencida)."""

    fecha_compromiso = serializers.DateField()

    def validate_fecha_compromiso(self, valor):
        if valor < timezone.localdate():
            raise serializers.ValidationError("La fecha de compromiso no puede ser anterior a hoy.")
        return valor

    def validate(self, attrs):
        actividad = self.context["actividad"]
        if attrs["fecha_compromiso"] == actividad.fecha_compromiso:
            raise serializers.ValidationError(
                {"fecha_compromiso": "Esa ya es la fecha de compromiso vigente."}
            )
        return self.validar_motivo_si_vencida(attrs)


class MotivoAtrasoSerializer(serializers.Serializer):
    """HU05: registrar o corregir el motivo de una actividad vencida o cerrada con atraso."""

    motivo_atraso = serializers.CharField(trim_whitespace=False)

    def validate_motivo_atraso(self, valor):
        return validar_motivo(valor)

    def validate(self, attrs):
        actividad = self.context["actividad"]
        if not (actividad.esta_vencida or actividad.dias_atraso > 0):
            raise serializers.ValidationError(
                {"motivo_atraso": "La actividad no está atrasada: no necesita motivo."}
            )
        if attrs["motivo_atraso"] == limpiar(actividad.motivo_atraso):
            raise serializers.ValidationError({"motivo_atraso": "Ese ya es el motivo registrado."})
        return attrs


# --- Serializers de salida --------------------------------------------------------------


def nombre_usuario(usuario):
    return usuario.get_full_name() or usuario.email


class HistorialSeguimientoSerializer(serializers.ModelSerializer):
    campo_nombre = serializers.CharField(source="get_campo_display", read_only=True)
    usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = ActividadHistorial
        fields = [
            "id_historial",
            "campo",
            "campo_nombre",
            "valor_anterior",
            "valor_nuevo",
            "usuario",
            "usuario_nombre",
            "fecha_cambio",
        ]

    def get_usuario_nombre(self, obj):
        return nombre_usuario(obj.usuario)


class ComentarioSerializer(serializers.ModelSerializer):
    """HU08."""

    usuario_nombre = serializers.SerializerMethodField()
    usuario_rol = serializers.CharField(source="usuario.rol.nombre", read_only=True)

    class Meta:
        model = Comentario
        fields = ["id_comentario", "usuario", "usuario_nombre", "usuario_rol", "texto", "fecha"]
        read_only_fields = ["usuario", "fecha"]

    def get_usuario_nombre(self, obj):
        return nombre_usuario(obj.usuario)

    def validate_texto(self, valor):
        valor = limpiar(valor)
        if not valor:
            raise serializers.ValidationError("Escribe el comentario.")
        if len(valor) > MAX_COMENTARIO:
            raise serializers.ValidationError(f"Máximo {MAX_COMENTARIO} caracteres.")
        return valor
