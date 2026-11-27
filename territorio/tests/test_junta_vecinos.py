from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from core.models import Auditoria
from organizacion.models import Delegacion

from ..models import JuntaVecinos, Territorio
from .utiles import crear_admin, crear_funcionario, crear_funcionario_con_delegacion
from core.models import Rol


class JuntaVecinosTests(APITestCase):
    url = "/api/juntas-vecinos/"

    def setUp(self):
        self.client.force_authenticate(crear_admin())
        delegacion = Delegacion.objects.create(codigo="D98", nombre="Norte de prueba")
        self.territorio = Territorio.objects.create(delegacion=delegacion, nombre="Barrio Uno")

    def datos(self, **extra):
        data = {
            "territorio": self.territorio.pk,
            "numero_registro": "JV-001",
            "nombre": "Junta Barrio Uno",
            "presidente": "Ana Pérez",
            "telefono": "+56912345678",
            "email": "junta@example.com",
        }
        data.update(extra)
        return data

    def test_crear_editar_auditar_y_desactivar(self):
        response = self.client.post(self.url, self.datos())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        pk = response.data["id_junta_vecinos"]
        self.assertTrue(
            Auditoria.objects.filter(
                entidad="junta_vecinos", evento="crear", entidad_id=pk
            ).exists()
        )
        self.assertEqual(
            self.client.patch(f"{self.url}{pk}/", {"nombre": "Junta actualizada"}).status_code,
            status.HTTP_200_OK,
        )
        self.assertTrue(
            Auditoria.objects.filter(
                entidad="junta_vecinos", evento="editar", entidad_id=pk
            ).exists()
        )
        self.assertEqual(
            self.client.delete(f"{self.url}{pk}/").status_code, status.HTTP_204_NO_CONTENT
        )
        self.assertFalse(JuntaVecinos.objects.get(pk=pk).activa)

    def test_rechaza_obligatorios_duplicados_y_territorio_inactivo(self):
        self.assertEqual(
            self.client.post(self.url, {"territorio": self.territorio.pk}).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertEqual(
            self.client.post(self.url, self.datos()).status_code, status.HTTP_201_CREATED
        )
        self.assertEqual(
            self.client.post(self.url, self.datos(nombre="Otra junta")).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.territorio.activo = False
        self.territorio.save(update_fields=["activo"])
        self.assertEqual(
            self.client.post(self.url, self.datos(numero_registro="JV-002")).status_code,
            status.HTTP_400_BAD_REQUEST,
        )

    def test_rechaza_territorio_inexistente_y_negativo(self):
        for territorio in (99999, -6):
            response = self.client.post(
                self.url, self.datos(territorio=territorio, numero_registro=f"JV-{territorio}")
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(response.data["campo"], "territorio")

    def test_busqueda_filtro_paginacion_relacion_y_rol(self):
        self.client.post(self.url, self.datos())
        self.assertEqual(self.client.get(self.url, {"search": "JV-001"}).data["count"], 1)
        self.assertEqual(
            self.client.get(
                self.url, {"territorio": self.territorio.pk, "activa": "true", "page_size": 1}
            ).data["count"],
            1,
        )
        self.assertEqual(
            self.client.post(
                self.url, {"territorio": 99999, "numero_registro": "JV-002", "nombre": "Inválida"}
            ).status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.client.force_authenticate(crear_funcionario())
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)

    def test_sin_autenticacion_denegado(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN)


class JuntaVecinosFuncionarioTests(APITestCase):
    url = "/api/juntas-vecinos/"

    def setUp(self):
        propia = Delegacion.objects.create(codigo="D91", nombre="Propia")
        ajena = Delegacion.objects.create(codigo="D92", nombre="Ajena")
        self.t_propio = Territorio.objects.create(delegacion=propia, nombre="Propio")
        self.t_ajeno = Territorio.objects.create(delegacion=ajena, nombre="Ajeno")
        self.j_propia = JuntaVecinos.objects.create(
            territorio=self.t_propio, numero_registro="P-1", nombre="Propia"
        )
        self.j_ajena = JuntaVecinos.objects.create(
            territorio=self.t_ajeno, numero_registro="A-1", nombre="Ajena"
        )
        self.usuario = crear_funcionario_con_delegacion(propia)
        self.client.force_authenticate(self.usuario)

    def datos(self, territorio, registro):
        return {"territorio": territorio.pk, "numero_registro": registro, "nombre": registro}

    def test_lista_solo_su_delegacion(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual([j["numero_registro"] for j in r.data["results"]], ["P-1"])
        self.assertEqual(
            self.client.get(f"{self.url}{self.j_ajena.pk}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_crea_en_su_territorio_y_no_en_ajeno(self):
        r = self.client.post(self.url, self.datos(self.t_propio, "N-1"))
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        r = self.client.post(self.url, self.datos(self.t_ajeno, "N-2"))
        self.assertIn(r.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST))
        self.assertFalse(JuntaVecinos.objects.filter(numero_registro="N-2").exists())

    def test_no_edita_ni_desactiva(self):
        url = f"{self.url}{self.j_propia.pk}/"
        for metodo in (self.client.patch, self.client.put):
            self.assertEqual(metodo(url, {"nombre": "X"}).status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.j_propia.refresh_from_db()
        self.assertTrue(self.j_propia.activa)

    def test_no_gestiona_miembros(self):
        self.assertEqual(self.client.get("/api/miembros-junta/").status_code, 403)
        r = self.client.post("/api/miembros-junta/", {"junta": self.j_propia.pk})
        self.assertEqual(r.status_code, 403)

    def test_territorios_solo_lectura_de_su_delegacion(self):
        r = self.client.get("/api/territorios/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([t["nombre"] for t in r.data["results"]], ["Propio"])
        r = self.client.post(
            "/api/territorios/", {"delegacion": self.t_propio.delegacion_id, "nombre": "Nuevo"}
        )
        self.assertEqual(r.status_code, 403)
        url = f"/api/territorios/{self.t_propio.pk}/"
        self.assertEqual(self.client.patch(url, {"nombre": "Z"}).status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)

    def test_funcionario_sin_delegacion_denegado(self):
        self.usuario.delegacion = None
        self.usuario.save(update_fields=["delegacion"])
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.get("/api/territorios/").status_code, 403)

    def test_pagina_y_menu(self):
        self.client.force_login(self.usuario)
        r = self.client.get("/territorio/juntas-vecinos/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f'href="{reverse("territorio_juntas")}"')
        self.assertEqual(self.client.get("/territorio/territorios/").status_code, 403)

    def test_alcaldesa_sigue_sin_acceso(self):
        from .utiles import crear_usuario

        alcaldesa = crear_usuario("alc.territorio@terriia.cl", 22222222, Rol.ALCALDESA)
        self.client.force_authenticate(alcaldesa)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.force_login(alcaldesa)
        self.assertEqual(self.client.get("/territorio/juntas-vecinos/").status_code, 403)
