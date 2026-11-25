"""
DEF-15 del protocolo de pruebas (caso AWS-02, en el servidor de AWS).

Después de cerrar sesión, «Atrás» volvía a mostrar el panel con sus datos:
el navegador lo sacaba de su memoria. Ahora toda pantalla de una sesión sale
con ``Cache-Control: no-store`` y la página pide recargarse si el navegador
la restaura de su memoria.
"""

from django.test import Client
from django.urls import reverse

from pruebas.test_evaluacion3 import Base


class SinCopiaEnElNavegador(Base):
    def test_las_pantallas_de_la_sesion_no_se_guardan(self):
        c = self._cliente("marcela.rios@ejemplo.cl")
        for url in ("/", reverse("gestion:actividades"), reverse("gestion:mi_resultado")):
            r = c.get(url)
            self.assertEqual(r.status_code, 200, url)
            self.assertIn("no-store", r["Cache-Control"], url)
            self.assertIn("private", r["Cache-Control"], url)

    def test_la_pagina_de_la_sesion_se_recarga_si_vuelve_de_la_memoria(self):
        r = self._cliente("marcela.rios@ejemplo.cl").get("/")
        self.assertContains(r, "data-sesion")

    def test_la_exportacion_tampoco_se_guarda(self):
        r = self.gestion.get(reverse("gestion:registro_actividades") + "?export=excel")
        self.assertEqual(r.status_code, 200)
        self.assertIn("no-store", r["Cache-Control"])

    def test_sin_sesion_el_ingreso_no_marca_sesion(self):
        r = Client().get(reverse("cuenta:login"))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "data-sesion")

    def test_despues_de_salir_el_panel_lleva_al_ingreso(self):
        c = self._cliente("marcela.rios@ejemplo.cl")
        c.post(reverse("cuenta:logout"))
        r = c.get("/")
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("cuenta:login"), r["Location"])
