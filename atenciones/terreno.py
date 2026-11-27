"""Verificación en terreno de las solicitudes del Tubo (HU29, SCRUM-32).

Flujo de una solicitud con `ingreso_a_tubo=True`:
  1. se registra y queda Ingresada;
  2. alguien va a terreno y registra la visita `inicial` (conforme o no conforme);
  3. con la visita inicial conforme se puede dar servicio (cambiar estado a Pendiente o En proceso);
  4. terminado el servicio se registra la visita de `cierre`;
  5. solo con el cierre conforme (posterior a la última inicial conforme) pasa a Realizado.
Asignar el responsable se permite antes de la visita inicial: es quien va a terreno.
Las solicitudes sin la marca no se ven afectadas. Registrar la visita puede quien verifica
(con alcance) y el responsable asignado.
"""

import os

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from core import auditoria
from core.models import Rol
from core.permissions import rol_de_usuario

from . import evidencias, verificacion
from .models import Actividad, ActividadHistorial, VisitaTerreno

MAX_OBSERVACION = 1000
MSJ_SIN_INICIAL = "Requiere verificación en terreno conforme antes de asignar o avanzar."
MSJ_SIN_CIERRE = "Requiere verificación de cierre conforme."
MSJ_SIN_PERMISO = "Solo quien verifica o el responsable asignado puede registrar la visita."


def _visitas(actividad):
    """Visitas de la actividad en orden cronológico (usa el prefetch si viene cargado)."""
    return sorted(actividad.visitas_terreno.all(), key=lambda v: v.pk)


def _ultima(visitas, tipo, resultado=None):
    for v in reversed(visitas):
        if v.tipo == tipo and (resultado is None or v.resultado == resultado):
            return v
    return None


def estado_terreno(actividad):
    """(resultado de la última inicial, resultado del cierre vigente); None si no hay.

    El cierre solo vale si es posterior a la última inicial conforme."""
    visitas = _visitas(actividad)
    inicial = _ultima(visitas, VisitaTerreno.INICIAL)
    base = _ultima(visitas, VisitaTerreno.INICIAL, VisitaTerreno.CONFORME)
    cierre = _ultima(visitas, VisitaTerreno.CIERRE)
    if cierre and base and cierre.pk < base.pk:
        cierre = None
    return (inicial.resultado if inicial else None, cierre.resultado if cierre else None)


def tiene_inicial_conforme(actividad):
    return actividad.visitas_terreno.filter(
        tipo=VisitaTerreno.INICIAL, resultado=VisitaTerreno.CONFORME
    ).exists()


def tiene_cierre_conforme(actividad):
    """Cierre conforme registrado después de la última inicial conforme."""
    base = (
        actividad.visitas_terreno.filter(
            tipo=VisitaTerreno.INICIAL, resultado=VisitaTerreno.CONFORME
        )
        .order_by("-pk")
        .first()
    )
    if base is None:
        return False
    return actividad.visitas_terreno.filter(
        tipo=VisitaTerreno.CIERRE, resultado=VisitaTerreno.CONFORME, pk__gt=base.pk
    ).exists()


def puede_registrar(usuario, actividad):
    """Quien verifica (con alcance de delegación) o el responsable asignado (ficha activa)."""
    rol = rol_de_usuario(usuario)
    if rol in verificacion.ROLES_VERIFICADORES:
        return verificacion.en_alcance(usuario, actividad)
    return (
        rol == Rol.FUNCIONARIO
        and verificacion.tiene_ficha_activa(usuario)
        and verificacion.es_responsable(usuario, actividad)
        and verificacion.en_alcance(usuario, actividad)
    )


def puede_registrar_ahora(usuario, actividad):
    """Lo anterior más el estado de la solicitud (para mostrar el botón)."""
    return (
        actividad.ingreso_a_tubo
        and actividad.estado != Actividad.REALIZADO
        and actividad.estado_verificacion != Actividad.VERIF_APROBADA
        and puede_registrar(usuario, actividad)
    )


def validar_asignacion(actividad):
    """Asignar en Ingresado se permite (el responsable hace la visita); después, ya hay inicial."""
    if actividad.ingreso_a_tubo and actividad.estado != Actividad.INGRESADO:
        if not tiene_inicial_conforme(actividad):
            raise verificacion.Conflicto(MSJ_SIN_INICIAL)


def validar_cambio_estado(actividad, nuevo):
    if not actividad.ingreso_a_tubo:
        return
    if actividad.estado == Actividad.INGRESADO and not tiene_inicial_conforme(actividad):
        raise verificacion.Conflicto(MSJ_SIN_INICIAL)
    if nuevo == Actividad.REALIZADO and not tiene_cierre_conforme(actividad):
        raise verificacion.Conflicto(MSJ_SIN_CIERRE)


