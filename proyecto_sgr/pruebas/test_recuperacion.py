"""
Recuperación de contraseña: la pantalla del código no delata si el correo
está registrado (plan de pruebas, ACC-04).

Antes, con un correo registrado la pantalla mostraba el reloj de vigencia y
los intentos que quedaban, y con uno no registrado decía que el código había
caducado. Comparar las dos respuestas bastaba para saber qué cuentas existen.
"""

import re

from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from django.contrib.auth import get_user_model

U = get_user_model()
REGISTRADO = "persona.registrada@ejemplo.cl"
NADIE = "nadie.registrado@ejemplo.cl"


def limpiar(html, correo):
    html = html.replace(correo, "CORREO")
    html = re.sub(r'name="csrfmiddlewaretoken" value="[^"]+"', "", html)
    # El reloj puede diferir en un segundo entre las dos peticiones.
    html = re.sub(r'data-cuenta="\d+"', "", html)
    return re.sub(r'class="reloj">[^<]*<', 'class="reloj"><', html)


@override_settings(SGR_MOSTRAR_CODIGO=False,
                   EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class LaPantallaNoDelata(TestCase):
    @classmethod
    def setUpTestData(cls):
        U.objects.create_user("registrada", REGISTRADO, "Una-Clave-Larga-1")

    def pedir(self, correo):
        c = Client()
        c.post(reverse("cuenta:recuperar"), {"correo": correo})
        return c

    def test_la_pantalla_del_codigo_es_igual(self):
        a = self.pedir(REGISTRADO).get(reverse("cuenta:codigo")).content.decode()
        b = self.pedir(NADIE).get(reverse("cuenta:codigo")).content.decode()
        self.assertEqual(limpiar(a, REGISTRADO), limpiar(b, NADIE))
        self.assertIn("Te quedan 3", b)
        self.assertNotIn("caducó", b)
        self.assertEqual(len(mail.outbox), 1)

    def test_los_intentos_fallidos_responden_igual(self):
        ca, cb = self.pedir(REGISTRADO), self.pedir(NADIE)
        codigo = re.search(r"es (\d{6})", mail.outbox[0].body).group(1)
        malo = "000000" if codigo != "000000" else "111111"
        for n in range(1, 5):
            a = ca.post(reverse("cuenta:codigo"), {"codigo": malo}).content.decode()
            b = cb.post(reverse("cuenta:codigo"), {"codigo": malo}).content.decode()
            self.assertEqual(limpiar(a, REGISTRADO), limpiar(b, NADIE), f"intento {n}")
        self.assertIn("Se agotaron los tres intentos", b)

    def test_un_reenvio_reinicia_los_intentos_simulados(self):
        c = self.pedir(NADIE)
        for _ in range(3):
            c.post(reverse("cuenta:codigo"), {"codigo": "123456"})
        flujo = c.session["sgr_recuperacion"]
        flujo["ultimo_envio"] -= 60
        s = c.session
        s["sgr_recuperacion"] = flujo
        s.save()
        c.post(reverse("cuenta:reenviar"))
        self.assertIn("Te quedan 3", c.get(reverse("cuenta:codigo")).content.decode())
