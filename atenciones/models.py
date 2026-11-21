"""Catálogos de atención (SCRUM-61, modelo físico v2.5).

Cada área ofrece sus tipos de atención y cada tipo se divide en sub atenciones. La actividad
(T5) apunta a ambos con id_tipo_atencion e id_sub_atencion.

SCRUM-62 agrega Actividad (actividades y gestiones sociales) y su contador de código.
"""

import os
import secrets
import string
import uuid

from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from organizacion.models import Area


class TipoAtencion(models.Model):
    """Tabla `tipo_atencion`. El nombre no se repite dentro del área (sin importar mayúsculas)."""

    id_tipo_atencion = models.AutoField(primary_key=True)
    # Mismas 4 áreas del ENUM de area.nombre: se reutiliza la lista de organizacion.
    area = models.CharField(max_length=30, choices=Area.NOMBRES)
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "tipo_atencion"
        ordering = ["area", "nombre"]
        verbose_name = "tipo de atención"
        verbose_name_plural = "tipos de atención"
        # Las mayúsculas se revisan en el serializer: MariaDB 10.5 no admite índices con
        # Lower("nombre") (Django lo omitiría) y su cotejamiento utf8mb4_unicode_ci ya las ignora.
        constraints = [
            models.UniqueConstraint(fields=["area", "nombre"], name="uq_tipo_atencion_area_nombre")
        ]

    def __str__(self):
        return f"{self.nombre} ({self.get_area_display()})"


class SubAtencion(models.Model):
    """Tabla `sub_atencion`. Solo se crea bajo un tipo de atención activo."""

    id_sub_atencion = models.AutoField(primary_key=True)
    tipo_atencion = models.ForeignKey(
        TipoAtencion,
        on_delete=models.PROTECT,
        db_column="id_tipo_atencion",
        related_name="sub_atenciones",
    )
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "sub_atencion"
        ordering = ["tipo_atencion__area", "tipo_atencion__nombre", "nombre"]
        verbose_name = "sub atención"
        verbose_name_plural = "sub atenciones"
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_atencion", "nombre"], name="uq_sub_atencion_tipo_nombre"
            )
        ]

    def __str__(self):
        return f"{self.nombre} · {self.tipo_atencion.nombre}"


class ContadorCodigoActividad(models.Model):
    """Último correlativo usado por delegación y año (SCRUM-62).

    Se bloquea con select_for_update dentro de una transacción al generar el código, así dos
    registros simultáneos nunca reciben el mismo número.
    """

    delegacion = models.ForeignKey(
        "organizacion.Delegacion",
        on_delete=models.PROTECT,
        db_column="id_delegacion",
        related_name="contadores_actividad",
    )
    anio = models.PositiveSmallIntegerField()
    ultimo = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "contador_codigo_actividad"
        constraints = [
            models.UniqueConstraint(
                fields=["delegacion", "anio"], name="uq_contador_actividad_delegacion_anio"
            )
        ]

    def __str__(self):
        return f"{self.delegacion_id}/{self.anio}: {self.ultimo}"


