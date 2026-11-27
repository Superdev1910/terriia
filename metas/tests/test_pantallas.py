"""Pruebas de acceso a las pantallas HTML de metas (períodos, ítems y metas)."""

from django.test import TestCase
from django.urls import reverse

from core.models import Rol
from metas.models import Periodo
from organizacion.models import Cargo, Delegacion
from personas.models import Funcionario, Usuario

PANTALLAS_ADMIN = [
    ("metas_periodos", "periodos"),
    ("metas_items", "items"),
    ("metas_delegacion", "metas-delegacion"),
    ("metas_individuales", "metas"),
    ("metas_felicitaciones", "felicitaciones-reclamos"),
]
PANTALLAS = PANTALLAS_ADMIN


def crear_usuario(email, rut, rol):
    return Usuario.objects.create_user(
        email=email, rut=rut, password="ClaveSegura#2026", rol=Rol.objects.get(nombre=rol)
    )


class PantallasMetasTests(TestCase):
    def setUp(self):
        self.admin = crear_usuario("admin@terriia.cl", "11.111.111-1", Rol.ADMINISTRADOR)
        self.funcionario = crear_usuario("func@terriia.cl", "12.345.678-5", Rol.FUNCIONARIO)

    def test_administrador_ve_cada_pantalla(self):
        self.client.force_login(self.admin)
        for nombre, entidad in PANTALLAS:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 200, nombre)
            self.assertTemplateUsed(r, "metas/mantenedor.html")
            esperado = f'<script id="entidad" type="application/json">"{entidad}"</script>'
            self.assertContains(r, esperado)

    def test_no_administrador_recibe_403(self):
        self.client.force_login(self.funcionario)
        for nombre, _ in PANTALLAS:
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 403, nombre)

    def test_anonimo_es_enviado_al_login(self):
        for nombre, _ in PANTALLAS:
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)
            self.assertTrue(r["Location"].startswith("/ingresar/?next="), r["Location"])

    def test_pantalla_trae_busqueda_paginador_excel_y_sweetalert(self):
        self.client.force_login(self.admin)
        html = self.client.get(reverse("metas_items")).content.decode()
        for esperado in [
            'id="buscar"',
            'id="paginador"',
            "Exportar a Excel",
            "xlsx",
            "sweetalert2",
        ]:
            self.assertIn(esperado, html, esperado)

    def test_menu_lateral_lleva_a_metas_desde_todas_las_pantallas(self):
        self.client.force_login(self.admin)
        metas = self.client.get(reverse("metas_periodos")).content.decode()
        territorio = self.client.get(reverse("territorio_vecinos")).content.decode()
        organizacion = self.client.get(reverse("org_cargos")).content.decode()
        for html in (metas, territorio, organizacion):
            for nombre, _ in PANTALLAS:
                self.assertIn(f'href="{reverse(nombre)}"', html, nombre)
            self.assertIn(f'href="{reverse("org_cargos")}"', html)
        self.assertEqual(metas.count('aria-current="page"'), 1)


