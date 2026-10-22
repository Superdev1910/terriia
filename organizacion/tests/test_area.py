"""Pruebas del mantenedor area (SCRUM-13 HU17)."""

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria
from organizacion.models import Area, Delegacion

from .utiles import crear_admin, crear_funcionario

URL = "/api/areas/"


class AreaMantenedorTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(crear_admin())
        self.delegacion = Delegacion.objects.create(codigo="D01", nombre="Centro")
        # La delegación nace con 4 áreas; se quitan para probar el alta manual.
        self.delegacion.areas.all().delete()

    def datos(self, **extra):
        base = {
            "delegacion": self.delegacion.pk,
            "nombre": Area.SOCIAL,
            "prioridad": 1,
        }
        base.update(extra)
        return base

    # 1. crear
    def test_crear(self):
        r = self.client.post(URL, self.datos())
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["delegacion_codigo"], "D01")
        self.assertEqual(r.data["nombre_texto"], "Social")
        self.assertTrue(
            Auditoria.objects.filter(
                evento="crear", entidad="area", entidad_id=r.data["id_area"]
            ).exists()
        )

    # 2. editar
    def test_editar_prioridad(self):
        a = Area.objects.create(delegacion=self.delegacion, nombre="Social", prioridad=1)
        r = self.client.patch(f"{URL}{a.pk}/", {"prioridad": 3})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        a.refresh_from_db()
        self.assertEqual(a.prioridad, 3)

    def test_editar_sin_chocar_consigo_misma(self):
        a = Area.objects.create(delegacion=self.delegacion, nombre="Social", prioridad=1)
        r = self.client.patch(f"{URL}{a.pk}/", {"nombre": "Social", "prioridad": 1})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

    # 3. duplicado o inválido
    def test_area_repetida_en_la_delegacion(self):
        Area.objects.create(delegacion=self.delegacion, nombre="Social", prioridad=1)
        r = self.client.post(URL, self.datos(prioridad=2))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "nombre")

    def test_prioridad_repetida_en_la_delegacion(self):
        Area.objects.create(delegacion=self.delegacion, nombre="Social", prioridad=1)
        r = self.client.post(URL, self.datos(nombre="DISERCO"))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "prioridad")

    def test_misma_area_y_prioridad_en_otra_delegacion_es_valido(self):
        Area.objects.create(delegacion=self.delegacion, nombre="Social", prioridad=1)
        otra = Delegacion.objects.create(codigo="D02", nombre="Norte")
        otra.areas.all().delete()
        r = self.client.post(URL, self.datos(delegacion=otra.pk))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)

    def test_prioridad_fuera_de_rango(self):
        for valor in (0, 5, -1):
            r = self.client.post(URL, self.datos(prioridad=valor))
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, valor)
            self.assertEqual(r.data["campo"], "prioridad")

    def test_area_inexistente_y_delegacion_inexistente(self):
        r = self.client.post(URL, self.datos(nombre="otro"))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "nombre")
        r = self.client.post(URL, self.datos(delegacion=9999))
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "delegacion")

    # 4. desactivar
    def test_desactivar(self):
        a = Area.objects.create(delegacion=self.delegacion, nombre="Social", prioridad=1)
        r = self.client.delete(f"{URL}{a.pk}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        a.refresh_from_db()
        self.assertEqual(a.estado, Area.INACTIVA)
        self.assertTrue(Auditoria.objects.filter(evento="desactivar", entidad_id=a.pk).exists())

    # 5. acceso denegado
    def test_no_admin_denegado(self):
        self.client.force_authenticate(crear_funcionario())
        self.assertEqual(self.client.get(URL).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post(URL, self.datos()).status_code, status.HTTP_403_FORBIDDEN)

    # listado
    def test_filtros_y_busqueda(self):
        otra = Delegacion.objects.create(codigo="D02", nombre="Norte")  # con sus 4 áreas
        Area.objects.create(delegacion=self.delegacion, nombre="Social", prioridad=1)
        self.assertEqual(self.client.get(URL, {"delegacion": otra.pk}).data["count"], 4)
        self.assertEqual(self.client.get(URL, {"nombre": "Social"}).data["count"], 2)
        self.assertEqual(self.client.get(URL, {"search": "norte"}).data["count"], 4)
        self.assertEqual(self.client.get(URL, {"search": "d01"}).data["count"], 1)


class AreaIntercambioPrioridadTests(APITestCase):
    """Las 4 áreas nacen con las 4 prioridades: reordenar = intercambiar (HU17)."""

    def setUp(self):
        self.client.force_authenticate(crear_admin())
        self.delegacion = Delegacion.objects.create(codigo="D01", nombre="Centro")
        self.p = {a.prioridad: a for a in self.delegacion.areas.all()}

    def prioridades(self):
        return {a.pk: a.prioridad for a in Area.objects.filter(delegacion=self.delegacion)}

    def test_cambiar_a_prioridad_usada_intercambia_las_dos(self):
        r = self.client.patch(f"{URL}{self.p[1].pk}/", {"prioridad": 2})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data["prioridad"], 2)
        self.p[2].refresh_from_db()
        self.assertEqual(self.p[2].prioridad, 1)
        # Siguen siendo 1, 2, 3 y 4 sin repetir.
        self.assertEqual(sorted(self.prioridades().values()), [1, 2, 3, 4])

    def test_el_intercambio_queda_en_auditoria_de_ambas_areas(self):
        self.client.patch(f"{URL}{self.p[1].pk}/", {"prioridad": 4})
        for area in (self.p[1], self.p[4]):
            self.assertTrue(
                Auditoria.objects.filter(
                    evento="editar", entidad="area", entidad_id=area.pk
                ).exists()
            )

    def test_editar_otro_campo_no_toca_las_prioridades(self):
        antes = self.prioridades()
        r = self.client.patch(f"{URL}{self.p[3].pk}/", {"prioridad": 3, "estado": "inactiva"})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(self.prioridades(), antes)

    def test_prioridad_fuera_de_rango_sigue_rechazada(self):
        antes = self.prioridades()
        r = self.client.patch(f"{URL}{self.p[1].pk}/", {"prioridad": 5})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "prioridad")
        self.assertEqual(self.prioridades(), antes)

    def test_no_se_puede_mover_un_area_a_otra_delegacion_con_la_prioridad_ocupada(self):
        otra = Delegacion.objects.create(codigo="D02", nombre="Norte")
        r = self.client.patch(f"{URL}{self.p[1].pk}/", {"delegacion": otra.pk})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.prioridades()[self.p[1].pk], 1)

    def test_crear_con_prioridad_usada_sigue_rechazado(self):
        r = self.client.post(
            URL, {"delegacion": self.delegacion.pk, "nombre": "Social", "prioridad": 1}
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
