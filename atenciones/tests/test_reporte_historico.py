from io import BytesIO
from datetime import datetime
from zipfile import ZipFile
from xml.etree import ElementTree

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from atenciones.models import Actividad
from core.models import Rol
from territorio.pantallas import menu_para_usuario

from .utiles_seguimiento import RAPIDO, EscenarioSolicitudesMixin

XLSX_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def filas_xlsx(respuesta):
    with ZipFile(BytesIO(respuesta.content)) as archivo:
        if archivo.testzip():
            raise AssertionError("El archivo Excel contiene una entrada dañada.")
        raiz = ElementTree.fromstring(archivo.read("xl/worksheets/sheet1.xml"))
    filas = []
    for fila in raiz.findall(".//x:row", XLSX_NS):
        valores = []
        for celda in fila.findall("x:c", XLSX_NS):
            texto = celda.find("x:is/x:t", XLSX_NS)
            valores.append(texto.text if texto is not None else "")
        filas.append(valores)
    return filas


@RAPIDO
class ReporteHistoricoApiTests(EscenarioSolicitudesMixin, APITestCase):
    def setUp(self):
        self.preparar_escenario()
        self.jefe = self.crear_usuario("jefe@terriia.cl", 88888888, Rol.JEFE_DELEGACIONES)
        self.url_reporte = reverse("reporte_solicitudes_resueltas")
        self.url_delegaciones = reverse("reporte_solicitudes_resueltas_delegaciones")

        self.en_periodo = self.crear_actividad(
            estado=Actividad.REALIZADO,
            fecha_estado=self.fecha("2026-03-10"),
            tipo_registro=Actividad.GESTION_SOCIAL,
        )
        self.fuera_periodo = self.crear_actividad(
            estado=Actividad.REALIZADO,
            fecha_estado=self.fecha("2026-03-20"),
        )
        self.otra_delegacion = self.crear_actividad(
            autor=self.pedro,
            estado=Actividad.REALIZADO,
            fecha_estado=self.fecha("2026-03-10"),
        )
        self.no_resuelta = self.crear_actividad(
            estado=Actividad.EN_PROCESO,
            fecha_estado=self.fecha("2026-03-10"),
        )
        self.sin_fecha = self.crear_actividad(
            estado=Actividad.REALIZADO,
            fecha_estado=None,
        )

    @staticmethod
    def fecha(valor):
        return timezone.make_aware(datetime.fromisoformat(f"{valor}T12:00:00"))

    def consultar(self, **parametros):
        return self.client.get(self.url_reporte, parametros)

    def test_jefe_recibe_solo_resueltas_de_la_delegacion_y_periodo(self):
        self.client.force_authenticate(self.jefe)

        respuesta = self.consultar(
            delegacion=self.centro.pk,
            desde="2026-03-01",
            hasta="2026-03-15",
        )

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK, respuesta.content[:100])
        self.assertEqual(
            respuesta["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertEqual(respuesta["X-Total-Registros"], "1")
        self.assertEqual(respuesta["X-Sin-Fecha-Resolucion"], "1")
        self.assertIn(
            f'filename="solicitudes-resueltas-cen-2026-03-01-2026-03-15.xlsx"',
            respuesta["Content-Disposition"],
        )
        filas = filas_xlsx(respuesta)
        celdas = [valor for fila in filas for valor in fila]
        self.assertIn(self.en_periodo.codigo, celdas)
        self.assertIn("Gestión social", celdas)
        self.assertIn("CEN · Centro", celdas)
        self.assertNotIn(self.fuera_periodo.codigo, celdas)
        self.assertNotIn(self.otra_delegacion.codigo, celdas)
        self.assertNotIn(self.no_resuelta.codigo, celdas)
        self.assertNotIn(self.sin_fecha.codigo, celdas)
        for dato_personal in ("Ana Pérez", "Juana", "+56911112222"):
            self.assertNotIn(dato_personal, celdas)

    def test_xlsx_es_un_archivo_openxml_valido(self):
        self.client.force_authenticate(self.admin)

        respuesta = self.consultar(
            delegacion=self.centro.pk,
            desde="2026-03-01",
            hasta="2026-03-15",
        )

        with ZipFile(BytesIO(respuesta.content)) as archivo:
            self.assertIsNone(archivo.testzip())
            for parte in (
                "[Content_Types].xml",
                "_rels/.rels",
                "xl/workbook.xml",
                "xl/_rels/workbook.xml.rels",
                "xl/worksheets/sheet1.xml",
            ):
                ElementTree.fromstring(archivo.read(parte))
        self.assertIn("Código", [valor for fila in filas_xlsx(respuesta) for valor in fila])

    def test_reporte_sin_resultados_responde_sin_filas(self):
        self.client.force_authenticate(self.admin)

        respuesta = self.consultar(
            delegacion=self.centro.pk,
            desde="2020-01-01",
            hasta="2020-01-31",
        )

        self.assertEqual(respuesta.status_code, status.HTTP_200_OK)
        self.assertEqual(respuesta["X-Total-Registros"], "0")
        self.assertEqual(respuesta["X-Sin-Fecha-Resolucion"], "1")
        self.assertNotIn(
            self.en_periodo.codigo, [v for fila in filas_xlsx(respuesta) for v in fila]
        )

    def test_rechaza_filtros_invalidos(self):
        self.client.force_authenticate(self.admin)
        casos = [
            ({"delegacion": self.centro.pk, "desde": "fecha", "hasta": "2026-03-15"}, "desde"),
            (
                {"delegacion": self.centro.pk, "desde": "2026-03-16", "hasta": "2026-03-15"},
                "hasta",
            ),
            (
                {"delegacion": 999999, "desde": "2026-03-01", "hasta": "2026-03-15"},
                "delegacion",
            ),
        ]
        for parametros, campo in casos:
            with self.subTest(parametros=parametros):
                respuesta = self.consultar(**parametros)
                self.assertEqual(respuesta.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertEqual(respuesta.data["campo"], campo)

    def test_solo_administrador_y_jefe_pueden_consultar_opciones_y_reporte(self):
        parametros = {
            "delegacion": self.centro.pk,
            "desde": "2026-03-01",
            "hasta": "2026-03-15",
        }
        for usuario in (self.admin, self.jefe):
            self.client.force_authenticate(usuario)
            self.assertEqual(self.client.get(self.url_delegaciones).status_code, 200)
            self.assertEqual(self.consultar(**parametros).status_code, 200)

        for usuario in (self.delegado, self.alcaldesa, self.usuario_ana):
            self.client.force_authenticate(usuario)
            self.assertEqual(self.client.get(self.url_delegaciones).status_code, 403)
            self.assertEqual(self.consultar(**parametros).status_code, 403)

    def test_opciones_incluyen_delegaciones_activas_e_inactivas(self):
        self.norte.estado = self.norte.INACTIVA
        self.norte.save(update_fields=["estado"])
        self.client.force_authenticate(self.jefe)

        respuesta = self.client.get(self.url_delegaciones)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(
            {fila["id"] for fila in respuesta.data["results"]},
            {self.centro.pk, self.norte.pk},
        )


@RAPIDO
class ReporteHistoricoPantallaTests(EscenarioSolicitudesMixin, TestCase):
    def setUp(self):
        self.preparar_escenario()
        self.jefe = self.crear_usuario("jefe@terriia.cl", 88888888, Rol.JEFE_DELEGACIONES)
        self.url_pantalla = reverse("atenciones_reporte_solicitudes_resueltas")

    def test_solo_administrador_y_jefe_ven_la_pantalla(self):
        for usuario in (self.admin, self.jefe):
            self.client.force_login(usuario)
            respuesta = self.client.get(self.url_pantalla)
            self.assertEqual(respuesta.status_code, 200)
            self.assertTemplateUsed(respuesta, "atenciones/reporte_historico.html")

        for usuario in (self.delegado, self.alcaldesa, self.usuario_ana):
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(self.url_pantalla).status_code, 403)

    def test_pantalla_presenta_filtros_y_descarga_excel(self):
        self.client.force_login(self.jefe)

        respuesta = self.client.get(self.url_pantalla)

        self.assertContains(respuesta, 'id="filtroDelegacion"')
        self.assertContains(respuesta, 'id="filtroDesde"')
        self.assertContains(respuesta, 'id="filtroHasta"')
        self.assertContains(respuesta, "Descargar Excel")
        self.assertContains(respuesta, "atenciones/css/reporte_historico.css")
        self.assertContains(respuesta, "terriia.css")
        self.assertNotContains(respuesta, "cdn.jsdelivr.net/npm/xlsx")
        self.assertContains(respuesta, "atenciones/js/reporte_historico.js")

    def test_menu_del_jefe_muestra_el_reporte_y_no_lo_expone_a_roles_no_autorizados(self):
        def nombres_menu(usuario):
            return {item[0] for _, paginas in menu_para_usuario(usuario) for item in paginas}

        self.assertIn("atenciones_reporte_solicitudes_resueltas", nombres_menu(self.jefe))
        self.assertNotIn("atenciones_reporte_solicitudes_resueltas", nombres_menu(self.delegado))
