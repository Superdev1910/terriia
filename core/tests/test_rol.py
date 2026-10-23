"""Pruebas del mantenedor de roles (API /api/roles/ y pantalla /core/roles/)."""

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria, Rol
from core.validators import calcular_dv
from personas.models import Usuario

CLAVE = "ClaveSegura#2026"


def crear_usuario(email, cuerpo_rut, rol):
    return Usuario.objects.create_user(
        email=email,
        rut=f"{cuerpo_rut}-{calcular_dv(cuerpo_rut)}",
        password=CLAVE,
        rol=rol if isinstance(rol, Rol) else Rol.objects.get(nombre=rol),
    )


def crear_admin():
    return crear_usuario("admin.roles@terriia.cl", 11111111, Rol.ADMINISTRADOR)


def crear_funcionario():
    return crear_usuario("func.roles@terriia.cl", 12345678, Rol.FUNCIONARIO)


class RolTests(APITestCase):
    url = "/api/roles/"

    def setUp(self):
        self.client.force_authenticate(crear_admin())

    def crear(self, **datos):
        datos = {"nombre": "Coordinador comunal", "descripcion": "Rol de prueba", **datos}
        return self.client.post(self.url, datos, format="json")

    def test_crear_rol_nuevo(self):
        r = self.crear(nombre="  Coordinador   comunal ")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        self.assertEqual(r.data["nombre"], "Coordinador comunal")
        self.assertTrue(r.data["activo"])
        self.assertFalse(r.data["es_del_sistema"])
        self.assertEqual(r.data["cantidad_usuarios"], 0)
        self.assertTrue(
            Auditoria.objects.filter(
                entidad="rol", evento="crear", entidad_id=r.data["id_rol"]
            ).exists()
        )

    def test_rechaza_nombre_duplicado_o_vacio(self):
        self.crear()
        r = self.crear(nombre="COORDINADOR COMUNAL")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data, {"error": "Ya existe un rol con este nombre.", "campo": "nombre"})
        self.assertEqual(self.crear(nombre="administrador").status_code, 400)
        self.assertEqual(self.crear(nombre="   ").status_code, 400)

    def test_editar_descripcion_de_un_rol_del_sistema(self):
        rol = Rol.objects.get(nombre=Rol.FUNCIONARIO)
        r = self.client.patch(
            f"{self.url}{rol.pk}/", {"descripcion": "Registra actividades."}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        rol.refresh_from_db()
        self.assertEqual(rol.descripcion, "Registra actividades.")
        self.assertTrue(r.data["es_del_sistema"])
        self.assertTrue(
            Auditoria.objects.filter(entidad="rol", evento="editar", entidad_id=rol.pk).exists()
        )
        # Mandar el mismo nombre (como hace un PUT) no cuenta como renombrar.
        r = self.client.put(
            f"{self.url}{rol.pk}/",
            {"nombre": Rol.FUNCIONARIO, "descripcion": "Otra", "activo": True},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)

    def test_rechaza_renombrar_un_rol_del_sistema(self):
        rol = Rol.objects.get(nombre=Rol.ADMINISTRADOR)
        r = self.client.patch(f"{self.url}{rol.pk}/", {"nombre": "Superadmin"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "nombre")
        self.assertIn("no se puede renombrar", r.data["error"])
        rol.refresh_from_db()
        self.assertEqual(rol.nombre, Rol.ADMINISTRADOR)

    def test_rechaza_desactivar_un_rol_del_sistema(self):
        for nombre in Rol.TODOS:
            rol = Rol.objects.get(nombre=nombre)
            r = self.client.patch(f"{self.url}{rol.pk}/", {"activo": False}, format="json")
            self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST, nombre)
            self.assertEqual(r.data["campo"], "activo")
            self.assertIn("no se puede desactivar", r.data["error"])
            rol.refresh_from_db()
            self.assertTrue(rol.activo, nombre)

    def test_rol_nuevo_se_edita_desactiva_y_reactiva(self):
        pk = self.crear().data["id_rol"]
        r = self.client.patch(f"{self.url}{pk}/", {"nombre": "Coordinador zonal"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        r = self.client.patch(f"{self.url}{pk}/", {"activo": False}, format="json")
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertFalse(Rol.objects.get(pk=pk).activo)
        self.assertEqual(self.client.get(self.url, {"activo": "false"}).data["count"], 1)
        r = self.client.patch(f"{self.url}{pk}/", {"activo": True}, format="json")
        self.assertTrue(r.data["activo"])

    def test_no_hay_delete(self):
        rol = Rol.objects.get(nombre=Rol.ALCALDESA)
        r = self.client.delete(f"{self.url}{rol.pk}/")
        self.assertEqual(r.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Rol.objects.filter(pk=rol.pk, activo=True).exists())

    def test_listado_cuenta_usuarios_por_rol_sin_n_consultas(self):
        crear_funcionario()
        crear_usuario("otro.func@terriia.cl", 22222222, Rol.FUNCIONARIO)
        # count de la paginación + listado con annotate: no crece con la cantidad de roles
        with self.assertNumQueries(2):
            r = self.client.get(self.url, {"page_size": 50})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        cantidades = {fila["nombre"]: fila["cantidad_usuarios"] for fila in r.data["results"]}
        self.assertEqual(cantidades[Rol.ADMINISTRADOR], 1)
        self.assertEqual(cantidades[Rol.FUNCIONARIO], 2)
        self.assertEqual(cantidades[Rol.ALCALDESA], 0)

    def test_busqueda_por_nombre_o_descripcion(self):
        self.crear(descripcion="Coordina las juntas de vecinos")
        self.assertEqual(self.client.get(self.url, {"search": "coordinador"}).data["count"], 1)
        self.assertEqual(self.client.get(self.url, {"search": "juntas"}).data["count"], 1)

    def test_no_admin_recibe_403(self):
        self.client.force_authenticate(crear_funcionario())
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.crear().status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)


class RolDesactivadoTests(APITestCase):
    """Qué pasa con los usuarios cuando un rol nuevo se desactiva."""

    def setUp(self):
        cache.clear()  # reinicia el freno de intentos de login
        self.rol = Rol.objects.create(nombre="Coordinador comunal")
        self.usuario = crear_usuario("coordinador@terriia.cl", 13131313, self.rol)
        self.rol.activo = False
        self.rol.save(update_fields=["activo"])
        self.admin = crear_admin()

    def test_quien_ya_tiene_el_rol_sigue_entrando(self):
        r = self.client.post(
            "/api/auth/login/",
            {"email": "coordinador@terriia.cl", "password": CLAVE},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        self.assertEqual(r.data["rol"], "Coordinador comunal")
        self.assertEqual(self.client.get("/api/auth/yo/").status_code, status.HTTP_200_OK)

    def test_no_se_asigna_a_usuarios_nuevos_ni_por_cambio(self):
        self.client.force_authenticate(self.admin)
        r = self.client.post(
            "/api/usuarios/",
            {
                "email": "nuevo@terriia.cl",
                "rut": f"14141414-{calcular_dv(14141414)}",
                "password": CLAVE,
                "rol": self.rol.pk,
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data, {"error": "El rol que seleccionó no está activo.", "campo": "rol"})
        funcionario = crear_funcionario()
        r = self.client.patch(
            f"/api/usuarios/{funcionario.pk}/", {"rol": self.rol.pk}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(r.data["campo"], "rol")

    def test_quien_ya_lo_tiene_se_puede_seguir_editando(self):
        self.client.force_authenticate(self.admin)
        r = self.client.patch(
            f"/api/usuarios/{self.usuario.pk}/",
            {"first_name": "Camila", "rol": self.rol.pk},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)


class PantallaRolesTests(TestCase):
    def test_administrador_ve_la_pantalla(self):
        self.client.force_login(crear_admin())
        r = self.client.get(reverse("core_roles"))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, "organizacion/base.html")
        html = r.content.decode()
        for esperado in [
            'id="buscar"',
            "Exportar a Excel",
            "Usuarios con este rol",
            "sweetalert2@11.",
            "xlsx@0.18.5",
            "core/js/roles.js",
        ]:
            self.assertIn(esperado, html, esperado)
        self.assertEqual(html.count('aria-current="page"'), 1)  # Roles marcado en el menú

    def test_no_admin_recibe_403(self):
        self.client.force_login(crear_funcionario())
        self.assertEqual(self.client.get(reverse("core_roles")).status_code, 403)

    def test_anonimo_va_a_ingresar(self):
        r = self.client.get(reverse("core_roles"))
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("/ingresar/?next="), r["Location"])

    def test_roles_sale_en_el_menu_de_todas_las_pantallas(self):
        self.client.force_login(crear_admin())
        enlace = f'href="{reverse("core_roles")}"'
        for pantalla in ["org_inicio", "org_cargos", "territorio_vecinos", "core_roles"]:
            self.assertIn(enlace, self.client.get(reverse(pantalla)).content.decode(), pantalla)
