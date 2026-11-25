"""
DEF-07 del protocolo de pruebas (caso AGE-01): un compromiso no se podía
crear a partir de una actividad. Ahora la ficha de la actividad ofrece
«Crear compromiso» y el compromiso queda vinculado a ella.
"""

from datetime import timedelta

from django.urls import reverse

from gestion.modelos_actividad import Actividad
from gestion.modelos_agenda import Compromiso

from pruebas.test_evaluacion3 import Base


class CompromisoDesdeActividad(Base):
    def setUp(self):
        super().setUp()
        self.marcela_c = self._cliente("marcela.rios@ejemplo.cl")
        self.act = Actividad.objects.filter(funcionario=self.marcela, estado=Actividad.Estado.APROBADA).first()

    def test_la_ficha_ofrece_crear_compromiso(self):
        r = self.marcela_c.get(reverse("gestion:actividad_detalle", args=[self.act.pk]))
        self.assertContains(r, "?actividad=%d" % self.act.pk)

    def test_el_compromiso_queda_vinculado(self):
        url = reverse("gestion:compromiso_nuevo") + "?actividad=%d" % self.act.pk
        r = self.marcela_c.get(url)
        self.assertContains(r, self.act.codigo)
        self.assertIn(self.act.codigo, r.context["form"].initial.get("descripcion", ""))
        r = self.marcela_c.post(url, {
            "solicitante": "Junta de vecinos de prueba", "origen": "externo", "territorio": "Sector de prueba",
            "descripcion": "Seguimiento de la actividad: reparar la luminaria de la plaza.",
            "responsable": self.marcela.pk, "vencimiento": (self.hoy + timedelta(days=10)).isoformat(),
        })
        self.assertEqual(r.status_code, 302)
        comp = Compromiso.objects.order_by("-pk").first()
        self.assertEqual(comp.actividad, self.act)
        self.assertIn(self.act.codigo, comp.cambios.first().observacion)

    def test_no_se_vincula_una_actividad_ajena(self):
        ajena = Actividad.objects.exclude(funcionario=self.marcela).first()
        url = reverse("gestion:compromiso_nuevo") + "?actividad=%d" % ajena.pk
        r = self.marcela_c.get(url)
        self.assertIsNone(r.context["origen"])