class Actividad(models.Model):
    """Tabla `actividad` (SQL v2.4 + v2.5 + delta v2.6). Una sola tabla para actividades y
    gestiones sociales (`tipo_registro`).

    `estado` es el estado operativo (seguimiento); `estado_verificacion` es aparte: lo decide
    quien verifica y no depende del avance de la tarea.
    """

    ACTIVIDAD, GESTION_SOCIAL = "actividad", "gestion_social"
    TIPOS_REGISTRO = [(ACTIVIDAD, "Actividad"), (GESTION_SOCIAL, "Gestión social")]

    ORIGEN_FUNCIONARIO, ORIGEN_DELEGADO = "funcionario", "delegado"
    ORIGENES = [
        (ORIGEN_FUNCIONARIO, "Iniciativa del funcionario"),
        (ORIGEN_DELEGADO, "Solicitada por el delegado"),
    ]

    PRIORIDADES = [("alta", "Alta"), ("media", "Media"), ("baja", "Baja")]

    INGRESADO, PENDIENTE, EN_PROCESO, REALIZADO = (
        "Ingresado",
        "Pendiente",
        "En proceso",
        "Realizado",
    )
    ESTADOS = [(e, e) for e in (INGRESADO, PENDIENTE, EN_PROCESO, REALIZADO)]

    VERIF_PENDIENTE, VERIF_APROBADA, VERIF_RECHAZADA, VERIF_ANTECEDENTES = (
        "pendiente",
        "aprobada",
        "rechazada",
        "antecedentes",
    )
    ESTADOS_VERIFICACION = [
        (VERIF_PENDIENTE, "Pendiente"),
        (VERIF_APROBADA, "Aprobada"),
        (VERIF_RECHAZADA, "Rechazada"),
        (VERIF_ANTECEDENTES, "Requiere antecedentes"),
    ]

    id_actividad = models.AutoField(primary_key=True)
    codigo = models.CharField(max_length=24, unique=True, editable=False)
    tipo_registro = models.CharField(max_length=14, choices=TIPOS_REGISTRO, default=ACTIVIDAD)
    funcionario = models.ForeignKey(
        "personas.Funcionario",
        on_delete=models.PROTECT,
        db_column="id_funcionario",
        related_name="actividades",
    )  # autor
    item = models.ForeignKey(
        "metas.Item", on_delete=models.PROTECT, db_column="id_item", related_name="actividades"
    )
    vecino = models.ForeignKey(
        "territorio.Vecino",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        db_column="id_vecino",
        related_name="actividades",
    )
    territorio = models.ForeignKey(
        "territorio.Territorio",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        db_column="id_territorio",
        related_name="actividades",
    )
    area = models.ForeignKey(
        "organizacion.Area",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        db_column="id_area",
        related_name="actividades",
    )
    tipo_atencion = models.ForeignKey(
        TipoAtencion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        db_column="id_tipo_atencion",
        related_name="actividades",
    )
    sub_atencion = models.ForeignKey(
        SubAtencion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        db_column="id_sub_atencion",
        related_name="actividades",
    )
    fecha = models.DateTimeField(default=timezone.now)  # cuándo ocurrió
    fecha_registro = models.DateTimeField(auto_now_add=True)  # cuándo se ingresó al sistema
    descripcion = models.TextField(blank=True, default="")
    accion = models.CharField(max_length=255, blank=True, default="")
    contacto = models.CharField(max_length=150, blank=True, default="")
    telefono = models.CharField(max_length=20, blank=True, default="")
    ingreso_a_tubo = models.BooleanField(default=False)  # TODO(Brian): flujo del Tubo
    es_coordinacion_preparatoria = models.BooleanField(default=False)
    origen = models.CharField(max_length=11, choices=ORIGENES, default=ORIGEN_FUNCIONARIO)
    delegado_solicitante = models.ForeignKey(
        "personas.Usuario",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        db_column="id_delegado_solicitante",
        related_name="actividades_solicitadas",
    )
    # TODO(Brian): convertir en FK a Hito cuando exista
    hito_id = models.IntegerField(null=True, blank=True, db_column="id_hito")
    prioridad = models.CharField(max_length=5, choices=PRIORIDADES, null=True, blank=True)
    responsable = models.ForeignKey(
        "personas.Funcionario",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        db_column="responsable_id",
        related_name="actividades_responsable",
    )
    # Estado operativo (SQL v2.4)
    estado = models.CharField(max_length=10, choices=ESTADOS, default=INGRESADO)
    fecha_estado = models.DateTimeField(null=True, blank=True)
    usuario_cambio = models.ForeignKey(
        "personas.Usuario",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        db_column="usuario_cambio_id",
        related_name="actividades_cambiadas",
    )
    fecha_compromiso = models.DateField(null=True, blank=True)
    motivo_atraso = models.CharField(max_length=255, blank=True, default="")
    # Verificación (separada del estado operativo)
    estado_verificacion = models.CharField(
        max_length=12, choices=ESTADOS_VERIFICACION, default=VERIF_PENDIENTE
    )
    # Los calcula el servidor (reglas.calcular_ponderacion)
    pondera = models.BooleanField(default=True)
    motivo_no_pondera = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "actividad"
        ordering = ["-fecha", "-id_actividad"]
        verbose_name_plural = "actividades"
        indexes = [
            models.Index(fields=["funcionario", "fecha"], name="ix_actividad_func_fecha"),
            models.Index(fields=["estado_verificacion"], name="ix_actividad_verificacion"),
        ]

    def __str__(self):
        return self.codigo or f"Actividad {self.pk}"

    def clean(self):
        """Mismas reglas que el serializer (atenciones/reglas.py)."""
        from . import reglas

        self.verificar_no_aprobada()
        reglas.validar_actividad(
            funcionario=self.funcionario,
            item=self.item,
            fecha=self.fecha,
            area=self.area,
            territorio=self.territorio,
            vecino=self.vecino,
            tipo_atencion=self.tipo_atencion,
            sub_atencion=self.sub_atencion,
            excluir_pk=self.pk,
        )
        self.pondera, self.motivo_no_pondera = reglas.calcular_ponderacion(
            vecino=self.vecino,
            contacto=self.contacto,
            telefono=self.telefono,
            es_coordinacion_preparatoria=self.es_coordinacion_preparatoria,
        )

    def verificar_no_aprobada(self):
        """Una actividad aprobada en la base de datos no se modifica (ni por API ni por admin)."""
        if self.pk and not self._state.adding:
            actual = (
                type(self)
                .objects.filter(pk=self.pk)
                .values_list("estado_verificacion", flat=True)
                .first()
            )
            if actual == self.VERIF_APROBADA:
                raise ValidationError("La actividad está aprobada y no se puede modificar.")

    def save(self, *args, **kwargs):
        self.verificar_no_aprobada()
        if self.codigo:
            return super().save(*args, **kwargs)
        # Reintento: dos registros simultáneos pueden chocar al crear el contador del año.
        for intento in range(3):
            try:
                with transaction.atomic():
                    self.codigo = siguiente_codigo(self.funcionario.delegacion)
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.codigo = ""
                if intento == 2:
                    raise


