"""Listados: tamaño de página, orden, detalle y resumen (UX-01 a UX-03, REN-01)."""

from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status
from rest_framework.test import APITestCase

from organizacion.models import Cargo, Delegacion

from .utiles import crear_admin, crear_funcionario

DELEGACIONES, AREAS, CARGOS = "/api/delegaciones/", "/api/areas/", "/api/cargos/"
RESUMEN = "/api/organizacion/resumen/"


def crear_delegaciones(n):
    for i in range(1, n + 1):
        Delegacion.objects.create(codigo=f"D{i:02d}", nombre=f"Delegación {i}")


class PaginacionYOrdenTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(crear_admin())
        crear_delegaciones(23)  # UX-03: 23 registros en tres páginas de 10

    def test_pagina_por_defecto_es_de_20(self):
        r = self.client.get(DELEGACIONES)
        self.assertEqual(len(r.data["results"]), 20)
        self.assertEqual(r.data["count"], 23)

    def test_tamano_de_pagina_elegible(self):
        for tam in (10, 20, 50):
            r = self.client.get(DELEGACIONES, {"page_size": tam})
            self.assertEqual(len(r.data["results"]), min(tam, 23))

    def test_tres_paginas_de_diez_sin_duplicados_ni_omisiones(self):
        vistos = []
        for pagina in (1, 2, 3):
            r = self.client.get(DELEGACIONES, {"page_size": 10, "page": pagina})
            vistos += [x["codigo"] for x in r.data["results"]]
        self.assertEqual(len(vistos), 23)
        self.assertEqual(len(set(vistos)), 23)

    def test_tamano_maximo_es_100(self):
        for i in range(120):
            Delegacion.objects.create(codigo=f"X{i:03d}", nombre=f"Extra {i}")
        r = self.client.get(DELEGACIONES, {"page_size": 500})
        self.assertEqual(len(r.data["results"]), 100)

    def test_orden_por_columna_asc_y_desc(self):
        asc = self.client.get(DELEGACIONES, {"ordering": "codigo"}).data["results"]
        desc = self.client.get(DELEGACIONES, {"ordering": "-codigo"}).data["results"]
        self.assertEqual(asc[0]["codigo"], "D01")
        self.assertEqual(desc[0]["codigo"], "D23")

    def test_orden_por_cantidad_de_areas_no_falla(self):
        r = self.client.get(DELEGACIONES, {"ordering": "-n_areas,id_delegacion"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_orden_en_areas_y_cargos(self):
        r = self.client.get(AREAS, {"ordering": "delegacion__codigo,id_area"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        r = self.client.get(CARGOS, {"ordering": "-nombre,id_cargo"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_orden_y_filtro_se_combinan_con_la_pagina(self):
        r = self.client.get(
            DELEGACIONES,
            {"search": "delegación", "ordering": "-codigo", "page_size": 10, "page": 2},
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(len(r.data["results"]), 10)


class RendimientoTests(APITestCase):
    """REN-01: el listado no hace una consulta por fila."""

    def setUp(self):
        self.client.force_authenticate(crear_admin())

    def consultas(self, url, parametros=None):
        with CaptureQueriesContext(connection) as c:
            r = self.client.get(url, parametros or {})
        self.assertEqual(r.status_code, 200)
        return len(c)

    def test_consultas_de_delegaciones_no_crecen_con_las_filas(self):
        crear_delegaciones(2)
        pocas = self.consultas(DELEGACIONES)
        for i in range(30, 50):
            Delegacion.objects.create(codigo=f"Z{i}", nombre=f"Zona {i}")
        muchas = self.consultas(DELEGACIONES)
        self.assertEqual(pocas, muchas)

    def test_consultas_de_areas_y_cargos_no_crecen_con_las_filas(self):
        crear_delegaciones(1)
        area = Delegacion.objects.first().areas.first()
        Cargo.objects.create(nombre="Uno", area=area)
        a1, c1 = self.consultas(AREAS), self.consultas(CARGOS)
        for i in range(8):
            d = Delegacion.objects.create(codigo=f"Q{i}", nombre=f"Q {i}")
            Cargo.objects.create(nombre=f"Cargo {d.codigo}", area=d.areas.first())
        self.assertEqual(a1, self.consultas(AREAS))
        self.assertEqual(c1, self.consultas(CARGOS))

    def test_listado_grande_responde_completo(self):
        crear_delegaciones(300)
        r = self.client.get(DELEGACIONES, {"page_size": 100, "page": 3})
        self.assertEqual(r.data["count"], 300)
        self.assertEqual(len(r.data["results"]), 100)


class DetalleYResumenTests(APITestCase):
    def setUp(self):
        self.client.force_authenticate(crear_admin())
        self.d = Delegacion.objects.create(codigo="D01", nombre="Centro")
        social = self.d.areas.get(tipo="social")
        Cargo.objects.create(nombre="Trabajador social", area=social)
        Cargo.objects.create(nombre="Asistente social", area=social)
        Cargo.objects.create(nombre="Secretaria", area=None)

    def test_detalle_trae_cuatro_areas_con_sus_cargos(self):
        r = self.client.get(f"{DELEGACIONES}{self.d.pk}/detalle/")
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["codigo"], "D01")
        self.assertEqual([a["prioridad"] for a in r.data["areas"]], [1, 2, 3, 4])
        social = r.data["areas"][0]
        self.assertEqual(social["tipo"], "social")
        nombres = [c["nombre"] for c in social["cargos"]]
        self.assertEqual(nombres, ["Asistente social", "Trabajador social"])
        self.assertEqual(r.data["areas"][1]["cargos"], [])

    def test_detalle_de_delegacion_inexistente(self):
        self.assertEqual(self.client.get(f"{DELEGACIONES}9999/detalle/").status_code, 404)

    def test_detalle_denegado_a_no_administrador(self):
        self.client.force_authenticate(crear_funcionario())
        self.assertEqual(self.client.get(f"{DELEGACIONES}{self.d.pk}/detalle/").status_code, 403)

    def test_resumen(self):
        self.client.delete(f"{AREAS}{self.d.areas.get(tipo='operativa').pk}/")
        r = self.client.get(RESUMEN)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data["delegaciones"], {"total": 1, "activas": 1, "inactivas": 0})
        self.assertEqual(r.data["areas"], {"total": 4, "activas": 3, "inactivas": 1})
        self.assertEqual(
            r.data["cargos"], {"total": 3, "vigentes": 3, "transversales": 1, "no_vigentes": 0}
        )

    def test_resumen_solo_administrador_y_con_sesion(self):
        self.client.force_authenticate(crear_funcionario())
        self.assertEqual(self.client.get(RESUMEN).status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(RESUMEN).status_code, (401, 403))
