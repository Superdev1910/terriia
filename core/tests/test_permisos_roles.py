"""Pruebas de los permisos por perfil: Delegado territorial y Funcionario. Datos ficticios."""

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Rol
from core.validators import calcular_dv
from metas.tests.datos_base import DatosMetasMixin
from organizacion.models import Area
from personas.models import Funcionario, Usuario
from territorio.models import Territorio


def ids(respuesta, campo):
    datos = respuesta.data
    filas = datos["results"] if isinstance(datos, dict) and "results" in datos else datos
    return {fila[campo] for fila in filas}


class EscenarioRolesMixin(DatosMetasMixin):
    """Dos delegaciones (Centro y Norte), un Delegado de Centro y un Funcionario (Ana)."""

    def preparar_escenario(self):
        self.preparar_datos()
        self.area_centro = Area.objects.filter(delegacion=self.centro).first()
        self.area_norte = Area.objects.filter(delegacion=self.norte).first()
        self.cargo.area = self.area_centro
        self.cargo.save()
        self.pedro = self.crear_funcionario("F-0003", "Pedro Soto", self.norte)

        self.t_centro = Territorio.objects.create(delegacion=self.centro, nombre="Plaza")
        self.t_norte = Territorio.objects.create(delegacion=self.norte, nombre="Cerro")

        self.md_centro = self.crear_meta_delegacion("100.00", delegacion=self.centro)
        self.md_norte = self.crear_meta_delegacion("100.00", delegacion=self.norte)
        self.meta_ana = self.crear_meta(self.md_centro, self.ana)
        self.meta_pedro = self.crear_meta(self.md_norte, self.pedro)

        self.delegado = self.crear_usuario(
            "delegado@terriia.cl",
            f"22222222-{calcular_dv(22222222)}",
            Rol.DELEGADO_TERRITORIAL,
            delegacion=self.centro,
        )
        self.delegado_sin_delegacion = self.crear_usuario(
            "delegado2@terriia.cl", f"33333333-{calcular_dv(33333333)}", Rol.DELEGADO_TERRITORIAL
        )
        self.usuario_ana = self.crear_usuario(
            "ana@terriia.cl",
            f"44444444-{calcular_dv(44444444)}",
            Rol.FUNCIONARIO,
            funcionario=self.ana,
        )
        self.usuario_sin_ficha = self.crear_usuario(
            "sinficha@terriia.cl", f"55555555-{calcular_dv(55555555)}", Rol.FUNCIONARIO
        )

    def crear_usuario(self, email, rut, rol, **extra):
        return Usuario.objects.create_user(
            email=email,
            rut=rut,
            password="ClaveSegura#2026",
            rol=Rol.objects.get(nombre=rol),
            **extra,
        )