def registrar_visita(usuario, actividad, datos):
    """Crea la visita con historial y auditoría (HTTP 403 / 409 si no corresponde)."""
    if not puede_registrar(usuario, actividad):
        raise PermissionDenied(MSJ_SIN_PERMISO)
    with transaction.atomic():
        bloqueada = Actividad.objects.select_for_update().get(pk=actividad.pk)
        verificacion.validar_modificable(bloqueada)
        if not bloqueada.ingreso_a_tubo:
            raise verificacion.Conflicto("La solicitud no requiere verificación en terreno.")
        if bloqueada.estado == Actividad.REALIZADO:
            raise verificacion.Conflicto("La solicitud ya está realizada: no admite más visitas.")
        if datos["tipo"] == VisitaTerreno.CIERRE:
            if not tiene_inicial_conforme(bloqueada):
                raise verificacion.Conflicto(
                    "La verificación de cierre requiere una verificación en terreno conforme previa."
                )
            if bloqueada.estado == Actividad.INGRESADO:
                raise verificacion.Conflicto(
                    "La verificación de cierre se hace con el servicio Pendiente o En proceso."
                )
        visita = VisitaTerreno.objects.create(actividad=bloqueada, usuario=usuario, **datos)
        ActividadHistorial.objects.create(
            actividad=bloqueada,
            campo=ActividadHistorial.VISITA_TERRENO,
            valor_anterior=None,
            valor_nuevo=f"{visita.get_tipo_display()}: {visita.get_resultado_display()}",
            usuario=usuario,
        )
        nuevo = auditoria.foto(visita)
        nuevo.pop("archivo", None)
        auditoria.registrar(usuario, "visita_terreno", visita, nuevo=nuevo)
    return visita


class VisitaTerrenoSerializer(serializers.ModelSerializer):
    """Entrada (multipart, con archivo opcional) y salida. El archivo no tiene URL pública."""

    archivo = serializers.FileField(write_only=True, required=False, allow_null=True)
    usuario_nombre = serializers.SerializerMethodField()
    tipo_nombre = serializers.CharField(source="get_tipo_display", read_only=True)
    resultado_nombre = serializers.CharField(source="get_resultado_display", read_only=True)
    descarga = serializers.SerializerMethodField()

    class Meta:
        model = VisitaTerreno
        fields = [
            "id_visita",
            "actividad",
            "tipo",
            "tipo_nombre",
            "resultado",
            "resultado_nombre",
            "observacion",
            "fecha",
            "usuario",
            "usuario_nombre",
            "latitud",
            "longitud",
            "archivo",
            "nombre_original",
            "tipo_contenido",
            "tamano",
            "descarga",
        ]
        read_only_fields = [
            "actividad",
            "fecha",
            "usuario",
            "nombre_original",
            "tipo_contenido",
            "tamano",
        ]
        extra_kwargs = {
            "latitud": {"min_value": -90, "max_value": 90, "required": False},
            "longitud": {"min_value": -180, "max_value": 180, "required": False},
        }

    def get_usuario_nombre(self, obj):
        return obj.usuario.get_full_name() or obj.usuario.email

    def get_descarga(self, obj):
        return f"/api/visitas-terreno/{obj.pk}/archivo/" if obj.archivo else None

    def validate_observacion(self, valor):
        valor = (valor or "").strip()
        if len(valor) > MAX_OBSERVACION:
            raise serializers.ValidationError(f"Máximo {MAX_OBSERVACION} caracteres.")
        return valor

    def validate_archivo(self, archivo):
        if archivo is None:
            return None
        try:
            tipo, extension = evidencias.validar_archivo(archivo)
        except DjangoValidationError as e:
            raise serializers.ValidationError(e.messages[0])
        self._tipo = tipo
        self._nombre_original = os.path.basename(archivo.name)[:150]
        archivo.name = f"visita{extension}"  # la ruta final usa uuid; la extensión es la real
        return archivo

    def validate(self, attrs):
        if attrs.get("resultado") == VisitaTerreno.NO_CONFORME and not attrs.get("observacion"):
            raise serializers.ValidationError(
                {"observacion": "La observación es obligatoria si la visita no es conforme."}
            )
        if (attrs.get("latitud") is None) != (attrs.get("longitud") is None):
            raise serializers.ValidationError(
                {"latitud": "Indica latitud y longitud juntas (o ninguna)."}
            )
        archivo = attrs.pop("archivo", None)
        if archivo is not None:
            attrs["archivo"] = archivo
            attrs["nombre_original"] = self._nombre_original
            attrs["tipo_contenido"] = self._tipo
            attrs["tamano"] = archivo.size
        return attrs
