from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from core.models import Auditoria, Rol
from metas.models import Item
from organizacion.models import Area, Cargo, Delegacion

Usuario = get_user_model()


class ItemAPITestCase(APITestCase):
    def setUp(self):
        # 1. Superusuario administrador para las pruebas
        self.admin = Usuario.objects.create_superuser(
            email="admin@laserena.cl",
            rut="11111111-1",
            password="Password123!",
        )
        self.client.force_authenticate(user=self.admin)

        # 2. Estructura organizativa base para la Foreign Key id_cargo
        self.delegacion = Delegacion.objects.create(
            nombre="Delegación Centro",
            codigo="D01",
        )
        # Se obtiene el área creada automáticamente por la delegación (HU17)
        self.area = Area.objects.filter(delegacion=self.delegacion).first()
        if not self.area:
            self.area = Area.objects.create(
                delegacion=self.delegacion,
                nombre="Social",
                prioridad=1,
            )
        self.cargo = Cargo.objects.create(
            area=self.area,
            nombre="Gestor Territorial",
        )

    def test_crear_item_exitoso(self):
        """1. Crear: Registro de un ítem válido con verificación previa"""
        data = {
            "cargo": self.cargo.pk,
            "nombre": "Atención de Caso Social",
            "tipo_meta": "conteo",
            "ponderador": "40.00",
            "activo": True,
            "requiere_verificacion_previa": True,
            "radio_tolerancia_metros": 100,
        }
        res = self.client.post("/api/items/", data, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Item.objects.count(), 1)

    def test_editar_item(self):
        """2. Editar: Actualización de datos de un ítem existente"""
        item = Item.objects.create(
            cargo=self.cargo,
            nombre="Inspección en Terreno",
            tipo_meta="conteo",
            ponderador=Decimal("30.00"),
        )
        data = {"nombre": "Inspección Avanzada en Terreno", "ponderador": "35.00"}
        res = self.client.patch(f"/api/items/{item.pk}/", data, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        item.refresh_from_db()
        self.assertEqual(item.nombre, "Inspección Avanzada en Terreno")
        self.assertEqual(item.ponderador, Decimal("35.00"))

    def test_duplicado_o_invalido(self):
        """3. Inválido: Rechazar verificación sin radio y suma de ponderadores > 100%"""
        # Prueba 3a: Requiere verificación previa pero se omite el radio de tolerancia
        data_sin_radio = {
            "cargo": self.cargo.pk,
            "nombre": "Ítem Inválido",
            "tipo_meta": "conteo",
            "ponderador": "20.00",
            "requiere_verificacion_previa": True,
        }
        res_sin_radio = self.client.post("/api/items/", data_sin_radio, format="json")
        self.assertEqual(res_sin_radio.status_code, status.HTTP_400_BAD_REQUEST)

        # Prueba 3b: Suma de ponderadores para el mismo cargo supera el 100%
        Item.objects.create(
            cargo=self.cargo,
            nombre="Ítem Existente 1",
            tipo_meta="conteo",
            ponderador=Decimal("60.00"),
        )
        data_excede_peso = {
            "cargo": self.cargo.pk,
            "nombre": "Ítem Excede Peso",
            "tipo_meta": "conteo",
            "ponderador": "50.00",  # 60 + 50 = 110% > 100%
        }
        res_excede = self.client.post("/api/items/", data_excede_peso, format="json")
        self.assertEqual(res_excede.status_code, status.HTTP_400_BAD_REQUEST)

    def test_desactivar_item(self):
        """4. Desactivar: Borrado lógico cambiando activo a False y auditando"""
        item = Item.objects.create(
            cargo=self.cargo,
            nombre="Ítem a Desactivar",
            tipo_meta="porcentaje",
            ponderador=Decimal("20.00"),
            activo=True,
        )
        res = self.client.delete(f"/api/items/{item.pk}/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        item.refresh_from_db()
        self.assertFalse(item.activo)  # Borrado lógico: queda inactivo
        self.assertTrue(Auditoria.objects.filter(evento="desactivar", entidad="item").exists())

    def test_acceso_denegado_a_funcionario(self):
        """5. Acceso denegado: Usuario con rol Funcionario no puede usar el mantenedor"""
        funcionario = Usuario.objects.create_user(
            email="func@laserena.cl",
            rut="12345678-5",
            password="Password123!",
            rol=Rol.objects.get(nombre=Rol.FUNCIONARIO),
        )
        self.client.force_authenticate(user=funcionario)
        res = self.client.get("/api/items/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
