from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from core.validators import normalizar_rut, rut_es_valido

from .models import Usuario, Funcionario
from organizacion.models import Delegacion


class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=False, style={"input_type": "password"}
    )
    rol_nombre = serializers.CharField(source="rol.nombre", read_only=True)

    class Meta:
        model = Usuario
        fields = [
            "id_usuario",
            "rut",
            "email",
            "first_name",
            "last_name",
            "rol",
            "rol_nombre",
            "funcionario",
            "delegacion",
            "estado",
            "password",
        ]

    def validate_rut(self, valor):
        if not rut_es_valido(valor):
            raise serializers.ValidationError("RUT inválido.")
        valor = normalizar_rut(valor)
        existe = Usuario.objects.filter(rut=valor)
        if self.instance:
            existe = existe.exclude(pk=self.instance.pk)
        if existe.exists():
            raise serializers.ValidationError("Ya existe un usuario con este RUT.")
        return valor

    def validate_email(self, valor):
        valor = valor.strip().lower()
        existe = Usuario.objects.filter(email=valor)
        if self.instance:
            existe = existe.exclude(pk=self.instance.pk)
        if existe.exists():
            raise serializers.ValidationError("Ya existe un usuario con este email.")
        return valor

    def validate_rol(self, rol):
        # Un rol desactivado no se asigna; quien ya lo tiene lo conserva y sigue entrando.
        cambio = not self.instance or self.instance.rol_id != rol.pk
        if cambio and not rol.activo:
            raise serializers.ValidationError("El rol que seleccionó no está activo.")
        return rol

    def validate_funcionario(self, funcionario):
        if funcionario is None:
            return funcionario
        cambio = not self.instance or self.instance.funcionario_id != funcionario.pk
        if cambio and funcionario.estado != Funcionario.ACTIVO:
            raise serializers.ValidationError("El funcionario que seleccionó no está activo.")
        return funcionario

    def validate_delegacion(self, delegacion):
        if delegacion is None:  # HU19: acceso global
            return delegacion
        cambio = not self.instance or self.instance.delegacion_id != delegacion.pk
        if cambio and delegacion.estado != Delegacion.ACTIVA:
            raise serializers.ValidationError("La delegación que seleccionó no está activa.")
        return delegacion

    def validate(self, datos):
        if self.instance is None and not datos.get("password"):
            raise serializers.ValidationError({"password": "La contraseña es obligatoria."})
        if datos.get("password"):
            validate_password(datos["password"])
        return datos

    def create(self, datos):
        password = datos.pop("password")
        usuario = Usuario(**datos)
        usuario.set_password(password)
        usuario.save()
        return usuario

    def update(self, instancia, datos):
        password = datos.pop("password", None)
        for campo, valor in datos.items():
            setattr(instancia, campo, valor)
        if password:
            instancia.set_password(password)
        instancia.save()
        return instancia


class FuncionarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Funcionario
        fields = ["id_funcionario", "identificador_inst", "nombre", "cargo", "delegacion", "estado"]

    def validate_identificador_inst(self, valor):
        valor = valor.strip()
        if not valor:
            raise serializers.ValidationError(
                "El identificador institucional es un campo obligatorio."
            )
        existe = Funcionario.objects.filter(identificador_inst__iexact=valor)
        if self.instance:
            existe = existe.exclude(pk=self.instance.pk)
        if existe.exists():
            raise serializers.ValidationError(
                "Ya existe un funcionario con este identificador institucional."
            )
        return valor

    def validate_nombre(self, valor):
        valor = valor.strip()
        if not valor:
            raise serializers.ValidationError("El nombre es un campo obligatorio.")
        return valor

    def validate_delegacion(self, delegacion):
        cambio = not self.instance or self.instance.delegacion_id != delegacion.pk
        if cambio and delegacion.estado != Delegacion.ACTIVA:
            raise serializers.ValidationError("La delegación que seleccionó no está activa.")
        return delegacion

    def validate_cargo(self, cargo):
        cambio = not self.instance or self.instance.cargo_id != cargo.pk
        if cambio and not cargo.vigente:
            raise serializers.ValidationError("El cargo que seleccionó no está vigente.")
        return cargo
