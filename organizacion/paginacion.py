"""Paginación de los mantenedores de organización.

Igual que la de DRF (20 por página) pero permite elegir 10, 20 o 50 filas desde la pantalla
y pedir hasta 100 de una vez, que usa la exportación a Excel para hacer menos solicitudes.
"""

from rest_framework.pagination import PageNumberPagination


class PaginacionMantenedor(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
