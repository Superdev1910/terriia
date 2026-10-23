from rest_framework import serializers

from .models import Rol


class RolSerializer(serializers.ModelSerializer):
    activo = serializers.BooleanField(default=True, required=False)
    es_del_sistema = serializers.BooleanField(read_only=True)
    cantidad_usuarios = serializers.SerializerMethodField()

    class Meta:
        model = Rol
        fields = [
            "id_rol",
            "nombre",
            "descripcion",
            "activo",
            "es_del_sistema",
            "cantidad_usuarios",
        ]
        extra_kwargs = {"nombre": {"validators": []}}  # el duplicado se revisa abajo

    def get_cantidad_usuarios(self, rol):
        # El listado la trae con annotate (una sola consulta); al crear o editar se cuenta aquí.
        if hasattr(rol, "cantidad_usuarios"):
            return rol.cantidad_usuarios
        return rol.usuario_set.count()

    def validate_nombre(self, valor):
        valor = " ".join(valor.split())
        if not valor:
            raise serializers.ValidationError("El nombre es un campo obligatorio.")
        if self.instance and self.instance.es_del_sistema and valor != self.instance.nombre:
            raise serializers.ValidationError(
                f"«{self.instance.nombre}» es un rol del sistema y no se puede renombrar."
            )
        existe = Rol.objects.filter(nombre__iexact=valor)
        if self.instance:
            existe = existe.exclude(pk=self.instance.pk)
        if existe.exists():
            raise serializers.ValidationError("Ya existe un rol con este nombre.")
        return valor

    def validate_descripcion(self, valor):
        return valor.strip()

    def validate_activo(self, valor):
        if self.instance and self.instance.es_del_sistema and not valor:
            raise serializers.ValidationError(
                f"«{self.instance.nombre}» es un rol del sistema y no se puede desactivar."
            )
        return valor
