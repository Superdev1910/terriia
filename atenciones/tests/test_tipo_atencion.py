import importlib

from django.apps import apps
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria

from ..models import SubAtencion, TipoAtencion
from .utiles import crear_admin, crear_funcionario

# El nombre del módulo empieza con un número, así que se importa con importlib.
semilla = importlib.import_module("atenciones.migrations.0002_semilla_social")


class TipoAtencionTests(APITestCase):
    url = "/api/tipos-atencion/"

    def setUp(self):
        self.client.force_authenticate(crear_admin())

    def datos(self, **extra):
        # DISERCO para no mezclarse con la semilla del área Social.
        data = {"area": "DISERCO", "nombre": "Mantención de luminarias"}
        data.update(extra)
        return data

    def crear(self, **extra):
        response = self.client.post(self.url, self.datos(**extra), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data["id_tipo_atencion"]

    def test_crear(self):
        response = self.client.post(
            self.url, self.datos(nombre="  Poda de árboles "), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["nombre"], "Poda de árboles")
        self.assertEqual(response.data["area_nombre"], "DISERCO")
        self.assertTrue(response.data["activo"])
        pk = response.data["id_tipo_atencion"]
        self.assertTrue(
            Auditoria.objects.filter(
                entidad="tipo_atencion", evento="crear", entidad_id=pk
            ).exists()
        )

    def test_editar(self):
        pk = self.crear()
        response = self.client.patch(
            f"{self.url}{pk}/", {"nombre": "Recambio de luminarias"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(TipoAtencion.objects.get(pk=pk).nombre, "Recambio de luminarias")
        self.assertTrue(
            Auditoria.objects.filter(
                entidad="tipo_atencion", evento="editar", entidad_id=pk
            ).exists()
        )

    def test_rechaza_duplicado_e_invalidos(self):
        self.crear()
        response = self.client.post(self.url, self.datos(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["campo"], "nombre")
        for invalido in ({"area": "DISERCO", "nombre": "   "}, {"area": "Otra", "nombre": "X"}, {}):
            self.assertEqual(
                self.client.post(self.url, invalido, format="json").status_code,
                status.HTTP_400_BAD_REQUEST,
                invalido,
            )

    def test_rechaza_duplicado_con_otras_mayusculas(self):
        self.crear()
        response = self.client.post(
            self.url, self.datos(nombre="MANTENCIÓN DE LUMINARIAS"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["campo"], "nombre")
        # Al editar otro tipo tampoco se puede llegar al mismo nombre.
        otro = self.crear(nombre="Poda")
        response = self.client.patch(
            f"{self.url}{otro}/", {"nombre": "mantención de luminarias"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mismo_nombre_en_otra_area_se_permite(self):
        self.crear()
        self.crear(area="Seguridad")

    def test_desactivar(self):
        pk = self.crear()
        self.assertEqual(
            self.client.delete(f"{self.url}{pk}/").status_code, status.HTTP_204_NO_CONTENT
        )
        self.assertFalse(TipoAtencion.objects.get(pk=pk).activo)  # no se borra
        self.assertTrue(
            Auditoria.objects.filter(
                entidad="tipo_atencion", evento="desactivar", entidad_id=pk
            ).exists()
        )

    def test_acceso_denegado(self):
        self.client.force_authenticate(crear_funcionario())
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.post(self.url, self.datos(), format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_busqueda_filtros_y_paginacion(self):
        self.crear()
        inactivo = self.crear(nombre="Retiro de escombros")
        self.client.delete(f"{self.url}{inactivo}/")
        self.assertEqual(self.client.get(self.url, {"area": "DISERCO"}).data["count"], 2)
        self.assertEqual(
            self.client.get(self.url, {"area": "DISERCO", "activo": "false"}).data["count"], 1
        )
        self.assertEqual(self.client.get(self.url, {"search": "luminarias"}).data["count"], 1)
        self.assertEqual(len(self.client.get(self.url, {"page_size": 1}).data["results"]), 1)

    def test_semilla_social_queda_cargada(self):
        sociales = TipoAtencion.objects.filter(area="Social", activo=True)
        self.assertCountEqual(
            sociales.values_list("nombre", flat=True),
            ["Informe social", "Gestión de subsidio", "Derivación", "Otras gestiones"],
        )
        self.assertTrue(
            SubAtencion.objects.filter(
                tipo_atencion__area="Social",
                tipo_atencion__nombre="Otras gestiones",
                nombre="Orientación social",
                activo=True,
            ).exists()
        )
        self.assertEqual(self.client.get(self.url, {"area": "Social"}).data["count"], 4)

    def test_semilla_es_reversible(self):
        semilla.quitar_semilla(apps, None)
        self.assertFalse(TipoAtencion.objects.filter(area="Social").exists())
        self.assertFalse(SubAtencion.objects.exists())
        semilla.cargar_semilla(apps, None)
        self.assertEqual(TipoAtencion.objects.filter(area="Social").count(), 4)
        self.assertEqual(SubAtencion.objects.count(), 1)
