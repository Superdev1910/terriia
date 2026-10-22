from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria
from ..models import Vecino

from .utiles import crear_admin, crear_funcionario, rut_valido


class VecinoTests(APITestCase):
    url = "/api/vecinos/"

    def setUp(self):
        self.client.force_authenticate(crear_admin())

    def datos(self, **extra):
        data = {
            "rut": rut_valido(15667777),
            "nombres": "Ana",
            "apellidos": "Pérez",
            "telefono": "+56912345678",
            "direccion": "Pasaje 1",
        }
        data.update(extra)
        return data

    def test_crear_editar_auditar_y_desactivar(self):
        response = self.client.post(self.url, self.datos())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        pk = response.data["id_vecino"]
        self.assertTrue(Auditoria.objects.filter(entidad="vecino", evento="crear", entidad_id=pk).exists())
        response = self.client.patch(f"{self.url}{pk}/", {"direccion": "Pasaje 2"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            Auditoria.objects.filter(entidad="vecino", evento="editar", entidad_id=pk).exists()
        )
        response = self.client.delete(f"{self.url}{pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(Auditoria.objects.filter(entidad="vecino", evento="desactivar", entidad_id=pk).exists())

    def test_rechaza_obligatorios_rut_invalido_y_duplicado(self):
        self.assertEqual(self.client.post(self.url, {"rut": "1-K"}).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.post(self.url, self.datos(rut="12.345.678-0")).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.post(self.url, self.datos()).status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            self.client.post(self.url, self.datos()).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_control_acceso_busqueda_filtro_y_paginacion(self):
        for i in range(3):
            self.client.post(self.url, self.datos(rut=rut_valido(15000000 + i), nombres=f"Nombre{i}"))
        self.assertEqual(self.client.get(self.url, {"search": "Nombre1"}).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"estado": "activo", "page_size": 2}).data["count"], 3)
        self.client.force_authenticate(crear_funcionario())
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_sin_autenticacion_denegado(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_desactivacion_conserva_el_registro(self):
        response = self.client.post(self.url, self.datos())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        pk = response.data["id_vecino"]

        response = self.client.delete(f"{self.url}{pk}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        vecino = Vecino.objects.get(pk=pk)
        self.assertEqual(vecino.estado, Vecino.INACTIVO)