class DelegadoApiTests(EscenarioRolesMixin, APITestCase):
    def setUp(self):
        self.preparar_escenario()
        self.client.force_authenticate(self.delegado)

    def test_lista_solo_territorios_de_su_delegacion(self):
        r = self.client.get("/api/territorios/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(ids(r, "id_territorio"), {self.t_centro.pk})

    def test_no_ve_territorio_de_otra_delegacion(self):
        r = self.client.get(f"/api/territorios/{self.t_norte.pk}/")
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_crea_territorio_en_su_delegacion(self):
        r = self.client.post("/api/territorios/", {"delegacion": self.centro.pk, "nombre": "Nuevo"})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)

    def test_no_crea_territorio_en_otra_delegacion(self):
        r = self.client.post("/api/territorios/", {"delegacion": self.norte.pk, "nombre": "Nuevo"})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Territorio.objects.filter(nombre="Nuevo").exists())

    def test_no_mueve_territorio_a_otra_delegacion(self):
        r = self.client.patch(
            f"/api/territorios/{self.t_centro.pk}/", {"delegacion": self.norte.pk}
        )
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        self.t_centro.refresh_from_db()
        self.assertEqual(self.t_centro.delegacion_id, self.centro.pk)

    def test_sin_delegacion_asignada_no_accede(self):
        self.client.force_authenticate(self.delegado_sin_delegacion)
        for url in ("/api/territorios/", "/api/funcionarios/", "/api/metas/", "/api/cargos/"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, url)

    def test_catalogos_solo_lectura_y_filtrados(self):
        r = self.client.get("/api/areas/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(
            ids(r, "id_area"),
            set(Area.objects.filter(delegacion=self.centro).values_list("pk", flat=True)),
        )
        r = self.client.post("/api/cargos/", {"nombre": "Otro", "area": self.area_centro.pk})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        r = self.client.patch(f"/api/delegaciones/{self.centro.pk}/", {"nombre": "Cambio"})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_periodos_visibles_globalmente(self):
        r = self.client.get("/api/periodos/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(ids(r, "id_periodo"), {self.periodo.pk})

    def test_no_gestiona_usuarios(self):
        r = self.client.get("/api/usuarios/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_lista_solo_funcionarios_de_su_delegacion(self):
        r = self.client.get("/api/funcionarios/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(ids(r, "id_funcionario"), {self.ana.pk, self.luis.pk})

    def test_no_mueve_funcionario_a_otra_delegacion(self):
        r = self.client.patch(f"/api/funcionarios/{self.ana.pk}/", {"delegacion": self.norte.pk})
        self.assertIn(r.status_code, (status.HTTP_400_BAD_REQUEST, status.HTTP_403_FORBIDDEN))
        self.ana.refresh_from_db()
        self.assertEqual(self.ana.delegacion_id, self.centro.pk)

    def test_lista_solo_metas_de_su_delegacion(self):
        r = self.client.get("/api/metas/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(ids(r, "id_meta"), {self.meta_ana.pk})
        r = self.client.get("/api/metas-delegacion/")
        self.assertEqual(ids(r, "id_meta_delegacion"), {self.md_centro.pk})

    def test_no_recalibra_meta_de_otra_delegacion(self):
        r = self.client.post(
            f"/api/metas/{self.meta_pedro.pk}/recalibrar/",
            {"valor_nuevo": "10.00", "motivo": "Ajuste"},
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_no_usa_mi_perfil(self):
        r = self.client.get("/api/mi-perfil/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)


class FuncionarioApiTests(EscenarioRolesMixin, APITestCase):
    def setUp(self):
        self.preparar_escenario()
        self.client.force_authenticate(self.usuario_ana)

    def test_mi_perfil_devuelve_sus_datos_y_metas(self):
        r = self.client.get("/api/mi-perfil/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["funcionario"]["identificador_inst"], "F-0001")
        self.assertEqual(r.data["funcionario"]["delegacion"], "Centro")
        self.assertEqual(len(r.data["metas"]), 1)
        self.assertEqual(r.data["metas"][0]["valor_objetivo"], "40.00")

    def test_sin_ficha_no_accede_a_mi_perfil(self):
        self.client.force_authenticate(self.usuario_sin_ficha)
        r = self.client.get("/api/mi-perfil/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_ficha_inactiva_no_accede_a_mi_perfil(self):
        self.ana.estado = Funcionario.INACTIVO
        self.ana.save()
        r = self.client.get("/api/mi-perfil/")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_solo_ve_su_propia_ficha_y_no_edita(self):
        r = self.client.get("/api/funcionarios/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(ids(r, "id_funcionario"), {self.ana.pk})
        r = self.client.patch(f"/api/funcionarios/{self.ana.pk}/", {"nombre": "Otra"})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_no_accede_a_mantenedores(self):
        for url in ("/api/territorios/", "/api/metas/", "/api/cargos/", "/api/usuarios/"):
            r = self.client.get(url)
            self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN, url)


class PantallasPorRolTests(EscenarioRolesMixin, APITestCase):
    def setUp(self):
        self.preparar_escenario()

    def nombres_menu(self, respuesta):
        return {item[0] for _, paginas in respuesta.context["menu_secciones"] for item in paginas}

    def test_delegado_ve_sus_pantallas(self):
        self.client.force_login(self.delegado)
        for nombre in ("territorio_territorios", "personas_funcionarios", "metas_individuales"):
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 200, nombre)
        self.assertNotIn("personas_usuarios", self.nombres_menu(r))
        self.assertNotIn("personas_mi_perfil", self.nombres_menu(r))

    def test_delegado_no_ve_pantallas_de_administrador(self):
        self.client.force_login(self.delegado)
        for nombre in ("personas_usuarios", "personas_mi_perfil"):
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 403, nombre)

    def test_funcionario_solo_ve_mi_perfil(self):
        self.client.force_login(self.usuario_ana)
        r = self.client.get(reverse("personas_mi_perfil"))
        self.assertEqual(r.status_code, 200)
        # SCRUM-62: además de su perfil, el funcionario registra y consulta sus actividades.
        self.assertEqual(
            self.nombres_menu(r),
            {
                "personas_mi_perfil",
                "metas_mi_cumplimiento",
                "atenciones_registrar",
                "atenciones_mis_registros",
                "atenciones_seguimiento",
            },
        )
        for nombre in ("personas_funcionarios", "territorio_territorios", "metas_individuales"):
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 403, nombre)

    def test_administrador_no_tiene_mi_perfil_en_menu(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse("personas_usuarios"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("personas_usuarios", self.nombres_menu(r))
        self.assertNotIn("personas_mi_perfil", self.nombres_menu(r))
