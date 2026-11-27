"""Consultas de reportes de atenciones con permisos globales restringidos."""

from io import BytesIO
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile

from django.http import HttpResponse
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import rol_de_usuario
from organizacion.models import Delegacion

from . import verificacion
from .models import Actividad

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
XLSX_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XLSX_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
XML_NS = "http://www.w3.org/XML/1998/namespace"


def _qname(namespace, local_name):
    return f"{{{namespace}}}{local_name}"


def _serializar_xml(root):
    return ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)


def _crear_xlsx(filas):
    hoja = ElementTree.Element(_qname(XLSX_MAIN_NS, "worksheet"))
    datos = ElementTree.SubElement(hoja, _qname(XLSX_MAIN_NS, "sheetData"))
    for numero_fila, valores in enumerate(filas, start=1):
        fila = ElementTree.SubElement(
            datos,
            _qname(XLSX_MAIN_NS, "row"),
            {"r": str(numero_fila)},
        )
        for numero_columna, valor in enumerate(valores):
            celda = ElementTree.SubElement(
                fila,
                _qname(XLSX_MAIN_NS, "c"),
                {"r": f"{chr(65 + numero_columna)}{numero_fila}", "t": "inlineStr"},
            )
            texto = ElementTree.SubElement(
                ElementTree.SubElement(celda, _qname(XLSX_MAIN_NS, "is")),
                _qname(XLSX_MAIN_NS, "t"),
            )
            texto.set(_qname(XML_NS, "space"), "preserve")
            texto.text = str(valor)

    libro = ElementTree.Element(_qname(XLSX_MAIN_NS, "workbook"))
    hojas = ElementTree.SubElement(libro, _qname(XLSX_MAIN_NS, "sheets"))
    ElementTree.SubElement(
        hojas,
        _qname(XLSX_MAIN_NS, "sheet"),
        {"name": "Solicitudes resueltas", "sheetId": "1", _qname(XLSX_REL_NS, "id"): "rId1"},
    )

    relaciones_raiz = ElementTree.Element(_qname(PACKAGE_REL_NS, "Relationships"))
    ElementTree.SubElement(
        relaciones_raiz,
        _qname(PACKAGE_REL_NS, "Relationship"),
        {
            "Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
            "Target": "xl/workbook.xml",
        },
    )

    relaciones_libro = ElementTree.Element(_qname(PACKAGE_REL_NS, "Relationships"))
    ElementTree.SubElement(
        relaciones_libro,
        _qname(PACKAGE_REL_NS, "Relationship"),
        {
            "Id": "rId1",
            "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet",
            "Target": "worksheets/sheet1.xml",
        },
    )

    tipos_contenido = ElementTree.Element(_qname(CONTENT_TYPES_NS, "Types"))
    ElementTree.SubElement(
        tipos_contenido,
        _qname(CONTENT_TYPES_NS, "Default"),
        {
            "Extension": "rels",
            "ContentType": "application/vnd.openxmlformats-package.relationships+xml",
        },
    )
    ElementTree.SubElement(
        tipos_contenido,
        _qname(CONTENT_TYPES_NS, "Default"),
        {"Extension": "xml", "ContentType": "application/xml"},
    )
    ElementTree.SubElement(
        tipos_contenido,
        _qname(CONTENT_TYPES_NS, "Override"),
        {
            "PartName": "/xl/workbook.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
        },
    )
    ElementTree.SubElement(
        tipos_contenido,
        _qname(CONTENT_TYPES_NS, "Override"),
        {
            "PartName": "/xl/worksheets/sheet1.xml",
            "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
        },
    )

    contenido = BytesIO()
    with ZipFile(contenido, "w", ZIP_DEFLATED) as archivo:
        archivo.writestr("[Content_Types].xml", _serializar_xml(tipos_contenido))
        archivo.writestr("_rels/.rels", _serializar_xml(relaciones_raiz))
        archivo.writestr("xl/workbook.xml", _serializar_xml(libro))
        archivo.writestr("xl/_rels/workbook.xml.rels", _serializar_xml(relaciones_libro))
        archivo.writestr("xl/worksheets/sheet1.xml", _serializar_xml(hoja))
    return contenido.getvalue()


