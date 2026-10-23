from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria
from metas.models import MetaDelegacion
from personas.models import Usuario

from .datos_base import DatosMetasMixin

URL = "/api/metas-delegacion/"


class MetaDelegacionTests(DatosMetasMixin, APITestCase):
    def setUp(self):
        self.preparar_datos()
        self.datos = {
            "item": self.item.pk,
            "delegacion": self.centro.pk,
            "periodo": self.periodo.pk,
            "valor_objetivo_total": "100.00",
        }

    # 1. crear
    def test_crear(self):
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["suma_metas"], "0.00")
        self.assertEqual(r.data["saldo_por_asignar"], "100.00")
        md = MetaDelegacion.objects.get()
        self.assertTrue(
            Auditoria.objects.filter(
                evento="crear", entidad="meta_delegacion", entidad_id=md.pk
            ).exists()
        )

    # 2. editar (sin metas individuales el total sí se puede cambiar)
    def test_editar_total(self):
        md = self.crear_meta_delegacion()
        r = self.client.patch(f"{URL}{md.pk}/", {"valor_objetivo_total": "120.00"})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        md.refresh_from_db()
        self.assertEqual(md.valor_objetivo_total, Decimal("120.00"))
        self.assertTrue(Auditoria.objects.filter(evento="editar", entidad_id=md.pk).exists())

    # 3. duplicado o inválido
    def test_duplicado(self):
        self.crear_meta_delegacion()
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "item")

    def test_total_cero_rechazado(self):
        self.datos["valor_objetivo_total"] = "0"
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "valor_objetivo_total")

    def test_item_inactivo_rechazado(self):
        self.item.activo = False
        self.item.save()
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "item")

    def test_total_bloqueado_con_metas_individuales(self):
        md = self.crear_meta_delegacion()
        self.crear_meta(md, self.ana)
        r = self.client.patch(f"{URL}{md.pk}/", {"valor_objetivo_total": "50.00"})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "valor_objetivo_total")

    # 4. no se borra (la tabla no tiene columna de estado)
    def test_no_se_puede_borrar(self):
        md = self.crear_meta_delegacion()
        r = self.client.delete(f"{URL}{md.pk}/")
        self.assertEqual(r.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(MetaDelegacion.objects.filter(pk=md.pk).exists())

    # 5. acceso denegado a no administrador
    def test_no_admin_denegado(self):
        func = Usuario.objects.create_user(
            email="f@terriia.cl", rut="12345678-5", password="OtraClave#2026"
        )
        self.client.force_authenticate(func)
        r = self.client.get(URL)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", r.data)

    # listado: suma asignada, saldo y filtro por delegación
    def test_listado_con_saldo_y_filtro(self):
        md = self.crear_meta_delegacion("100.00", self.centro)
        self.crear_meta_delegacion("50.00", self.norte)
        self.crear_meta(md, self.ana, "30.00")
        r = self.client.get(URL, {"delegacion": self.centro.pk})
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["results"][0]["suma_metas"], "30.00")
        self.assertEqual(r.data["results"][0]["saldo_por_asignar"], "70.00")
