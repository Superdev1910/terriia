"""Pruebas del mantenedor cargo (SCRUM-13 HU17)."""

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria
from organizacion.models import Cargo, Delegacion

from .utiles import crear_admin, crear_funcionario

URL = "/api/cargos/"


class CargoMantenedorTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(crear_admin())
        self.delegacion = Delegacion.objects.create(codigo="D01", nombre="Centro")
        self.area = self.delegacion.areas.get(tipo="social")

    # 1. crear
    def test_crear_con_area(self):
        r = self.client.post(
            URL, {"nombre": "Asistente social", "area": self.area.pk}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertTrue(r.data["vigente"])
        self.assertFalse(r.data["transversal"])
        self.assertTrue(
            Auditoria.objects.filter(
                evento="crear", entidad="cargo", entidad_id=r.data["id_cargo"]
            ).exists()
        )

    def test_crear_transversal_sin_area(self):
        r = self.client.post(URL, {"nombre": "Secretaria", "area": None}, format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertIsNone(Cargo.objects.get(pk=r.data["id_cargo"]).area)
        self.assertTrue(r.data["transversal"])
        self.assertEqual(r.data["area_texto"], "Transversal")

    # 2. editar
    def test_editar_y_marcar_no_vigente(self):
        c = Cargo.objects.create(nombre="Conductor", area=self.area)
        r = self.client.patch(
            f"{URL}{c.pk}/", {"vigente": False, "descripcion": "Chofer"}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        c.refresh_from_db()
        self.assertFalse(c.vigente)
        self.assertEqual(c.descripcion, "Chofer")

    def test_pasar_de_area_a_transversal(self):
        c = Cargo.objects.create(nombre="Conductor", area=self.area)
        r = self.client.patch(f"{URL}{c.pk}/", {"area": None}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        c.refresh_from_db()
        self.assertIsNone(c.area)

    # 3. duplicado o inválido
    def test_nombre_duplicado_en_la_misma_area(self):
        Cargo.objects.create(nombre="Conductor", area=self.area)
        r = self.client.post(URL, {"nombre": "conductor", "area": self.area.pk})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "nombre")

    def test_nombre_duplicado_entre_transversales(self):
        Cargo.objects.create(nombre="Secretaria", area=None)
        r = self.client.post(URL, {"nombre": "Secretaria", "area": None}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "nombre")

    def test_mismo_nombre_en_otra_area_es_valido(self):
        Cargo.objects.create(nombre="Conductor", area=self.area)
        otra = self.delegacion.areas.get(tipo="territorial")
        r = self.client.post(URL, {"nombre": "Conductor", "area": otra.pk})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)

    def test_nombre_obligatorio_y_longitud(self):
        r = self.client.post(URL, {"area": self.area.pk})
        self.assertEqual((r.status_code, r.data["campo"]), (400, "nombre"))
        r = self.client.post(URL, {"nombre": "x" * 101, "area": self.area.pk})
        self.assertEqual((r.status_code, r.data["campo"]), (400, "nombre"))
        self.assertFalse(Cargo.objects.exists())

    def test_area_inexistente(self):
        r = self.client.post(URL, {"nombre": "Conductor", "area": 9999})
        self.assertEqual((r.status_code, r.data["campo"]), (400, "area"))

    # 4. desactivar = no vigente
    def test_desactivar_marca_no_vigente(self):
        c = Cargo.objects.create(nombre="Conductor", area=self.area)
        r = self.client.delete(f"{URL}{c.pk}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        c.refresh_from_db()
        self.assertFalse(c.vigente)
        self.assertTrue(Auditoria.objects.filter(evento="desactivar", entidad_id=c.pk).exists())

    # 5. acceso denegado
    def test_no_admin_denegado(self):
        self.client.force_authenticate(crear_funcionario())
        self.assertEqual(self.client.get(URL).status_code, status.HTTP_403_FORBIDDEN)

    # listado
    def test_filtros_y_busqueda(self):
        Cargo.objects.create(nombre="Conductor", area=self.area)
        Cargo.objects.create(nombre="Secretaria", area=None, vigente=False)
        self.assertEqual(self.client.get(URL, {"vigente": "false"}).data["count"], 1)
        self.assertEqual(self.client.get(URL, {"search": "COND"}).data["count"], 1)
        self.assertEqual(self.client.get(URL, {"area": self.area.pk}).data["count"], 1)
