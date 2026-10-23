from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria

from ..models import SubAtencion, TipoAtencion
from .utiles import crear_admin, crear_funcionario


class SubAtencionTests(APITestCase):
    url = "/api/sub-atenciones/"

    def setUp(self):
        self.client.force_authenticate(crear_admin())
        # DISERCO para no mezclarse con la semilla del área Social.
        self.tipo = TipoAtencion.objects.create(area="DISERCO", nombre="Mantención vial")

    def datos(self, **extra):
        data = {"tipo_atencion": self.tipo.pk, "nombre": "Bacheo"}
        data.update(extra)
        return data

    def crear(self, **extra):
        response = self.client.post(self.url, self.datos(**extra), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data["id_sub_atencion"]

    def test_crear(self):
        response = self.client.post(self.url, self.datos(nombre=" Bacheo "), format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["nombre"], "Bacheo")
        self.assertEqual(response.data["tipo_atencion_nombre"], "Mantención vial")
        self.assertEqual(response.data["area"], "DISERCO")
        self.assertTrue(response.data["activo"])
        pk = response.data["id_sub_atencion"]
        self.assertTrue(
            Auditoria.objects.filter(entidad="sub_atencion", evento="crear", entidad_id=pk).exists()
        )

    def test_editar(self):
        pk = self.crear()
        otro_tipo = TipoAtencion.objects.create(area="DISERCO", nombre="Aseo")
        response = self.client.patch(
            f"{self.url}{pk}/",
            {"tipo_atencion": otro_tipo.pk, "nombre": "Limpieza de veredas"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        sub = SubAtencion.objects.get(pk=pk)
        self.assertEqual((sub.tipo_atencion, sub.nombre), (otro_tipo, "Limpieza de veredas"))
        self.assertTrue(
            Auditoria.objects.filter(
                entidad="sub_atencion", evento="editar", entidad_id=pk
            ).exists()
        )

    def test_rechaza_duplicado_e_invalidos(self):
        self.crear()
        response = self.client.post(self.url, self.datos(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["campo"], "nombre")
        for invalido in (self.datos(nombre=" "), self.datos(tipo_atencion=99999), {}):
            self.assertEqual(
                self.client.post(self.url, invalido, format="json").status_code,
                status.HTTP_400_BAD_REQUEST,
                invalido,
            )

    def test_rechaza_duplicado_con_otras_mayusculas(self):
        self.crear()
        response = self.client.post(self.url, self.datos(nombre="BACHEO"), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["campo"], "nombre")
        # También con tildes: en SQLite «Ñ»/«É» no se igualan con iexact.
        self.crear(nombre="Señalética")
        response = self.client.post(self.url, self.datos(nombre="SEÑALÉTICA"), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mismo_nombre_en_otro_tipo_se_permite(self):
        self.crear()
        otro_tipo = TipoAtencion.objects.create(area="Seguridad", nombre="Patrullaje")
        self.crear(tipo_atencion=otro_tipo.pk)

    def test_desactivar(self):
        pk = self.crear()
        self.assertEqual(
            self.client.delete(f"{self.url}{pk}/").status_code, status.HTTP_204_NO_CONTENT
        )
        self.assertFalse(SubAtencion.objects.get(pk=pk).activo)  # no se borra
        self.assertTrue(
            Auditoria.objects.filter(
                entidad="sub_atencion", evento="desactivar", entidad_id=pk
            ).exists()
        )

    def test_acceso_denegado(self):
        self.client.force_authenticate(crear_funcionario())
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.post(self.url, self.datos(), format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_no_se_crea_bajo_un_tipo_inactivo(self):
        self.client.delete(f"/api/tipos-atencion/{self.tipo.pk}/")
        response = self.client.post(self.url, self.datos(), format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["campo"], "tipo_atencion")
        self.assertFalse(SubAtencion.objects.filter(nombre="Bacheo").exists())

    def test_no_se_mueve_a_un_tipo_inactivo_pero_se_puede_editar(self):
        pk = self.crear()
        inactivo = TipoAtencion.objects.create(area="DISERCO", nombre="Antiguo", activo=False)
        response = self.client.patch(
            f"{self.url}{pk}/", {"tipo_atencion": inactivo.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Si su propio tipo se desactiva después, la sub atención se puede seguir editando.
        self.client.delete(f"/api/tipos-atencion/{self.tipo.pk}/")
        response = self.client.patch(
            f"{self.url}{pk}/", self.datos(nombre="Bacheo menor"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

    def test_filtros_por_area_tipo_estado_y_busqueda(self):
        self.crear()
        inactiva = self.crear(nombre="Demarcación")
        self.client.delete(f"{self.url}{inactiva}/")
        seguridad = TipoAtencion.objects.create(area="Seguridad", nombre="Patrullaje")
        self.crear(tipo_atencion=seguridad.pk, nombre="Ronda nocturna")

        def contar(**filtros):
            return self.client.get(self.url, filtros).data["count"]

        self.assertEqual(contar(area="DISERCO"), 2)
        self.assertEqual(contar(area="Seguridad"), 1)
        self.assertEqual(contar(area="Social"), 1)  # la semilla: Orientación social
        self.assertEqual(contar(tipo_atencion=self.tipo.pk), 2)
        self.assertEqual(contar(tipo_atencion=self.tipo.pk, activo="true"), 1)
        self.assertEqual(contar(search="Patrullaje"), 1)  # busca también por el tipo
        self.assertEqual(
            self.client.get(self.url, {"area": "Otra"}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
