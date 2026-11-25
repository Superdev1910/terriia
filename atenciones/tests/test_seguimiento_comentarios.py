"""HU08 · Comentarios en cada tarea. SCRUM-82 / SCRUM-83."""

from rest_framework import status
from rest_framework.test import APITestCase

from atenciones.models import Comentario
from core.models import Auditoria

from .utiles_seguimiento import RAPIDO, EscenarioSolicitudesMixin


@RAPIDO
class ComentariosTests(EscenarioSolicitudesMixin, APITestCase):
    def setUp(self):
        self.preparar_escenario()
        self.a = self.crear_actividad()

    def comentar(self, texto, actividad=None):
        return self.client.post(
            self.url(actividad or self.a, "comentarios"), {"texto": texto}, format="json"
        )

    def test_comentar_guarda_autor_fecha_y_auditoria(self):
        self.client.force_authenticate(self.usuario_ana)
        r = self.comentar("  Llamé a la vecina, vuelve el lunes  ")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        c = Comentario.objects.get()
        self.assertEqual(
            (c.usuario, c.actividad, c.texto),
            (self.usuario_ana, self.a, "Llamé a la vecina, vuelve el lunes"),
        )
        self.assertEqual(r.data["usuario_rol"], "Funcionario")
        self.assertTrue(Auditoria.objects.filter(evento="comentar", entidad="comentario").exists())

    def test_se_listan_en_orden_cronologico_con_varios_autores(self):
        self.client.force_authenticate(self.usuario_ana)
        self.comentar("Primero")
        self.client.force_authenticate(self.delegado)
        self.comentar("Segundo")
        r = self.client.get(self.url(self.a, "comentarios"))
        self.assertEqual([c["texto"] for c in r.data], ["Primero", "Segundo"])
        self.assertEqual(r.data[1]["usuario_rol"], "Delegado territorial")
        self.assertEqual(self.client.get(self.url(self.a)).data["n_comentarios"], 2)

    def test_comentario_vacio_o_muy_largo(self):
        self.client.force_authenticate(self.usuario_ana)
        for malo in ("", "   ", "x" * 1001):
            r = self.comentar(malo)
            self.assertEqual((r.status_code, r.data["campo"]), (400, "texto"), len(malo))
        self.assertEqual(Comentario.objects.count(), 0)

    def test_los_comentarios_no_se_editan_ni_se_borran(self):
        self.client.force_authenticate(self.usuario_ana)
        self.comentar("Hola")
        c = Comentario.objects.get()
        for metodo in ("patch", "put", "delete"):
            r = getattr(self.client, metodo)(
                f"/api/comentarios/{c.pk}/", {"texto": "x"}, format="json"
            )
            self.assertEqual(r.status_code, 404, metodo)

    def test_solo_comenta_quien_ve_la_solicitud(self):
        self.client.force_authenticate(self.usuario_luis)
        self.assertEqual(self.comentar("No debería").status_code, 403)
        self.assertEqual(self.client.get(self.url(self.a, "comentarios")).status_code, 404)
        self.client.force_authenticate(self.delegado_norte)
        self.assertEqual(self.comentar("Tampoco").status_code, 403)
        self.assertEqual(self.client.get(self.url(self.a, "comentarios")).status_code, 404)
        self.client.force_authenticate(self.alcaldesa)
        self.assertEqual(self.comentar("Sin acceso").status_code, 403)
        self.assertEqual(Comentario.objects.count(), 0)

    def test_responsable_puede_comentar(self):
        self.a.responsable = self.luis
        self.a.save()
        self.client.force_authenticate(self.usuario_luis)
        self.assertEqual(self.comentar("Me hago cargo").status_code, 201)

    def test_se_puede_comentar_una_solicitud_realizada(self):
        self.a.estado = "Realizado"
        self.a.save()
        self.client.force_authenticate(self.usuario_ana)
        self.assertEqual(self.comentar("Cierre confirmado con la vecina").status_code, 201)
