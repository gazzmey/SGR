"""
Correcciones posteriores a la Evaluación 3.

* El teléfono es obligatorio en todos los formularios que lo piden: vecino,
  delegación, ingreso de atención y regalos.
* La fecha de compromiso de una actividad, una vez puesta, no se cambia al
  editar.
"""

from datetime import timedelta

from django import forms
from django.urls import reverse

from atencion.forms import AtencionForm
from atencion.forms_regalos import InscripcionForm
from atencion.models import Solicitante
from comun.formularios import limpiar_telefono
from gestion.modelos_actividad import Actividad
from organizacion.models import Delegacion

from pruebas.test_evaluacion3 import Base


class TelefonoObligatorio(Base):
    def test_formatos(self):
        for valido in ("9 1234 5678", "51 2 200 101", "+56 9 1234 5678", "(51) 220-0101"):
            self.assertEqual(limpiar_telefono(valido), valido)
        for invalido in ("", "   ", "9 1234", "nueve uno dos", "+56 9 1234 5678 99"):
            with self.assertRaises(forms.ValidationError, msg=invalido):
                limpiar_telefono(invalido)

    def test_vecino_sin_telefono_no_se_guarda(self):
        datos = dict(self.datos("vecino"), telefono="")
        antes = Solicitante.objects.count()
        r = self.gestion.post(reverse("atencion:vecino_nuevo"), datos)
        self.assertEqual(r.status_code, 200)
        self.assertIn("El teléfono es obligatorio", r.content.decode())
        self.assertEqual(Solicitante.objects.count(), antes)

    def test_vecino_con_telefono_corto_no_se_guarda(self):
        datos = dict(self.datos("vecino"), telefono="9 123")
        r = self.gestion.post(reverse("atencion:vecino_nuevo"), datos)
        self.assertIn("necesita al menos 8", r.content.decode())

    def test_delegacion_sin_telefono_no_se_guarda(self):
        datos = dict(self.datos("delegacion"), telefono="")
        antes = Delegacion.objects.count()
        r = self.gestion.post(reverse("organizacion:delegacion_nueva"), datos)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Delegacion.objects.count(), antes)

    def test_ingreso_y_regalos_lo_exigen(self):
        self.assertTrue(AtencionForm.base_fields["telefono"].required)
        self.assertTrue(InscripcionForm.base_fields["telefono_apoderado"].required)

    def test_la_ficha_lo_marca_obligatorio(self):
        html = self.gestion.get(reverse("atencion:vecino_nuevo")).content.decode()
        self.assertRegex(html, r'name="telefono"[^>]*required|required[^>]*name="telefono"')


class FechaDeCompromisoFija(Base):
    def _crear(self, **cambios):
        datos = dict(self.datos("actividad"), **cambios)
        r = self.gestion.post(reverse("gestion:registro_actividad_nueva"), datos)
        self.assertEqual(r.status_code, 302)
        return Actividad.objects.order_by("-pk").first(), datos

    def test_no_cambia_al_editar(self):
        actividad, datos = self._crear()
        fijada = actividad.fecha_compromiso
        url = reverse("gestion:registro_actividad_editar", args=[actividad.pk])
        html = self.gestion.get(url).content.decode()
        self.assertRegex(html, r'name="fecha_compromiso"[^>]*disabled')
        otra = str(fijada + timedelta(days=20))
        r = self.gestion.post(url, dict(datos, fecha_compromiso=otra, accion="Actividad editada en la prueba"))
        self.assertEqual(r.status_code, 302)
        actividad.refresh_from_db()
        self.assertEqual(actividad.fecha_compromiso, fijada)
        self.assertEqual(actividad.accion, "Actividad editada en la prueba")

    def test_sin_fecha_se_puede_poner_una_vez(self):
        actividad, datos = self._crear(fecha_compromiso="")
        self.assertIsNone(actividad.fecha_compromiso)
        url = reverse("gestion:registro_actividad_editar", args=[actividad.pk])
        plazo = actividad.fecha + timedelta(days=7)
        r = self.gestion.post(url, dict(datos, fecha_compromiso=str(plazo)))
        self.assertEqual(r.status_code, 302)
        actividad.refresh_from_db()
        self.assertEqual(actividad.fecha_compromiso, plazo)
        html = self.gestion.get(url).content.decode()
        self.assertRegex(html, r'name="fecha_compromiso"[^>]*disabled')
