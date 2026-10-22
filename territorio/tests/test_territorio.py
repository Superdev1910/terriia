from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria
from organizacion.models import Delegacion

from ..models import Territorio
from .utiles import crear_admin, crear_funcionario


class TerritorioTests(APITestCase):
    url = "/api/territorios/"

    def setUp(self):
        self.client.force_authenticate(crear_admin())
        self.delegacion = Delegacion.objects.create(codigo="D99", nombre="Centro de prueba")

    def datos(self, **extra):
        data = {"delegacion": self.delegacion.pk, "nombre": "Sector Norte", "es_formal": True}
        data.update(extra)
        return data

    def test_crear_editar_auditar_y_desactivar(self):
        response = self.client.post(self.url, self.datos())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        pk = response.data["id_territorio"]
        self.assertEqual(response.data["delegacion_codigo"], "D99")
        self.assertTrue(Auditoria.objects.filter(entidad="territorio", evento="crear", entidad_id=pk).exists())
        self.assertEqual(
            self.client.patch(f"{self.url}{pk}/", {"es_formal": False}).status_code,
            status.HTTP_200_OK,
        )
        self.assertTrue(
            Auditoria.objects.filter(
                entidad="territorio", evento="editar", entidad_id=pk
            ).exists()
        )
        self.assertEqual(self.client.delete(f"{self.url}{pk}/").status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Territorio.objects.get(pk=pk).activo)

    def test_rechaza_obligatorios_duplicados_y_delegacion_inactiva(self):
        self.assertEqual(self.client.post(self.url, {"delegacion": self.delegacion.pk}).status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.post(self.url, self.datos()).status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.post(self.url, self.datos(nombre="sector norte")).status_code, status.HTTP_400_BAD_REQUEST)
        self.delegacion.estado = Delegacion.INACTIVA
        self.delegacion.save(update_fields=["estado"])
        self.assertEqual(self.client.post(self.url, self.datos(nombre="Rural")).status_code, status.HTTP_400_BAD_REQUEST)

    def test_rechaza_delegacion_inexistente_o_inactiva(self):
        response = self.client.post(self.url, self.datos(delegacion=99999))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["campo"], "delegacion")
        self.delegacion.estado = Delegacion.INACTIVA
        self.delegacion.save(update_fields=["estado"])
        response = self.client.post(self.url, self.datos(nombre="Otro sector"))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["campo"], "delegacion")

    def test_busqueda_filtro_paginacion_relacion_y_rol(self):
        self.client.post(self.url, self.datos())
        self.assertEqual(self.client.get(self.url, {"search": "Norte"}).data["count"], 1)
        self.assertEqual(
            self.client.get(self.url, {"activo": "true", "es_formal": "true", "page_size": 1}).data[
                "count"
            ],
            1,
        )
        self.assertEqual(self.client.post(self.url, {"delegacion": 99999, "nombre": "Inválido"}).status_code, status.HTTP_400_BAD_REQUEST)
        self.client.force_authenticate(crear_funcionario())
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_sin_autenticacion_denegado(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)