def siguiente_codigo(delegacion):
    """<COD_DELEGACION>-<AAAA>-<5 dígitos>. Debe llamarse dentro de transaction.atomic()."""
    anio = timezone.localdate().year
    try:
        contador = ContadorCodigoActividad.objects.select_for_update().get(
            delegacion=delegacion, anio=anio
        )
    except ContadorCodigoActividad.DoesNotExist:
        # Si otro proceso lo crea a la vez, el UNIQUE lanza IntegrityError y save() reintenta.
        contador = ContadorCodigoActividad.objects.create(delegacion=delegacion, anio=anio)
    contador.ultimo += 1
    contador.save(update_fields=["ultimo"])
    return f"{delegacion.codigo}-{anio}-{contador.ultimo:05d}"


class HistorialVerificacion(models.Model):
    """Cada cambio de estado_verificacion de una actividad (quién, cuándo y por qué)."""

    id_historial = models.AutoField(primary_key=True)
    actividad = models.ForeignKey(
        Actividad,
        on_delete=models.PROTECT,
        db_column="id_actividad",
        related_name="historial_verificacion",
    )
    usuario = models.ForeignKey(
        "personas.Usuario",
        on_delete=models.PROTECT,
        db_column="id_usuario",
        related_name="verificaciones",
    )
    estado_anterior = models.CharField(max_length=12, choices=Actividad.ESTADOS_VERIFICACION)
    estado_nuevo = models.CharField(max_length=12, choices=Actividad.ESTADOS_VERIFICACION)
    observacion = models.TextField(blank=True, default="")
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "historial_verificacion"
        ordering = ["fecha", "id_historial"]
        verbose_name_plural = "historial de verificación"

    def __str__(self):
        return f"{self.actividad_id}: {self.estado_anterior} -> {self.estado_nuevo}"


def ruta_evidencia(instancia, nombre_archivo):
    """Nombre uuid (nunca el del usuario) en carpetas por año; sin URL pública."""
    extension = os.path.splitext(nombre_archivo)[1].lower()
    return f"evidencias/{timezone.localdate().year}/{uuid.uuid4().hex}{extension}"


def generar_codigo_verificador():
    """3 letras mayúsculas + 3 dígitos (ej. ORC711)."""
    letras = "".join(secrets.choice(string.ascii_uppercase) for _ in range(3))
    digitos = "".join(secrets.choice(string.digits) for _ in range(3))
    return letras + digitos


class Evidencia(models.Model):
    """Tabla `evidencia` (SQL v2.4 + delta v2.6). El archivo solo se descarga por la API."""

    PENDIENTE, REVISADO = "pendiente", "revisado"
    ESTADOS_REVISION = [(PENDIENTE, "Pendiente"), (REVISADO, "Revisado")]

    id_evidencia = models.AutoField(primary_key=True)
    actividad = models.ForeignKey(
        Actividad,
        on_delete=models.PROTECT,
        db_column="id_actividad",
        related_name="evidencias",
    )
    codigo_verificador = models.CharField(max_length=10, unique=True, editable=False)
    archivo = models.FileField(upload_to=ruta_evidencia, max_length=255)
    nombre_original = models.CharField(max_length=150, blank=True, default="")
    # Detectado en el servidor por la firma del archivo
    tipo_contenido = models.CharField(max_length=30, blank=True, default="")
    tamano = models.PositiveIntegerField(default=0)
    autor = models.ForeignKey(
        "personas.Usuario",
        on_delete=models.PROTECT,
        db_column="autor_usuario_id",
        related_name="evidencias",
    )
    fecha = models.DateTimeField(auto_now_add=True)
    tiene_imagen = models.BooleanField(default=False)
    estado_revision = models.CharField(max_length=9, choices=ESTADOS_REVISION, default=PENDIENTE)

    class Meta:
        db_table = "evidencia"
        ordering = ["fecha", "id_evidencia"]

    def __str__(self):
        return self.codigo_verificador

    def _verificar_actividad_no_aprobada(self):
        actual = Actividad.objects.filter(pk=self.actividad_id).values_list(
            "estado_verificacion", flat=True
        ).first()
        if actual == Actividad.VERIF_APROBADA:
            raise ValidationError("La actividad está aprobada: no se modifican sus evidencias.")

    def save(self, *args, **kwargs):
        self._verificar_actividad_no_aprobada()
        if self.codigo_verificador:
            return super().save(*args, **kwargs)
        for intento in range(5):  # el UNIQUE evita repetidos; si choca se prueba otro código
            try:
                with transaction.atomic():
                    self.codigo_verificador = generar_codigo_verificador()
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.codigo_verificador = ""
                if intento == 4:
                    raise

    def delete(self, *args, **kwargs):
        self._verificar_actividad_no_aprobada()
        archivo = self.archivo
        resultado = super().delete(*args, **kwargs)
        if archivo:
            archivo.delete(save=False)
        return resultado
