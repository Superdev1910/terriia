from core.views import MantenedorViewSet

from .models import Usuario
from .serializers import UsuarioSerializer


class UsuarioViewSet(MantenedorViewSet):
    queryset = Usuario.objects.select_related("rol").all()
    serializer_class = UsuarioSerializer
    search_fields = ["email", "rut", "first_name", "last_name"]
    filterset_fields = ["estado", "rol"]
    campo_estado = "estado"
