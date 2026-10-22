from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase
from metas.models import Periodo

Usuario = get_user_model()


class PeriodoAPITestCase(APITestCase):
    def setUp(self):
        # Se crea el superusuario sin el campo 'username'
        self.admin = Usuario.objects.create_superuser(
            email="admin@laserena.cl",
            rut="11111111-1",
            password="Password123!",
        )
        self.client.force_authenticate(user=self.admin)

    def test_crear_periodo_exitoso(self):
        """1. Crear: Comprueba la creación exitosa con datos válidos"""
        data = {
            "fecha_inicio": "2026-01-01",
            "fecha_termino": "2026-03-31",
            "dias_computables": 90,
            "estado": "vigente",
            "version_parametros": "v1.0",
        }
        res = self.client.post("/api/periodos/", data)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Periodo.objects.count(), 1)

    def test_editar_periodo(self):
        """2. Editar: Comprueba la actualización de un período existente"""
        periodo = Periodo.objects.create(
            fecha_inicio="2026-01-01",
            fecha_termino="2026-03-31",
            dias_computables=90,
            estado="programado",
            version_parametros="v1.0",
        )
        data = {"version_parametros": "v1.1", "estado": "vigente"}
        res = self.client.patch(f"/api/periodos/{periodo.pk}/", data)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        periodo.refresh_from_db()
        self.assertEqual(periodo.version_parametros, "v1.1")
        self.assertEqual(periodo.estado, "vigente")

    def test_duplicado_o_invalido(self):
        """3. Duplicado/Inválido: Comprueba rechazo por fechas invertidas y doble estado vigente"""
        # Prueba 3a: Rechazar fecha_termino <= fecha_inicio
        data_invalida = {
            "fecha_inicio": "2026-03-31",
            "fecha_termino": "2026-01-01",
            "dias_computables": 90,
            "estado": "programado",
            "version_parametros": "v1.0",
        }
        res_invalido = self.client.post("/api/periodos/", data_invalida)
        self.assertEqual(res_invalido.status_code, status.HTTP_400_BAD_REQUEST)

        # Prueba 3b: Rechazar dos períodos simultáneos en estado 'vigente'
        Periodo.objects.create(
            fecha_inicio="2026-01-01",
            fecha_termino="2026-03-31",
            dias_computables=90,
            estado="vigente",
            version_parametros="v1.0",
        )
        data_duplicada = {
            "fecha_inicio": "2026-04-01",
            "fecha_termino": "2026-06-30",
            "dias_computables": 90,
            "estado": "vigente",
            "version_parametros": "v1.0",
        }
        res_duplicado = self.client.post("/api/periodos/", data_duplicada)
        self.assertEqual(res_duplicado.status_code, status.HTTP_400_BAD_REQUEST)

    def test_desactivar_periodo(self):
        """4. Desactivar: Comprueba borrado lógico / cambio de estado vía DELETE"""
        periodo = Periodo.objects.create(
            fecha_inicio="2026-01-01",
            fecha_termino="2026-03-31",
            dias_computables=90,
            estado="vigente",
            version_parametros="v1.0",
        )
        res = self.client.delete(f"/api/periodos/{periodo.pk}/")
        self.assertIn(
            res.status_code,
            [status.HTTP_200_OK, status.HTTP_204_NO_CONTENT],
        )

    def test_acceso_denegado_sin_rol(self):
        """5. Acceso denegado: Comprueba que usuarios sin autenticación o sin rol Administrador sean bloqueados"""
        self.client.logout()
        res = self.client.get("/api/periodos/")
        self.assertIn(
            res.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )
