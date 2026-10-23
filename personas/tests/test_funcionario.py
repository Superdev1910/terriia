"""Pruebas del mantenedor funcionario (feature/funcionario)."""

from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria, Rol
from organizacion.models import Cargo, Delegacion
from personas.models import Funcionario, Usuario

URL = "/api/funcionarios/"


class FuncionarioMantenedorTests(APITestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            email="admin@terriia.cl",
            rut="11.111.111-1",
            password="ClaveSegura#2026",
            rol=Rol.objects.get(nombre=Rol.ADMINISTRADOR),
        )
        self.client.force_authenticate(self.admin)
        self.cargo = Cargo.objects.create(nombre="Inspector")
        self.centro = Delegacion.objects.create(codigo="CEN", nombre="Centro")
        self.norte = Delegacion.objects.create(codigo="NOR", nombre="Norte")
        self.datos = {
            "identificador_inst": "F-0001",
            "nombre": "Ana Pérez",
            "cargo": self.cargo.pk,
            "delegacion": self.centro.pk,
        }

    def _crear(self, identificador, delegacion=None, nombre="Ana Pérez"):
        return Funcionario.objects.create(
            identificador_inst=identificador,
            nombre=nombre,
            cargo=self.cargo,
            delegacion=delegacion or self.centro,
        )

    # 1. crear
    def test_crear(self):
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        f = Funcionario.objects.get(identificador_inst="F-0001")
        self.assertEqual(f.estado, Funcionario.ACTIVO)
        self.assertTrue(
            Auditoria.objects.filter(
                evento="crear", entidad="funcionario", entidad_id=f.pk
            ).exists()
        )

    # 2. editar
    def test_editar(self):
        f = self._crear("F-0001")
        r = self.client.patch(f"{URL}{f.pk}/", {"delegacion": self.norte.pk})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        f.refresh_from_db()
        self.assertEqual(f.delegacion, self.norte)
        self.assertTrue(Auditoria.objects.filter(evento="editar", entidad_id=f.pk).exists())

    # 3. duplicado o inválido
    def test_identificador_duplicado(self):
        self._crear("F-0001")
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "identificador_inst")
        self.assertEqual(
            r.data["error"], "Ya existe un funcionario con este identificador institucional."
        )

    def test_identificador_vacio(self):
        self.datos["identificador_inst"] = "   "
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "identificador_inst")

    def test_identificador_muy_largo(self):
        self.datos["identificador_inst"] = "F" * 31
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "identificador_inst")

    def test_nombre_vacio(self):
        self.datos["nombre"] = "   "
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "nombre")

    def test_delegacion_inexistente(self):
        self.datos["delegacion"] = 9999
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "delegacion")

    def test_delegacion_inactiva_rechazada(self):
        Delegacion.objects.filter(pk=self.centro.pk).update(estado=Delegacion.INACTIVA)
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "delegacion")

    def test_cargo_no_vigente_rechazado(self):
        Cargo.objects.filter(pk=self.cargo.pk).update(vigente=False)
        r = self.client.post(URL, self.datos)
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "cargo")

    def test_editar_sin_cambiar_delegacion_inactiva(self):
        f = self._crear("F-0001")
        Delegacion.objects.filter(pk=self.centro.pk).update(estado=Delegacion.INACTIVA)
        r = self.client.patch(f"{URL}{f.pk}/", {"identificador_inst": "F-0009"})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

    # 4. desactivar (no borra)
    def test_desactivar(self):
        f = self._crear("F-0001")
        r = self.client.delete(f"{URL}{f.pk}/")
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        f.refresh_from_db()
        self.assertEqual(f.estado, Funcionario.INACTIVO)
        self.assertTrue(Auditoria.objects.filter(evento="desactivar", entidad_id=f.pk).exists())

    # 5. acceso denegado a no administrador
    def test_no_admin_denegado(self):
        func = Usuario.objects.create_user(
            email="f@terriia.cl", rut="12345678-5", password="OtraClave#2026"
        )
        self.client.force_authenticate(func)
        r = self.client.get(URL)
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", r.data)

    # listado: búsqueda, filtro por delegación y por estado
    def test_listado_busqueda_y_filtros(self):
        self._crear("F-0001", self.centro)
        self._crear("F-0002", self.norte, nombre="Luis Rojas")
        inactivo = self._crear("F-0003", self.norte)
        Funcionario.objects.filter(pk=inactivo.pk).update(estado=Funcionario.INACTIVO)

        r = self.client.get(URL, {"search": "F-0002"})
        self.assertEqual(r.data["count"], 1)
        r = self.client.get(URL, {"search": "Rojas"})
        self.assertEqual(r.data["count"], 1)
        r = self.client.get(URL, {"delegacion": self.norte.pk})
        self.assertEqual(r.data["count"], 2)
        r = self.client.get(URL, {"delegacion": self.norte.pk, "estado": "activo"})
        self.assertEqual(r.data["count"], 1)

    # SCRUM-38: lo que usa la pantalla de funcionarios
    def test_nombres_y_orden_para_la_pantalla(self):
        self._crear("F-0001", self.norte)
        otro = self._crear("F-0002", self.centro, nombre="Luis Rojas")
        otro.cargo = Cargo.objects.create(nombre="Asistente social")
        otro.save()
        r = self.client.get(URL, {"ordering": "cargo__nombre,id_funcionario"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        primero = r.data["results"][0]
        self.assertEqual(primero["identificador_inst"], "F-0002")
        self.assertEqual(primero["cargo_nombre"], "Asistente social")
        self.assertEqual(primero["delegacion_codigo"], "CEN")
        self.assertEqual(primero["delegacion_nombre"], "Centro")
        r = self.client.get(URL, {"ordering": "-delegacion__codigo"})
        self.assertEqual(r.data["results"][0]["delegacion_codigo"], "NOR")
        r = self.client.get(URL, {"search": "Centro"})
        self.assertEqual(r.data["count"], 1)
