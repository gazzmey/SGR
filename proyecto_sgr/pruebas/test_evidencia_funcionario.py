"""
DEF-06 del protocolo de pruebas (casos EVI-01 a EVI-07): la funcionaria no
podía adjuntar evidencia desde su actividad.

``EvidenciaForm`` asignaba la actividad recién al guardar, pero Django valida
el modelo antes, y ``Evidencia.clean()`` exige que la evidencia respalde una
actividad o una gestión social. Toda evidencia nueva se rechazaba con
«Revisa los datos», sin más explicación.
"""

import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse

from gestion.modelos_actividad import Actividad, Evidencia

from pruebas.test_evaluacion3 import Base

#: Un JPEG mínimo: los primeros bytes son los que revisa gestion/evidencias.py.
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 200 + b"\xff\xd9"


class AdjuntarDesdeLaActividad(Base):
    def setUp(self):
        super().setUp()
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.marcela = self._cliente("marcela.rios@ejemplo.cl")
        self.act = Actividad.objects.filter(funcionario__email="marcela.rios@ejemplo.cl",
                                            estado=Actividad.Estado.BORRADOR).first()

    def test_la_evidencia_se_guarda_y_la_actividad_pasa_a_pendiente(self):
        with override_settings(MEDIA_ROOT=self.media):
            antes = Evidencia.objects.count()
            r = self.marcela.post(reverse("gestion:evidencia_nueva", args=[self.act.pk]), {
                "archivo": SimpleUploadedFile("foto.jpg", JPEG, content_type="image/jpeg"),
                "descripcion": "Fotografía de la visita a terreno",
            })
            self.assertEqual(r.status_code, 302, r.context["form"].errors if r.context else r)
            self.assertEqual(Evidencia.objects.count(), antes + 1)
            ev = Evidencia.objects.order_by("-pk").first()
            self.assertEqual(ev.actividad, self.act)
            self.assertEqual(ev.autor.email, "marcela.rios@ejemplo.cl")
            self.assertEqual(ev.nombre_original, "foto.jpg")
            self.act.refresh_from_db()
            self.assertEqual(self.act.estado, Actividad.Estado.PENDIENTE)

    def test_un_error_sin_campo_se_muestra(self):
        """Si el modelo rechaza algo que no es de un campo, la pantalla lo dice."""
        with override_settings(MEDIA_ROOT=self.media):
            r = self.marcela.post(reverse("gestion:evidencia_nueva", args=[self.act.pk]), {
                "archivo": SimpleUploadedFile("foto.jpg", JPEG, content_type="image/jpeg"),
                "descripcion": "corto",
            })
            self.assertEqual(r.status_code, 200)
            self.assertContains(r, "Qué respalda")


class DecisionSimultanea(Base):
    """EVI-06: la decisión se toma con un UPDATE condicionado a que siga pendiente."""

    def test_solo_la_primera_decision_queda(self):
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        from gestion.views_actividad import DecidirEvidencia

        ev = Evidencia.objects.filter(decision=Evidencia.Decision.PENDIENTE, anulada=False).first()
        pablo = get_user_model().objects.get(email="pablo.fuentes@ejemplo.cl")
        primera = DecidirEvidencia._tomar(ev, decision=Evidencia.Decision.APROBADA, verificador=pablo,
                                          decidida=timezone.now(), motivo="")
        # El segundo verificador tenía la misma evidencia «pendiente» en memoria.
        vieja = Evidencia.objects.get(pk=ev.pk)
        vieja.decision = Evidencia.Decision.PENDIENTE
        segunda = DecidirEvidencia._tomar(vieja, decision=Evidencia.Decision.RECHAZADA, verificador=pablo,
                                          decidida=timezone.now(), motivo="Rechazo que llega tarde")
        self.assertTrue(primera)
        self.assertFalse(segunda)
        ev.refresh_from_db()
        self.assertEqual(ev.decision, Evidencia.Decision.APROBADA)
        self.assertEqual(ev.motivo, "")


class CodigoSimultaneo(Base):
    """DEF-09: dos altas que calculan el mismo código no terminan en error."""

    def test_si_el_codigo_ya_se_tomo_se_usa_el_siguiente(self):
        from comun.utilidades import guardar_con_codigo, proximo_codigo

        base = Actividad.objects.filter(funcionario=self.marcela).first()
        codigo = proximo_codigo(Actividad, "ACT", ancho=4)

        def nueva(texto):
            return Actividad(codigo=codigo, funcionario=base.funcionario, delegacion=base.delegacion,
                             periodo=base.periodo, item=base.item, asignacion=base.asignacion, fecha=base.fecha,
                             cantidad=1, accion=texto, detalle="Prueba de altas simultáneas.")
        primera = guardar_con_codigo(nueva("Primera"), "ACT", ancho=4)
        segunda = guardar_con_codigo(nueva("Segunda"), "ACT", ancho=4)   # llega con el mismo código calculado
        self.assertEqual(primera.codigo, codigo)
        self.assertNotEqual(segunda.codigo, codigo)
        self.assertTrue(segunda.pk)
