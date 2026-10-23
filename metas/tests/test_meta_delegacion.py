from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria
from metas.models import MetaDelegacion
from organizacion.models import Cargo
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
        self.assertIsNone(r.data["advertencia"])  # el único ítem pesa 100%
        md = MetaDelegacion.objects.get()
        self.assertTrue(
            Auditoria.objects.filter(
                evento="crear", entidad="meta_delegacion", entidad_id=md.pk
            ).exists()
        )

    # 2. editar
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

    # listado: filtro por delegación
    def test_listado_y_filtro_por_delegacion(self):
        self.crear_meta_delegacion("100.00", self.centro)
        self.crear_meta_delegacion("50.00", self.norte)
        r = self.client.get(URL, {"delegacion": self.centro.pk})
        self.assertEqual(r.data["count"], 1)

    # HU09: la respuesta trae los datos del ítem (tipo de meta, ponderador, cargo)
    def test_respuesta_incluye_datos_del_item(self):
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.data["item_nombre"], "Visitas")
        self.assertEqual(r.data["tipo_meta"], "conteo")
        self.assertEqual(r.data["ponderador"], "100.00")
        self.assertEqual(r.data["cargo_nombre"], "Inspector")

    # HU09: se soportan metas por cantidad y por porcentaje
    def test_meta_por_porcentaje(self):
        soluciones = self.crear_item("Soluciones al ingreso al tubo", "porcentaje", "30")
        self.datos.update(item=soluciones.pk, valor_objetivo_total="80")
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["tipo_meta"], "porcentaje")

    def test_porcentaje_no_puede_superar_100(self):
        soluciones = self.crear_item("Soluciones al ingreso al tubo", "porcentaje", "30")
        self.datos.update(item=soluciones.pk, valor_objetivo_total="120")
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "valor_objetivo_total")

    # HU09: advierte si los ponderadores de las metas del cargo no suman 100%
    def test_advertencia_hasta_completar_100(self):
        atencion = self.crear_item("Atención de usuario", ponderador="40")
        talleres = self.crear_item("Gestión de talleres", ponderador="60")
        self.datos.update(item=atencion.pk, valor_objetivo_total="45")
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertIn("40.00%", r.data["advertencia"])
        self.assertIn("Inspector", r.data["advertencia"])

        self.datos.update(item=talleres.pk, valor_objetivo_total="24")
        r = self.client.post(URL, self.datos)
        self.assertIsNone(r.data["advertencia"])
        listado = self.client.get(URL)
        self.assertTrue(all(m["advertencia"] is None for m in listado.data["results"]))

    def test_advertencia_es_por_delegacion(self):
        atencion = self.crear_item("Atención de usuario", ponderador="40")
        self.crear_meta_delegacion("45", self.centro, item=atencion)
        self.datos.update(item=atencion.pk, delegacion=self.norte.pk, valor_objetivo_total="30")
        r = self.client.post(URL, self.datos)
        self.assertIn("40.00%", r.data["advertencia"])

    def test_filtro_por_cargo(self):
        self.crear_meta_delegacion("100.00")
        r = self.client.get(URL, {"item__cargo": self.cargo.pk})
        self.assertEqual(r.data["count"], 1)
        otro_cargo = Cargo.objects.create(nombre="Asistente social")
        r = self.client.get(URL, {"item__cargo": otro_cargo.pk})
        self.assertEqual(r.data["count"], 0)