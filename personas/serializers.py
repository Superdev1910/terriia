from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from core.validators import normalizar_rut, rut_es_valido

from .models import Usuario, Funcionario
from organizacion.models import Delegacion


class UsuarioSerializer(serializers.ModelSerializer):
    # La clave no se recorta: el login la compara tal cual se escribió.
    password = serializers.CharField(
        write_only=True, required=False, trim_whitespace=False, style={"input_type": "password"}
    )
    rol_nombre = serializers.CharField(source="rol.nombre", read_only=True)
    funcionario_nombre = serializers.CharField(
        source="funcionario.nombre", read_only=True, allow_null=True
    )
    delegacion_codigo = serializers.CharField(
        source="delegacion.codigo", read_only=True, allow_null=True
    )
    delegacion_nombre = serializers.CharField(
        source="delegacion.nombre", read_only=True, allow_null=True
    )

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
            "funcionario_nombre",
            "delegacion",
            "delegacion_codigo",
            "delegacion_nombre",
            "estado",
            "password",
        ]
        # RUT y email se validan a mano (ya normalizados) con mensajes en español.
        extra_kwargs = {"rut": {"validators": []}, "email": {"validators": []}}

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
        clave = datos.get("password")
        if self.instance is None and not clave:
            raise serializers.ValidationError({"password": "La contraseña es obligatoria."})
        if clave:
            # Reglas de clave de settings; con los datos nuevos del usuario para rechazar
            # claves parecidas a su email o a su nombre.
            usuario = Usuario(
                email=datos.get("email", getattr(self.instance, "email", "")),
                first_name=datos.get("first_name", getattr(self.instance, "first_name", "")),
                last_name=datos.get("last_name", getattr(self.instance, "last_name", "")),
            )
            try:
                validate_password(clave, usuario)
            except DjangoValidationError as error:
                raise serializers.ValidationError({"password": list(error.messages)})
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
    cargo_nombre = serializers.CharField(source="cargo.nombre", read_only=True)
    delegacion_codigo = serializers.CharField(source="delegacion.codigo", read_only=True)
    delegacion_nombre = serializers.CharField(source="delegacion.nombre", read_only=True)

    class Meta:
        model = Funcionario
        fields = [
            "id_funcionario",
            "identificador_inst",
            "nombre",
            "cargo",
            "cargo_nombre",
            "delegacion",
            "delegacion_codigo",
            "delegacion_nombre",
            "estado",
        ]
        # La unicidad se valida a mano (sin distinguir mayúsculas) con mensajes en español.
        extra_kwargs = {"identificador_inst": {"validators": []}}

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