class PuedeGenerarReporte(BasePermission):
    message = "Solo Administrador o Jefe de delegaciones puede generar este reporte."

    def has_permission(self, request, _view):
        return rol_de_usuario(request.user) in verificacion.ROLES_GLOBALES


class FiltrosReporteSerializer(serializers.Serializer):
    delegacion = serializers.PrimaryKeyRelatedField(queryset=Delegacion.objects.all())
    desde = serializers.DateField()
    hasta = serializers.DateField()

    def validate(self, attrs):
        if attrs["desde"] > attrs["hasta"]:
            raise serializers.ValidationError(
                {"hasta": "La fecha final debe ser igual o posterior a la fecha inicial."}
            )
        return attrs


class SolicitudResueltaSerializer(serializers.Serializer):
    codigo = serializers.CharField()
    tipo_registro = serializers.CharField(source="get_tipo_registro_display")
    delegacion_codigo = serializers.CharField(source="funcionario.delegacion.codigo")
    delegacion_nombre = serializers.CharField(source="funcionario.delegacion.nombre")
    item = serializers.CharField(source="item.nombre")
    fecha_resolucion = serializers.DateTimeField(source="fecha_estado")


class ReporteDelegacionesView(APIView):
    permission_classes = [IsAuthenticated, PuedeGenerarReporte]

    def get(self, _request):
        delegaciones = Delegacion.objects.order_by("codigo").values(
            "id_delegacion", "codigo", "nombre"
        )
        return Response(
            {
                "results": [
                    {
                        "id": fila["id_delegacion"],
                        "codigo": fila["codigo"],
                        "nombre": fila["nombre"],
                    }
                    for fila in delegaciones
                ]
            }
        )


class ReporteSolicitudesResueltasView(APIView):
    permission_classes = [IsAuthenticated, PuedeGenerarReporte]

    def get(self, request):
        filtros = FiltrosReporteSerializer(data=request.query_params)
        filtros.is_valid(raise_exception=True)
        delegacion = filtros.validated_data["delegacion"]
        desde = filtros.validated_data["desde"]
        hasta = filtros.validated_data["hasta"]

        base = Actividad.objects.filter(
            funcionario__delegacion=delegacion,
            estado=Actividad.REALIZADO,
        )
        sin_fecha_resolucion = base.filter(fecha_estado__isnull=True).count()
        solicitudes = (
            base.filter(fecha_estado__date__range=(desde, hasta))
            .select_related("funcionario__delegacion", "item")
            .order_by("fecha_estado", "codigo")
        )
        resultados = SolicitudResueltaSerializer(solicitudes, many=True).data
        filas = [
            ["Reporte histórico de solicitudes resueltas"],
            ["Delegación", f"{delegacion.codigo} · {delegacion.nombre}"],
            ["Período", desde.isoformat(), hasta.isoformat()],
            ["Realizado sin fecha de resolución (no incluidos)", sin_fecha_resolucion],
            [],
            [
                "Código",
                "Tipo",
                "Delegación",
                "Ítem",
                "Fecha de resolución",
            ],
        ]
        filas.extend(
            [
                [
                    solicitud["codigo"],
                    solicitud["tipo_registro"],
                    f'{solicitud["delegacion_codigo"]} · {solicitud["delegacion_nombre"]}',
                    solicitud["item"],
                    solicitud["fecha_resolucion"],
                ]
                for solicitud in resultados
            ]
        )
        codigo_archivo = slugify(delegacion.codigo) or str(delegacion.pk)
        nombre_archivo = (
            f"solicitudes-resueltas-{codigo_archivo}-{desde.isoformat()}-{hasta.isoformat()}.xlsx"
        )
        respuesta = HttpResponse(_crear_xlsx(filas), content_type=XLSX_CONTENT_TYPE)
        respuesta["Content-Disposition"] = f'attachment; filename="{nombre_archivo}"'
        respuesta["X-Total-Registros"] = str(len(resultados))
        respuesta["X-Sin-Fecha-Resolucion"] = str(sin_fecha_resolucion)
        return respuesta
