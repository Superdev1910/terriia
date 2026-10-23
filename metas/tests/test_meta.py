from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria
from metas.models import MetaIndividual
from personas.models import Funcionario, Usuario

from .datos_base import DatosMetasMixin

URL = "/api/metas/"


class MetaIndividualTests(DatosMetasMixin, APITestCase):
    def setUp(self):
        self.preparar_datos()
        self.md = self.crear_meta_delegacion("100.00")
        self.datos = {
            "meta_delegacion": self.md.pk,
            "funcionario": self.ana.pk,
            "valor_objetivo": "40.00",
            "unidad": "visitas",
        }

    # 1. crear
    def test_crear(self):
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        meta = MetaIndividual.objects.get()
        self.assertEqual(meta.valor_objetivo, Decimal("40.00"))
        self.assertTrue(
            Auditoria.objects.filter(evento="crear", entidad="meta", entidad_id=meta.pk).exists()
        )

    def test_suma_igual_al_total_permitida(self):
        self.client.post(URL, self.datos)
        self.datos.update(funcionario=self.luis.pk, valor_objetivo="60.00")
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)

    # 2. editar (solo la unidad; el valor se cambia recalibrando)
    def test_editar_unidad(self):
        meta = self.crear_meta(self.md, self.ana)
        r = self.client.patch(f"{URL}{meta.pk}/", {"unidad": "casos"})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        meta.refresh_from_db()
        self.assertEqual(meta.unidad, "casos")
        self.assertTrue(Auditoria.objects.filter(evento="editar", entidad_id=meta.pk).exists())

    def test_valor_no_se_cambia_por_edicion(self):
        meta = self.crear_meta(self.md, self.ana)
        r = self.client.patch(f"{URL}{meta.pk}/", {"valor_objetivo": "10.00"})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "valor_objetivo")
        meta.refresh_from_db()
        self.assertEqual(meta.valor_objetivo, Decimal("40.00"))

    # 3. duplicado o inválido
    def test_funcionario_duplicado(self):
        self.crear_meta(self.md, self.ana)
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "funcionario")

    def test_suma_supera_el_total(self):
        self.crear_meta(self.md, self.ana, "70.00")
        self.datos.update(funcionario=self.luis.pk, valor_objetivo="40.00")
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "valor_objetivo")

    def test_valor_cero_rechazado(self):
        self.datos["valor_objetivo"] = "0"
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "valor_objetivo")

    def test_funcionario_de_otra_delegacion(self):
        otro = self.crear_funcionario("F-0003", "Eva Soto", self.norte)
        self.datos["funcionario"] = otro.pk
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "funcionario")

    def test_funcionario_inactivo(self):
        Funcionario.objects.filter(pk=self.ana.pk).update(estado=Funcionario.INACTIVO)
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "funcionario")

    # 4. no se borra (la tabla no tiene columna de estado)
    def test_no_se_puede_borrar(self):
        meta = self.crear_meta(self.md, self.ana)
        r = self.client.delete(f"{URL}{meta.pk}/")
        self.assertEqual(r.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(MetaIndividual.objects.filter(pk=meta.pk).exists())

    # 5. acceso denegado a no administrador
    def test_no_admin_denegado(self):
        func = Usuario.objects.create_user(
            email="f@terriia.cl", rut="12345678-5", password="OtraClave#2026"
        )
        self.client.force_authenticate(func)
        r = self.client.get(URL)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", r.data)

    # listado: búsqueda y filtro por delegación
    def test_listado_busqueda_y_filtros(self):
        self.crear_meta(self.md, self.ana, "30.00")
        self.crear_meta(self.md, self.luis, "20.00")
        r = self.client.get(URL, {"search": "Rojas"})
        self.assertEqual(r.data["count"], 1)
        r = self.client.get(URL, {"meta_delegacion__delegacion": self.centro.pk})
        self.assertEqual(r.data["count"], 2)
        r = self.client.get(URL, {"meta_delegacion__delegacion": self.norte.pk})
        self.assertEqual(r.data["count"], 0)