class PantallasCumplimientoTests(TestCase):
    """Cumplimiento por delegación, Mi cumplimiento y Felicitaciones y reclamos."""

    ROLES_DELEGACION = {
        Rol.ADMINISTRADOR,
        Rol.JEFE_DELEGACIONES,
        Rol.ALCALDESA,
        Rol.DELEGADO_TERRITORIAL,
        Rol.ENCARGADO_AREA,
    }

    def setUp(self):
        self.centro = Delegacion.objects.create(codigo="CEN", nombre="Centro")
        self.norte = Delegacion.objects.create(codigo="NOR", nombre="Norte")
        self.periodo = Periodo.objects.create(
            fecha_inicio="2026-01-01", fecha_termino="2026-03-31", estado=Periodo.VIGENTE
        )
        cargo = Cargo.objects.create(nombre="Territorial")
        ficha = Funcionario.objects.create(
            identificador_inst="F-1", nombre="Ana", cargo=cargo, delegacion=self.centro
        )
        self.usuarios = {}
        for i, rol in enumerate(Rol.objects.values_list("nombre", flat=True)):
            self.usuarios[rol] = Usuario.objects.create_user(
                email=f"u{i}@terriia.cl",
                rut=f"{20 + i}.000.00{i}-0",
                password="ClaveSegura#2026",
                rol=Rol.objects.get(nombre=rol),
                delegacion=self.centro if rol != Rol.ADMINISTRADOR else None,
                funcionario=ficha if rol == Rol.FUNCIONARIO else None,
            )

    def entrar(self, rol):
        self.client.force_login(self.usuarios[rol])

    def enlaces(self, rol):
        self.entrar(rol)
        # Una página que ese rol sí puede abrir, para leer su menú lateral.
        propia = (
            "metas_mi_cumplimiento" if rol == Rol.FUNCIONARIO else "metas_cumplimiento_delegacion"
        )
        html = self.client.get(reverse(propia)).content.decode()
        return {
            nombre: f'href="{reverse(nombre)}"' in html
            for nombre in (
                "metas_cumplimiento_delegacion",
                "metas_mi_cumplimiento",
                "metas_felicitaciones",
            )
        }

    def test_cumplimiento_delegacion_por_rol(self):
        for rol in self.usuarios:
            self.entrar(rol)
            r = self.client.get(reverse("metas_cumplimiento_delegacion"))
            esperado = 200 if rol in self.ROLES_DELEGACION else 403
            self.assertEqual(r.status_code, esperado, rol)
            if esperado == 200:
                self.assertTemplateUsed(r, "metas/cumplimiento.html")

    def test_delegado_y_encargado_quedan_fijos_en_su_delegacion(self):
        for rol in (Rol.DELEGADO_TERRITORIAL, Rol.ENCARGADO_AREA):
            self.entrar(rol)
            config = self.client.get(reverse("metas_cumplimiento_delegacion")).context[
                "config_cumplimiento"
            ]
            self.assertEqual([d["id"] for d in config["delegaciones"]], [self.centro.pk], rol)
        self.entrar(Rol.JEFE_DELEGACIONES)
        config = self.client.get(reverse("metas_cumplimiento_delegacion")).context[
            "config_cumplimiento"
        ]
        self.assertEqual(len(config["delegaciones"]), 2)

    def test_mi_cumplimiento_solo_funcionario(self):
        for rol in self.usuarios:
            self.entrar(rol)
            r = self.client.get(reverse("metas_mi_cumplimiento"))
            self.assertEqual(r.status_code, 200 if rol == Rol.FUNCIONARIO else 403, rol)
        self.entrar(Rol.FUNCIONARIO)
        config = self.client.get(reverse("metas_mi_cumplimiento")).context["config_cumplimiento"]
        self.assertEqual(config["funcionario_id"], self.usuarios[Rol.FUNCIONARIO].funcionario_id)
        self.assertEqual(config["modo"], "propio")

    def test_felicitaciones_solo_administrador(self):
        for rol in self.usuarios:
            self.entrar(rol)
            r = self.client.get(reverse("metas_felicitaciones"))
            self.assertEqual(r.status_code, 200 if rol == Rol.ADMINISTRADOR else 403, rol)

    def test_anonimo_es_enviado_al_login(self):
        for nombre in (
            "metas_cumplimiento_delegacion",
            "metas_mi_cumplimiento",
            "metas_felicitaciones",
        ):
            r = self.client.get(reverse(nombre))
            self.assertEqual(r.status_code, 302, nombre)
            self.assertTrue(r["Location"].startswith("/ingresar/?next="), r["Location"])

    def test_menu_muestra_cada_entrada_solo_a_su_rol(self):
        for rol in self.usuarios:
            esperado = {
                "metas_cumplimiento_delegacion": rol in self.ROLES_DELEGACION,
                "metas_mi_cumplimiento": rol == Rol.FUNCIONARIO,
                "metas_felicitaciones": rol == Rol.ADMINISTRADOR,
            }
            self.assertEqual(self.enlaces(rol), esperado, rol)
