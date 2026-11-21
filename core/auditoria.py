import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models.fields.files import FieldFile
from django.forms.models import model_to_dict

from .models import Auditoria


def foto(instancia):
    """Copia JSON de un registro (para valor_anterior / valor_nuevo)."""
    if instancia is None:
        return None
    datos = model_to_dict(instancia)
    datos.pop("password", None)  # nunca guardar hashes de clave
    for campo, valor in datos.items():
        if isinstance(valor, FieldFile):  # archivos: solo la ruta, nunca el contenido
            datos[campo] = valor.name
    return json.loads(json.dumps(datos, cls=DjangoJSONEncoder))


def registrar(usuario, evento, instancia, anterior=None, nuevo=None, entidad=None):
    return Auditoria.objects.create(
        usuario=usuario,
        evento=evento,
        entidad=entidad or instancia._meta.db_table,
        entidad_id=instancia.pk,
        valor_anterior=anterior,
        valor_nuevo=nuevo,
    )
