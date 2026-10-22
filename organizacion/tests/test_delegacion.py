"""Pruebas del mantenedor delegacion (SCRUM-13 HU17)."""

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria
from organizacion.models import Area, Delegacion

from .utiles import crear_admin, crear_funcionario

URL = "/api/delegaciones/"


class DelegacionMantenedorTests(APITestCase):
    def setUp(self):
        self.admin = crear_admin()
        self.client.force_authenticate(self.admin)
        self.datos = {
            "codigo": "d01",
            "nombre": "Delegación Centro",
            "direccion": "Prat 451",
            "comuna": "La Serena",
        }

    # 1. crear (HU17: nacen las 4 áreas)
    def test_crear_genera_cuatro_areas(self):
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        d = Delegacion.objects.get(pk=r.data["id_delegacion"])
        self.assertEqual(d.codigo, "D01")  # se guarda en mayúsculas
        self.assertEqual(d.estado, Delegacion.ACTIVA)
        areas = Area.objects.filter(delegacion=d)
        self.assertEqual(areas.count(), 4)
        self.assertEqual(sorted(a.prioridad for a in areas), [1, 2, 3, 4])
        self.assertEqual({a.nombre for a in areas}, {n for n, _ in Area.NOMBRES})
        self.assertEqual(r.data["total_areas"], 4)
        self.assertTrue(
            Auditoria.objects.filter(evento="crear", entidad="delegacion", entidad_id=d.pk).exists()
        )

    # 2. editar
    def test_editar_no_duplica_areas(self):
        d = Delegacion.objects.create(codigo="D01", nombre="Centro")
        r = self.client.patch(f"{URL}{d.pk}/", {"nombre": "Centro Histórico"})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        d.refresh_from_db()
        self.assertEqual(d.nombre, "Centro Histórico")
        self.assertEqual(d.areas.count(), 4)
        self.assertTrue(Auditoria.objects.filter(evento="editar", entidad_id=d.pk).exists())

    # 3. duplicado o inválido
    def test_codigo_duplicado_sin_distinguir_mayusculas(self):
        Delegacion.objects.create(codigo="D01", nombre="Centro")
        r = self.client.post(URL, self.datos)  # "d01"
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "codigo")

    def test_nombre_duplicado(self):
        Delegacion.objects.create(codigo="D09", nombre="Delegación Centro")
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "nombre")

    def test_codigo_obligatorio(self):
        self.datos.pop("codigo")
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "codigo")

    def test_nombre_solo_espacios(self):
        self.datos["nombre"] = "   "
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_longitud_maxima_codigo(self):
        self.datos["codigo"] = "X" * 11
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "codigo")
        self.assertFalse(Delegacion.objects.exists())  # sin guardado parcial

    def test_editar_conservando_su_propio_codigo(self):
        d = Delegacion.objects.create(codigo="D01", nombre="Centro")
        r = self.client.patch(f"{URL}{d.pk}/", {"codigo": "d01", "comuna": "Coquimbo"})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

    # 4. desactivar (no borra)
    def test_desactivar_conserva_registro_y_areas(self):
        d = Delegacion.objects.create(codigo="D01", nombre="Centro")
        r = self.client.delete(f"{URL}{d.pk}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        d.refresh_from_db()
        self.assertEqual(d.estado, Delegacion.INACTIVA)
        self.assertEqual(d.areas.count(), 4)
        self.assertTrue(Auditoria.objects.filter(evento="desactivar", entidad_id=d.pk).exists())

    # 5. acceso denegado a no administrador
    def test_no_admin_denegado(self):
        self.client.force_authenticate(crear_funcionario())
        for metodo in (self.client.get, self.client.post):
            r = metodo(URL)
            self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
            self.assertIn("error", r.data)

    def test_anonimo_denegado(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(URL).status_code, status.HTTP_403_FORBIDDEN)

    # listado
    def test_busqueda_parcial_en_varios_campos(self):
        Delegacion.objects.create(codigo="D01", nombre="Centro", comuna="La Serena")
        Delegacion.objects.create(
            codigo="D02", nombre="Norte", direccion="Av. del Mar", comuna="Coquimbo"
        )
        casos = [("cent", 1), ("CENT", 1), ("coqui", 1), ("av. del", 1), ("d0", 2), ("zzz", 0)]
        for texto, esperado in casos:
            r = self.client.get(URL, {"search": texto})
            self.assertEqual(r.data["count"], esperado, texto)

    def test_filtro_estado_y_paginacion(self):
        for n in range(25):
            Delegacion.objects.create(codigo=f"D{n:02d}", nombre=f"Delegación {n}")
        Delegacion.objects.filter(codigo="D00").update(estado=Delegacion.INACTIVA)
        r = self.client.get(URL)
        self.assertEqual(r.data["count"], 25)
        self.assertEqual(len(r.data["results"]), 20)
        r = self.client.get(URL, {"estado": "inactiva"})
        self.assertEqual(r.data["count"], 1)
        r = self.client.get(URL, {"page": 2, "estado": "activa"})
        self.assertEqual(len(r.data["results"]), 4)  # 24 activas: 20 + 4
