"""
Atenciones registradas como pantalla de consulta (atencion/acceso.py).

La registra quien atiende; la consultan también quien supervisa y quien
administra, sin poder registrar. Se prueba quién entra, qué ve cada uno, que
el alcance siga siendo la delegación activa y que el menú y el panel usen la
misma regla que la vista.
"""

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from atencion.acceso import puede_consultar_atenciones
from atencion.models import Atencion

from pruebas.test_evaluacion3 import Base

U = get_user_model()
URL = reverse("atencion:registradas")
INGRESO = reverse("atencion:ingreso")


class QuienLasVe(Base):
    def test_quien_atiende_las_ve_y_puede_registrar(self):
        r = self._cliente("marcela.rios@ejemplo.cl").get(URL)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'href="%s"' % INGRESO)
        self.assertContains(r, "Registrar atención")

    def test_el_administrador_las_ve_sin_poder_registrar(self):
        r = self._cliente("felipe.araya@ejemplo.cl").get(URL)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Es una pantalla de consulta")
        self.assertNotContains(r, 'href="%s"' % INGRESO)
        self.assertNotContains(r, "Abrir caso")
        # Sigue sin poder registrar: el ingreso le responde 403.
        self.assertEqual(self._cliente("felipe.araya@ejemplo.cl").get(INGRESO).status_code, 403)

    def test_quien_supervisa_las_ve(self):
        for correo in ("soledad.guerrero@ejemplo.cl", "pablo.fuentes@ejemplo.cl",
                       "valentina.cortes@ejemplo.cl", "consulta@ejemplo.cl"):
            r = self._cliente(correo).get(URL)
            self.assertEqual(r.status_code, 200, correo)
            self.assertNotContains(r, "Registrar atención", msg_prefix=correo)

    def test_sin_permiso_no_entra(self):
        sin_perfil = U.objects.create_user("sin.perfil", "sin.perfil@ejemplo.cl", "x")
        c = Client()
        c.force_login(sin_perfil)
        self.assertEqual(c.get(URL).status_code, 403)

    def test_sin_sesion_va_al_ingreso(self):
        r = Client().get(URL)
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("cuenta:login"), r["Location"])


class QueVe(Base):
    def test_solo_la_delegacion_activa(self):
        felipe = self._cliente("felipe.araya@ejemplo.cl")
        propia = Atencion.objects.filter(delegacion=self.del1).select_related("solicitante").first()
        # Una persona atendida solo en otra delegación: así su nombre no puede
        # aparecer por otra atención de la propia.
        de_la_propia = Atencion.objects.filter(delegacion=self.del1).values("solicitante")
        ajena = (Atencion.objects.exclude(delegacion=self.del1)
                 .exclude(solicitante__in=de_la_propia).select_related("solicitante").first())
        r = felipe.get(URL)
        self.assertContains(r, propia.solicitante.nombre)
        self.assertNotContains(r, ajena.solicitante.nombre)

        # Al cambiar la delegación activa, ve la otra.
        felipe.post(reverse("comun:cambiar_delegacion"),
                    {"delegacion": ajena.delegacion_id, "volver": URL})
        r = felipe.get(URL)
        self.assertContains(r, ajena.solicitante.nombre)

    def test_el_caso_abre_la_ficha_que_cada_uno_puede_ver(self):
        atencion = Atencion.objects.filter(delegacion=self.del1, caso__isnull=False).first()
        caso = atencion.caso
        ficha_caso = reverse("atencion:caso", args=[caso.pk])
        ficha_gestion = reverse("atencion:gestion_detalle", args=[caso.pk])

        r = self._cliente("pablo.fuentes@ejemplo.cl").get(URL)
        self.assertContains(r, ficha_caso)

        r = self._cliente("felipe.araya@ejemplo.cl").get(URL)
        self.assertNotContains(r, ficha_caso)
        self.assertContains(r, ficha_gestion)
        self.assertEqual(self._cliente("felipe.araya@ejemplo.cl").get(ficha_gestion).status_code, 200)


class MenuYPanel(Base):
    def test_el_menu_la_muestra_al_administrador(self):
        html = self._cliente("felipe.araya@ejemplo.cl").get(reverse("comun:panel")).content.decode()
        self.assertIn('href="%s"' % URL, html)
        self.assertIn("Atenciones registradas", html)

    def test_el_menu_el_panel_y_la_vista_usan_la_misma_regla(self):
        from comun.modulos import areas_de

        for usuario in U.objects.filter(email__endswith="@ejemplo.cl"):
            en_el_panel = any(m.clave == "atenciones" for a in areas_de(usuario) for m in a.modulos)
            self.assertEqual(en_el_panel, puede_consultar_atenciones(usuario), usuario.email)
