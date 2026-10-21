"""Formato único de error para toda la API: {"error": "mensaje", "campo": "nombre"}."""

from rest_framework.views import exception_handler


def _primer_mensaje(detalle):
    if isinstance(detalle, list):
        return _primer_mensaje(detalle[0]) if detalle else ""
    if isinstance(detalle, dict):
        return _primer_mensaje(next(iter(detalle.values()), ""))
    return str(detalle)


def manejador_errores(exc, context):
    respuesta = exception_handler(exc, context)
    if respuesta is None:
        return None

    datos = respuesta.data
    campo = None
    if isinstance(datos, dict) and "detail" not in datos:
        campo = next(iter(datos), None)
        mensaje = _primer_mensaje(datos[campo]) if campo else ""
        if campo == "non_field_errors":
            campo = None
    else:
        mensaje = _primer_mensaje(datos.get("detail", datos) if isinstance(datos, dict) else datos)

    respuesta.data = {"error": mensaje, "campo": campo}
    return respuesta
