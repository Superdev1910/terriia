"""Validación de archivos de evidencia (SCRUM-123): solo JPG, PNG o PDF de hasta 5 MB.

El tipo se decide por los primeros bytes del archivo (firma), no por la extensión ni por el
Content-Type que declara el cliente.
"""

from django.core.exceptions import ValidationError

MAX_BYTES = 5 * 1024 * 1024
FIRMAS = [
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"%PDF-", "application/pdf", ".pdf"),
]


def detectar_tipo(archivo):
    """Devuelve (tipo_mime, extension) según la firma, o None si no es JPG, PNG ni PDF."""
    posicion = archivo.tell() if hasattr(archivo, "tell") else 0
    archivo.seek(0)
    cabecera = archivo.read(16)
    archivo.seek(posicion)
    for firma, tipo, extension in FIRMAS:
        if cabecera.startswith(firma):
            return tipo, extension
    return None


def validar_archivo(archivo):
    """Lanza ValidationError si pesa más de 5 MB, está vacío o no es JPG, PNG ni PDF reales."""
    if archivo.size > MAX_BYTES:
        raise ValidationError("El archivo supera el máximo de 5 MB.")
    if archivo.size == 0:
        raise ValidationError("El archivo está vacío.")
    tipo = detectar_tipo(archivo)
    if tipo is None:
        raise ValidationError("Solo se aceptan archivos JPG, PNG o PDF.")
    return tipo
