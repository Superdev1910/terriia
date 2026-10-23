"""Pruebas del mantenedor usuario (SCRUM-14 HU18). Sirve de modelo para los demás mantenedores."""

from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria, Rol
from organizacion.models import Cargo, Delegacion
from personas.models import Funcionario, Usuario

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


class UsuarioFuncionarioDelegacionTests(APITestCase):
    """SCRUM-38 HU19: usuario -> funcionario y delegación (NULL = acceso global)."""

    def setUp(self):
        self.admin = Usuario.objects.create_user(
            email="admin@terriia.cl",
            rut="11.111.111-1",
            password="ClaveSegura#2026",
            rol=Rol.objects.get(nombre=Rol.ADMINISTRADOR),
        )
        self.client.force_authenticate(self.admin)
        self.centro = Delegacion.objects.create(codigo="CEN", nombre="Centro")
        self.norte = Delegacion.objects.create(codigo="NOR", nombre="Norte")
        self.funcionario = Funcionario.objects.create(
            identificador_inst="F-0001",
            nombre="Ana Pérez",
            cargo=Cargo.objects.create(nombre="Inspector"),
            delegacion=self.centro,
        )
        self.datos = {
            "rut": "12.345.678-5",
            "email": "ana@terriia.cl",
            "rol": Rol.objects.get(nombre=Rol.FUNCIONARIO).pk,
            "password": "OtraClave#2026",
        }

    def _crear(self, **extra):
        return Usuario.objects.create_user(
            email="ana@terriia.cl", rut="12345678-5", password="OtraClave#2026", **extra
        )

    def test_crear_con_funcionario_y_delegacion(self):
        self.datos.update(funcionario=self.funcionario.pk, delegacion=self.centro.pk)
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        u = Usuario.objects.get(email="ana@terriia.cl")
        self.assertEqual(u.funcionario, self.funcionario)
        self.assertEqual(u.delegacion, self.centro)
        aud = Auditoria.objects.get(evento="crear", entidad="usuario", entidad_id=u.pk)
        self.assertEqual(aud.valor_nuevo["delegacion"], self.centro.pk)
        self.assertEqual(aud.valor_nuevo["funcionario"], self.funcionario.pk)

    def test_sin_delegacion_es_acceso_global(self):
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertIsNone(r.data["delegacion"])
        self.assertIsNone(r.data["funcionario"])

    def test_cambiar_y_quitar_delegacion(self):
        u = self._crear(delegacion=self.centro)
        r = self.client.patch(f"{URL}{u.pk}/", {"delegacion": self.norte.pk})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        u.refresh_from_db()
        self.assertEqual(u.delegacion, self.norte)
        r = self.client.patch(f"{URL}{u.pk}/", {"delegacion": None}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        u.refresh_from_db()
        self.assertIsNone(u.delegacion)

    def test_delegacion_inactiva_rechazada(self):
        Delegacion.objects.filter(pk=self.norte.pk).update(estado=Delegacion.INACTIVA)
        self.datos["delegacion"] = self.norte.pk
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "delegacion")

    def test_funcionario_inactivo_rechazado(self):
        Funcionario.objects.filter(pk=self.funcionario.pk).update(estado=Funcionario.INACTIVO)
        self.datos["funcionario"] = self.funcionario.pk
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "funcionario")

    def test_editar_sin_cambiar_delegacion_ni_funcionario_inactivos(self):
        u = self._crear(delegacion=self.centro, funcionario=self.funcionario)
        Delegacion.objects.filter(pk=self.centro.pk).update(estado=Delegacion.INACTIVA)
        Funcionario.objects.filter(pk=self.funcionario.pk).update(estado=Funcionario.INACTIVO)
        datos = {
            "first_name": "Beatriz",
            "delegacion": self.centro.pk,
            "funcionario": self.funcionario.pk,
        }
        r = self.client.patch(f"{URL}{u.pk}/", datos)
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

    def test_filtro_por_delegacion(self):
        self._crear(delegacion=self.centro)
        self.assertEqual(self.client.get(URL, {"delegacion": self.centro.pk}).data["count"], 1)
        self.assertEqual(self.client.get(URL, {"delegacion": self.norte.pk}).data["count"], 0)

    def test_no_se_borra_funcionario_con_usuario(self):
        self._crear(funcionario=self.funcionario)
        with self.assertRaises(ProtectedError):
            self.funcionario.delete()


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
