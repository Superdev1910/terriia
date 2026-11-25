"""Alcance por rol y por delegación del seguimiento de actividades, filtros, resumen y listas
del formulario de asignación. Los permisos se prueban contra la API, no contra el menú."""

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase

from organizacion.models import Area

from .utiles_seguimiento import PNG, RAPIDO, EscenarioSolicitudesMixin, MediaTemporalMixin


def ids(respuesta):
    return {f["id_actividad"] for f in respuesta.data["results"]}


@RAPIDO
class AlcanceTests(EscenarioSolicitudesMixin, APITestCase):
    def setUp(self):
        self.preparar_escenario()
        self.de_ana = self.crear_actividad(self.ana)
        self.de_luis = self.crear_actividad(self.luis)
        self.de_pedro = self.crear_actividad(self.pedro, item=self.item_norte)
        self.asignada_a_luis = self.crear_actividad(self.ana, responsable=self.luis)

    def listar(self, usuario, **filtros):
        self.client.force_authenticate(usuario)
        return self.client.get("/api/actividades/", filtros)

    def test_administrador_ve_todo(self):
        self.assertEqual(
            ids(self.listar(self.admin)),
            {self.de_ana.pk, self.de_luis.pk, self.de_pedro.pk, self.asignada_a_luis.pk},
        )

    def test_delegado_ve_solo_su_delegacion(self):
        self.assertEqual(
            ids(self.listar(self.delegado)),
            {self.de_ana.pk, self.de_luis.pk, self.asignada_a_luis.pk},
        )
        self.assertEqual(ids(self.listar(self.delegado_norte)), {self.de_pedro.pk})
        self.assertEqual(self.client.get(self.url(self.de_ana)).status_code, 404)

    def test_funcionario_ve_las_que_escribio_o_le_asignaron(self):
        """HU02: la persona a quien se asigna una actividad la ve en su lista."""
        self.assertEqual(
            ids(self.listar(self.usuario_ana)), {self.de_ana.pk, self.asignada_a_luis.pk}
        )
        self.assertEqual(
            ids(self.listar(self.usuario_luis)), {self.de_luis.pk, self.asignada_a_luis.pk}
        )
        self.assertEqual(ids(self.listar(self.usuario_pedro)), {self.de_pedro.pk})

    def test_funcionario_no_abre_la_de_otro(self):
        self.client.force_authenticate(self.usuario_ana)
        self.assertEqual(self.client.get(self.url(self.de_luis)).status_code, 404)
        self.assertEqual(self.client.get(self.url(self.de_pedro)).status_code, 404)

    def test_anonimo_no_entra(self):
        self.client.force_authenticate(None)
        self.assertIn(self.client.get("/api/actividades/").status_code, (401, 403))

    def test_alcaldesa_solo_consulta_no_opera(self):
        self.assertEqual(self.listar(self.alcaldesa).status_code, status.HTTP_200_OK)
        self.client.force_authenticate(self.alcaldesa)
        r = self.client.post(self.url(self.de_ana, "comentarios"), {"texto": "Hola"}, format="json")
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)
        r = self.client.post(self.url(self.de_ana, "cambiar-estado"), {"estado": "Pendiente"})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_delegado_sin_delegacion_no_entra(self):
        sin = self.crear_usuario("sin.deleg@terriia.cl", 99999999, "Delegado territorial")
        self.assertEqual(self.listar(sin).status_code, 403)

    def test_busqueda_y_filtros(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get("/api/actividades/?search=Pedro")
        self.assertEqual(ids(r), {self.de_pedro.pk})
        r = self.client.get(f"/api/actividades/?responsable={self.luis.pk}")
        self.assertEqual(ids(r), {self.asignada_a_luis.pk})
        r = self.client.get("/api/actividades/?estado=Realizado")
        self.assertEqual(ids(r), set())

    def test_paginacion_con_tamano_elegido(self):
        self.client.force_authenticate(self.admin)
        r = self.client.get("/api/actividades/?page_size=2")
        self.assertEqual((r.data["count"], len(r.data["results"])), (4, 2))
        self.assertIsNotNone(r.data["next"])

    def test_resumen_respeta_el_alcance(self):
        self.vencida()  # de Ana, vencida
        self.client.force_authenticate(self.delegado_norte)
        r = self.client.get("/api/actividades/resumen/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data["total"], r.data["vencidas"]), (1, 0))
        self.client.force_authenticate(self.admin)
        r = self.client.get("/api/actividades/resumen/")
        self.assertEqual((r.data["total"], r.data["vencidas"]), (5, 1))
        self.assertEqual(r.data["por_estado"]["Ingresado"], 5)


@RAPIDO
class OpcionesSeguimientoTests(EscenarioSolicitudesMixin, APITestCase):
    def setUp(self):
        self.preparar_escenario()
        self.a = self.crear_actividad()

    def pedir(self, usuario, actividad=None):
        self.client.force_authenticate(usuario)
        return self.client.get(self.url(actividad or self.a, "opciones-seguimiento"))

    def test_delegado_recibe_areas_y_responsables_de_su_delegacion(self):
        r = self.pedir(self.delegado)
        self.assertEqual(r.status_code, 200)
        nombres = {f["nombre"] for f in r.data["responsables"]}
        self.assertEqual(nombres, {"Ana Pérez", "Luis Rojas", "Marta Díaz"})
        self.assertEqual(len(r.data["areas"]), Area.objects.filter(delegacion=self.centro).count())
        self.assertEqual(r.data["transiciones"]["Realizado"], [])
        self.assertEqual(
            sorted(r.data["transiciones"]["Ingresado"]),
            sorted(["Pendiente", "En proceso", "Realizado"]),
        )

    def test_funcionario_no_recibe_listas_de_asignacion(self):
        r = self.pedir(self.usuario_ana)
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.data["areas"], r.data["responsables"]), ([], []))

    def test_otra_delegacion_no_las_ve(self):
        self.assertEqual(self.pedir(self.delegado_norte).status_code, 404)


@RAPIDO
class EvidenciaDelResponsableTests(MediaTemporalMixin, EscenarioSolicitudesMixin, APITestCase):
    """HU04 ya existe en atenciones; aquí solo se prueba lo que agrega HU02: el responsable
    asignado puede ver y adjuntar evidencia de la actividad."""

    def setUp(self):
        super().setUp()
        self.preparar_escenario()
        self.a = self.crear_actividad(responsable=self.luis)

    def subir(self, usuario):
        self.client.force_authenticate(usuario)
        foto = SimpleUploadedFile("foto.png", PNG, content_type="image/png")
        return self.client.post(
            "/api/evidencias/", {"actividad": self.a.pk, "archivo": foto}, format="multipart"
        )

    def test_responsable_sube_y_descarga(self):
        r = self.subir(self.usuario_luis)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(r.data["codigo_verificador"]), 6)
        bajada = self.client.get(r.data["descarga"])
        self.assertEqual(bajada.status_code, 200)

    def test_otro_funcionario_no_sube_ni_descarga(self):
        r = self.subir(self.usuario_luis)
        self.client.force_authenticate(self.usuario_pedro)
        self.assertEqual(self.client.get(r.data["descarga"]).status_code, 403)
        foto = SimpleUploadedFile("foto.png", PNG, content_type="image/png")
        r = self.client.post(
            "/api/evidencias/", {"actividad": self.a.pk, "archivo": foto}, format="multipart"
        )
        self.assertIn(r.status_code, (400, 403))
