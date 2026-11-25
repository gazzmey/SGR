"""
DEF-10 del protocolo de pruebas (caso REN-04).

Con el servidor sobrecargado, una actividad se guardaba y aun así la persona
recibía un error: lo que fallaba después de guardar era la escritura de la
sesión. Si volvía a enviar el formulario, quedaban dos actividades iguales.

Ahora el formulario lleva una ficha de envío que se guarda con la actividad.
Un reenvío con la misma ficha no crea otra: lleva a la que ya existe.
"""

from django.urls import reverse

from gestion.modelos_actividad import Actividad

from pruebas.test_evaluacion3 import Base


class FichaDeEnvio(Base):
    def setUp(self):
        super().setUp()
        self.f01 = self._cliente("marcela.rios@ejemplo.cl")
        self.url = reverse("gestion:actividad_nueva")

    def formulario(self):
        r = self.f01.get(self.url)
        self.assertEqual(r.status_code, 200)
        form = r.context["form"]
        item = form.fields["item"].queryset.first()
        return r.context["ficha_envio"], {
            "item": item.pk, "fecha": self.hoy.isoformat(), "cantidad": "1",
            "tipo": "terreno", "origen": "planificada",
            "accion": "Reunión con la directiva por el envío doble",
            "detalle": "Registro de la prueba de DEF-10 con datos ficticios y suficientes.",
        }

    def test_cada_formulario_trae_una_ficha_distinta(self):
        a, _ = self.formulario()
        b, _ = self.formulario()
        self.assertTrue(a and b)
        self.assertNotEqual(a, b)

    def test_el_reenvio_no_duplica_y_lleva_a_la_primera(self):
        ficha, datos = self.formulario()
        antes = Actividad.objects.count()
        r1 = self.f01.post(self.url, dict(datos, envio=ficha))
        self.assertEqual(r1.status_code, 302)
        primera = Actividad.objects.get(envio=ficha)
        # El mismo formulario llega otra vez: por ejemplo, porque la primera
        # respuesta se perdió y la persona volvió a tocar «Guardar».
        r2 = self.f01.post(self.url, dict(datos, envio=ficha))
        self.assertRedirects(r2, reverse("gestion:actividad_detalle", args=[primera.pk]),
                             fetch_redirect_response=False)
        self.assertEqual(Actividad.objects.count(), antes + 1)
        self.assertEqual(Actividad.objects.filter(accion=datos["accion"]).count(), 1)

    def test_dos_formularios_distintos_crean_dos_actividades(self):
        f1, datos = self.formulario()
        f2, _ = self.formulario()
        self.f01.post(self.url, dict(datos, envio=f1))
        self.f01.post(self.url, dict(datos, envio=f2, accion=datos["accion"] + " (segunda)"))
        self.assertEqual(Actividad.objects.filter(envio__in=[f1, f2]).count(), 2)

    def test_sin_ficha_sigue_registrando(self):
        _, datos = self.formulario()
        r = self.f01.post(self.url, datos)
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Actividad.objects.filter(accion=datos["accion"], envio__isnull=True).exists())

    def test_la_ficha_de_otra_persona_no_entrega_su_actividad(self):
        ficha, datos = self.formulario()
        self.f01.post(self.url, dict(datos, envio=ficha))
        ajena = Actividad.objects.get(envio=ficha)
        otra = self._cliente("camila.otarola@ejemplo.cl")
        r = otra.post(self.url, dict(datos, envio=ficha))
        # No se redirige a la actividad de Marcela ni se revela su código.
        self.assertNotEqual(r.get("Location"), reverse("gestion:actividad_detalle", args=[ajena.pk]))
