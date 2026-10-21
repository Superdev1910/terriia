"""Pruebas del mantenedor usuario (SCRUM-14 HU18). Sirve de modelo para los demás mantenedores."""

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria, Rol
from personas.models import Usuario

URL = "/api/usuarios/"


class UsuarioMantenedorTests(APITestCase):
    def setUp(self):
        self.rol_admin = Rol.objects.get(nombre=Rol.ADMINISTRADOR)
        self.rol_func = Rol.objects.get(nombre=Rol.FUNCIONARIO)
        self.admin = Usuario.objects.create_user(
            email="admin@terriia.cl",
            rut="11.111.111-1",
            password="ClaveSegura#2026",
            rol=self.rol_admin,
        )
        self.client.force_authenticate(self.admin)
        self.datos = {
            "rut": "12.345.678-5",
            "email": "Funcionario@Terriia.cl",
            "first_name": "Ana",
            "last_name": "Pérez",
            "rol": self.rol_func.pk,
            "password": "OtraClave#2026",
        }

    # 1. crear
    def test_crear(self):
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        u = Usuario.objects.get(email="funcionario@terriia.cl")
        self.assertEqual(u.rut, "12345678-5")
        self.assertTrue(u.check_password("OtraClave#2026"))
        self.assertNotIn("password", r.data)
        self.assertTrue(
            Auditoria.objects.filter(evento="crear", entidad="usuario", entidad_id=u.pk).exists()
        )

    # 2. editar
    def test_editar(self):
        u = Usuario.objects.create_user(
            email="x@terriia.cl", rut="12345678-5", password="OtraClave#2026"
        )
        r = self.client.patch(f"{URL}{u.pk}/", {"first_name": "Beatriz"})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        u.refresh_from_db()
        self.assertEqual(u.first_name, "Beatriz")
        aud = Auditoria.objects.get(evento="editar", entidad_id=u.pk)
        self.assertNotIn("password", aud.valor_nuevo)

    # 3. duplicado o inválido
    def test_rut_duplicado(self):
        self.datos["rut"] = "11111111-1"  # ya es del admin
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "rut")

    def test_rut_invalido(self):
        self.datos["rut"] = "12345678-9"
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data, {"error": "RUT inválido.", "campo": "rut"})

    # 4. desactivar (no borra)
    def test_desactivar(self):
        u = Usuario.objects.create_user(
            email="x@terriia.cl", rut="12345678-5", password="OtraClave#2026"
        )
        r = self.client.delete(f"{URL}{u.pk}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        u.refresh_from_db()
        self.assertEqual(u.estado, Usuario.INACTIVO)
        self.assertFalse(u.is_active)
        self.assertTrue(Auditoria.objects.filter(evento="desactivar", entidad_id=u.pk).exists())

    # 5. acceso denegado a no administrador
    def test_no_admin_denegado(self):
        func = Usuario.objects.create_user(
            email="f@terriia.cl", rut="12345678-5", password="OtraClave#2026"
        )
        self.client.force_authenticate(func)
        r = self.client.get(URL)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", r.data)

    def test_listado_busqueda(self):
        r = self.client.get(URL, {"search": "admin"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["count"], 1)


class LoginTests(APITestCase):
    def setUp(self):
        Usuario.objects.create_user(
            email="a@terriia.cl", rut="11111111-1", password="ClaveSegura#2026"
        )

    def test_login_ok(self):
        r = self.client.post(
            "/api/auth/login/", {"email": "A@terriia.cl", "password": "ClaveSegura#2026"}
        )
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["rol"], Rol.FUNCIONARIO)
        self.assertEqual(self.client.get("/api/auth/yo/").status_code, 200)

    def test_login_mala_clave(self):
        r = self.client.post("/api/auth/login/", {"email": "a@terriia.cl", "password": "x"})
        self.assertEqual(r.status_code, 400)

    def test_usuario_inactivo_no_entra(self):
        Usuario.objects.filter(email="a@terriia.cl").update(estado=Usuario.INACTIVO)
        r = self.client.post(
            "/api/auth/login/", {"email": "a@terriia.cl", "password": "ClaveSegura#2026"}
        )
        self.assertEqual(r.status_code, 400)
