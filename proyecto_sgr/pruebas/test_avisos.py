"""
Aviso de que un compromiso no llega a la fecha (guía 4.2, punto 4).

Se prueba lo que decide el servidor: quién puede avisar, a quién le llega,
que el aviso no cambie la fecha ni el atraso, que aparezca en *Mi panel* de
quien lo recibe hasta que lo marca como visto, y que solo el destinatario
pueda marcarlo.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import resolve, reverse

from comun.models import EventoAuditoria
from gestion.modelos_agenda import (
    AvisoCompromiso, CambioCompromiso, Compromiso, DestinatarioAviso,
)
from gestion.views_agenda import CompromisoAvisar
from organizacion.models import Delegacion

from pruebas.test_evaluacion3 import Base

U = get_user_model()
PANEL = reverse("comun:panel")
MOTIVO = "La cuadrilla de Diserco no tiene hora hasta el 28; quedaría para la primera semana de diciembre."


def abierto(delegacion, responsable):
    return Compromiso.objects.filter(
        delegacion__codigo=delegacion, responsable__email=responsable,
        estado__in=Compromiso.ABIERTOS).order_by("pk").first()


class QuienAvisa(Base):
    def setUp(self):
        super().setUp()
        self.soledad = U.objects.get(email="soledad.guerrero@ejemplo.cl")
        self.camila = U.objects.get(email="camila.otarola@ejemplo.cl")
        self.suyo = abierto("DEL-01", "marcela.rios@ejemplo.cl")
        self.de_camila = abierto("DEL-01", "camila.otarola@ejemplo.cl")
        self.assertIsNotNone(self.suyo)
        self.assertIsNotNone(self.de_camila)

    def avisar(self, correo, compromiso, motivo=MOTIVO):
        return self._cliente(correo).post(
            reverse("gestion:compromiso_avisar", args=[compromiso.pk]), {"motivo": motivo})

    def test_la_direccion_no_la_captura_el_cambio_de_estado(self):
        url = reverse("gestion:compromiso_avisar", args=[self.suyo.pk])
        self.assertEqual(resolve(url).func.view_class, CompromisoAvisar)

    def test_el_responsable_avisa_y_le_llega_al_delegado(self):
        antes = AvisoCompromiso.objects.count()
        r = self.avisar("marcela.rios@ejemplo.cl", self.suyo)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(AvisoCompromiso.objects.count(), antes + 1)
        aviso = AvisoCompromiso.objects.latest("pk")
        self.assertEqual(aviso.autor, self.marcela)
        self.assertEqual(aviso.motivo, MOTIVO)
        destinatarios = list(aviso.destinatarios.values_list("usuario__email", "por_que"))
        self.assertEqual(destinatarios, [("soledad.guerrero@ejemplo.cl", "delegado")])

    def test_si_avisa_un_colega_tambien_le_llega_al_responsable(self):
        self.avisar("marcela.rios@ejemplo.cl", self.de_camila)
        aviso = AvisoCompromiso.objects.filter(autor=self.marcela).latest("pk")
        self.assertEqual(
            list(aviso.destinatarios.values_list("usuario__email", "por_que")),
            [("soledad.guerrero@ejemplo.cl", "delegado"),
             ("camila.otarola@ejemplo.cl", "responsable")])

    def test_si_el_delegado_es_el_responsable_le_llega_una_vez(self):
        del2 = Delegacion.objects.get(codigo="DEL-02")
        rodrigo = U.objects.get(email="rodrigo.tapia@ejemplo.cl")
        self.assertEqual(del2.delegado, rodrigo)
        suyo = abierto("DEL-02", "rodrigo.tapia@ejemplo.cl")
        self.assertIsNotNone(suyo)
        self.avisar("hector.pizarro@ejemplo.cl", suyo)
        aviso = AvisoCompromiso.objects.filter(compromiso=suyo).latest("pk")
        self.assertEqual(list(aviso.destinatarios.values_list("usuario__email", "por_que")),
                         [("rodrigo.tapia@ejemplo.cl", "delegado")])

    def test_queda_en_el_historial_en_la_observacion_y_en_la_auditoria(self):
        self.avisar("marcela.rios@ejemplo.cl", self.suyo)
        self.suyo.refresh_from_db()
        self.assertEqual(self.suyo.observacion, MOTIVO)
        cambio = self.suyo.cambios.first()
        self.assertEqual(cambio.tipo, CambioCompromiso.Tipo.AVISO)
        self.assertEqual(cambio.quien, self.marcela)
        self.assertEqual(cambio.observacion, MOTIVO)
        evento = EventoAuditoria.objects.filter(accion=EventoAuditoria.Accion.AVISAR).latest("pk")
        self.assertEqual(evento.objeto_id, self.suyo.pk)
        self.assertIn("Soledad", evento.despues)

    def test_no_cambia_la_fecha_ni_el_estado_ni_el_atraso(self):
        Compromiso.objects.filter(pk=self.suyo.pk).update(vencimiento=self.hoy - timedelta(days=3))
        self.suyo.refresh_from_db()
        estado, vence = self.suyo.estado, self.suyo.vencimiento
        self.avisar("marcela.rios@ejemplo.cl", self.suyo)
        self.suyo.refresh_from_db()
        self.assertEqual((self.suyo.estado, self.suyo.vencimiento), (estado, vence))
        self.assertEqual(self.suyo.atraso_al_dia(), 3)
        aviso = AvisoCompromiso.objects.latest("pk")
        self.assertEqual(aviso.vencimiento, vence)
        self.assertEqual(aviso.dias_de_anticipacion, -3)
        self.assertEqual(aviso.cuando_texto, "3 días después de vencido")

    def test_el_motivo_es_obligatorio(self):
        antes = AvisoCompromiso.objects.count()
        r = self.avisar("marcela.rios@ejemplo.cl", self.suyo, motivo="no alcanzo")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(AvisoCompromiso.objects.count(), antes)

    def test_quien_no_trabaja_compromisos_no_avisa(self):
        for correo in ("pablo.fuentes@ejemplo.cl", "soledad.guerrero@ejemplo.cl",
                       "valentina.cortes@ejemplo.cl", "consulta@ejemplo.cl"):
            self.assertEqual(self.avisar(correo, self.suyo).status_code, 403, correo)

    def test_no_se_avisa_sobre_otra_delegacion(self):
        ajeno = abierto("DEL-02", "rodrigo.tapia@ejemplo.cl")
        self.assertEqual(self.avisar("marcela.rios@ejemplo.cl", ajeno).status_code, 403)

    def test_un_compromiso_cerrado_no_recibe_avisos(self):
        cerrado = Compromiso.objects.filter(
            delegacion=self.del1, estado=Compromiso.Estado.REALIZADO).first()
        antes = AvisoCompromiso.objects.count()
        self.avisar("marcela.rios@ejemplo.cl", cerrado)
        self.assertEqual(AvisoCompromiso.objects.count(), antes)

    def test_sin_delegado_queda_en_la_ficha_y_lo_dice(self):
        Delegacion.objects.filter(pk=self.del1.pk).update(delegado=None)
        r = self._cliente("marcela.rios@ejemplo.cl").post(
            reverse("gestion:compromiso_avisar", args=[self.suyo.pk]),
            {"motivo": MOTIVO}, follow=True)
        aviso = AvisoCompromiso.objects.latest("pk")
        self.assertEqual(aviso.destinatarios.count(), 0)
        self.assertContains(r, "no le llegó a nadie")


class EnMiPanel(Base):
    """El aviso de la demostración: Camila avisa y le llega a Soledad."""

    def setUp(self):
        super().setUp()
        self.aviso = AvisoCompromiso.objects.get(compromiso__codigo__startswith="CMP-D",
                                                 autor__email="camila.otarola@ejemplo.cl")
        self.compromiso = self.aviso.compromiso
        self.titulo = "No se llega a la fecha: %s" % self.compromiso.codigo

    def test_al_delegado_le_aparece_en_mi_panel(self):
        r = self._cliente("soledad.guerrero@ejemplo.cl").get(PANEL)
        self.assertContains(r, self.titulo)
        self.assertContains(r, reverse("gestion:compromiso_detalle", args=[self.compromiso.pk]) + "#avisos")

    def test_a_quien_avisa_y_a_los_demas_no_les_aparece(self):
        for correo in ("camila.otarola@ejemplo.cl", "marcela.rios@ejemplo.cl", "pablo.fuentes@ejemplo.cl"):
            self.assertNotContains(self._cliente(correo).get(PANEL), self.titulo, msg_prefix=correo)

    def test_la_ficha_muestra_a_quien_le_llego(self):
        r = self._cliente("pablo.fuentes@ejemplo.cl").get(
            reverse("gestion:compromiso_detalle", args=[self.compromiso.pk]))
        self.assertContains(r, "Avisos de que no se llega a la fecha")
        self.assertContains(r, "sin ver")
        self.assertNotContains(r, ">Lo vi<")

    def test_lo_vi_lo_saca_del_panel_y_queda_en_la_ficha(self):
        soledad = self._cliente("soledad.guerrero@ejemplo.cl")
        ficha = reverse("gestion:compromiso_detalle", args=[self.compromiso.pk])
        self.assertContains(soledad.get(ficha), ">Lo vi<")
        r = soledad.post(reverse("gestion:compromiso_aviso_visto",
                                 args=[self.compromiso.pk, self.aviso.pk]))
        self.assertEqual(r.status_code, 302)
        destino = DestinatarioAviso.objects.get(aviso=self.aviso, usuario__email="soledad.guerrero@ejemplo.cl")
        self.assertIsNotNone(destino.visto_el)
        self.assertNotContains(soledad.get(PANEL), self.titulo)
        self.assertContains(soledad.get(ficha), "lo vio el")

    def test_solo_el_destinatario_lo_marca(self):
        url = reverse("gestion:compromiso_aviso_visto", args=[self.compromiso.pk, self.aviso.pk])
        for correo in ("camila.otarola@ejemplo.cl", "pablo.fuentes@ejemplo.cl", "felipe.araya@ejemplo.cl"):
            self.assertEqual(self._cliente(correo).post(url).status_code, 403, correo)
        self.assertFalse(DestinatarioAviso.objects.filter(aviso=self.aviso, visto_el__isnull=False).exists())

    def test_la_ficha_dice_a_quien_le_llegara_antes_de_avisar(self):
        r = self._cliente("marcela.rios@ejemplo.cl").get(
            reverse("gestion:compromiso_detalle", args=[self.compromiso.pk]))
        self.assertContains(r, "Enviar aviso")
        self.assertContains(r, "La fecha comprometida no cambia")
        self.assertContains(r, "Soledad")

    def test_quien_no_avanza_no_ve_el_formulario(self):
        r = self._cliente("soledad.guerrero@ejemplo.cl").get(
            reverse("gestion:compromiso_detalle", args=[self.compromiso.pk]))
        self.assertNotContains(r, "Enviar aviso")
