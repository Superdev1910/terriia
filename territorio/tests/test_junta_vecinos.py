from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria
from organizacion.models import Delegacion

from ..models import JuntaVecinos, Territorio
from .utiles import crear_admin, crear_funcionario


class JuntaVecinosTests(APITestCase):
    url = "/api/juntas-vecinos/"

    def setUp(self):
        self.client.force_authenticate(crear_admin())
        delegacion = Delegacion.objects.create(codigo="D98", nombre="Norte de prueba")
        self.territorio = Territorio.objects.create(delegacion=delegacion, nombre="Barrio Uno")

    def datos(self, **extra):
        data = {
            "territorio": self.territorio.pk,
            "numero_registro": "JV-001",
            "nombre": "Junta Barrio Uno",
            "presidente": "Ana Pérez",
            "telefono": "+56912345678",
            "email": "junta@example.com",
        }
        data.update(extra)
        return data

    def test_crear_editar_auditar_y_desactivar(self):
        response = self.client.post(self.url, self.datos())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        pk = response.data["id_junta_vecinos"]
        self.assertTrue(
            Auditoria.objects.filter(
                entidad="junta_vecinos", evento="crear", entidad_id=pk
            ).exists()
        )
        self.assertEqual(
            self.client.patch(f"{self.url}{pk}/", {"nombre": "Junta actualizada"}).status_code,
            status.HTTP_200_OK,
        )
        self.assertTrue(
            Auditoria.objects.filter(
                entidad="junta_vecinos", evento="editar", entidad_id=pk
            ).exists()
        )
        self.assertEqual(
            self.client.delete(f"{self.url}{pk}/").status_code, status.HTTP_204_NO_CONTENT
        )
        self.assertFalse(JuntaVecinos.objects.get(pk=pk).activa)

    def test_rechaza_obligatorios_duplicados_y_territorio_inactivo(self):
        self.assertEqual(
            self.client.post(self.url, {"territorio": self.territorio.pk}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(self.url, self.datos()).status_code, status.HTTP_201_CREATED
        )
        self.assertEqual(
            self.client.post(self.url, self.datos(nombre="Otra junta")).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.territorio.activo = False
        self.territorio.save(update_fields=["activo"])
        self.assertEqual(
            self.client.post(self.url, self.datos(numero_registro="JV-002")).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_rechaza_territorio_inexistente_y_negativo(self):
        for territorio in (99999, -6):
            response = self.client.post(
                self.url, self.datos(territorio=territorio, numero_registro=f"JV-{territorio}")
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data["campo"], "territorio")

    def test_busqueda_filtro_paginacion_relacion_y_rol(self):
        self.client.post(self.url, self.datos())
        self.assertEqual(self.client.get(self.url, {"search": "JV-001"}).data["count"], 1)
        self.assertEqual(
            self.client.get(
                self.url, {"territorio": self.territorio.pk, "activa": "true", "page_size": 1}
            ).data["count"],
            1,
        )
        self.assertEqual(
            self.client.post(
                self.url, {"territorio": 99999, "numero_registro": "JV-002", "nombre": "Inválida"}
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.client.force_authenticate(crear_funcionario())
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_sin_autenticacion_denegado(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)
