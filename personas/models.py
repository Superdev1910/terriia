# Patricio: usuario (SCRUM-14 HU18, SCRUM-15 HU19) · Fernando: funcionario (agregar aquí abajo).
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from core.models import Rol
from core.validators import normalizar_rut, validar_rut


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def _crear(self, email, rut, password, **extra):
        if not email:
            raise ValueError("El email es obligatorio.")
        if not rut:
            raise ValueError("El RUT es obligatorio.")
        email = self.normalize_email(email).lower()
        if "rol" not in extra and "rol_id" not in extra:
            extra["rol"] = Rol.objects.get(nombre=Rol.FUNCIONARIO)
        user = self.model(email=email, rut=normalizar_rut(rut), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, rut, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._crear(email, rut, password, **extra)

    def create_superuser(self, email, rut, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("rol", Rol.objects.get(nombre=Rol.ADMINISTRADOR))
        return self._crear(email, rut, password, **extra)


class Usuario(AbstractUser):
    """
    Tabla `usuario` del modelo físico v2.3. Login por email.
    HU18 (gestión de usuarios y roles) / HU19 (aislamiento por delegación).
    """

    ACTIVO, INACTIVO = "activo", "inactivo"
    ESTADOS = [(ACTIVO, "Activo"), (INACTIVO, "Inactivo")]

    username = None  # se usa email
    id_usuario = models.AutoField(primary_key=True)
    rol = models.ForeignKey(Rol, on_delete=models.PROTECT, db_column="id_rol")
    rut = models.CharField(max_length=12, unique=True, validators=[validar_rut])
    email = models.EmailField(max_length=150, unique=True)
    password = models.CharField(max_length=255, db_column="password_hash")
    estado = models.CharField(max_length=8, choices=ESTADOS, default=ACTIVO)

    # Pendientes: se agregan con una migración nueva cuando existan sus modelos.
    # funcionario = models.ForeignKey("personas.Funcionario", null=True, blank=True,
    #                                 on_delete=models.PROTECT, db_column="id_funcionario")
    # delegacion = models.ForeignKey("organizacion.Delegacion", null=True, blank=True,
    #                                on_delete=models.PROTECT, db_column="id_delegacion")  # NULL = acceso global

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["rut"]

    objects = UsuarioManager()

    class Meta:
        db_table = "usuario"
        ordering = ["email"]

    @property
    def is_active(self):
        """Django bloquea el login si es False. Se controla con `estado`."""
        return self.estado == self.ACTIVO

    def save(self, *args, **kwargs):
        self.rut = normalizar_rut(self.rut)
        self.email = (self.email or "").lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} ({self.rol})"


class Funcionario(models.Model):
    """
    tabla 'funcionario' del modelo físico de la BBDD
    """

    ACTIVO, INACTIVO = "activo", "inactivo"
    ESTADOS = [(ACTIVO, "Activo"), (INACTIVO, "Inactivo")]

    id_funcionario = models.AutoField(primary_key=True)
    identificador_inst = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=150)
    cargo = models.ForeignKey("organizacion.Cargo", on_delete=models.PROTECT, db_column="id_cargo")
    delegacion = models.ForeignKey(
        "organizacion.Delegacion", on_delete=models.PROTECT, db_column="id_delegacion"
    )
    estado = models.CharField(max_length=8, choices=ESTADOS, default=ACTIVO)

    class Meta:
        db_table = "funcionario"
        ordering = ["identificador_inst"]

    def save(self, *args, **kwargs):
        self.identificador_inst = (self.identificador_inst or "").strip()
        self.nombre = (self.nombre or "").strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.identificador_inst
