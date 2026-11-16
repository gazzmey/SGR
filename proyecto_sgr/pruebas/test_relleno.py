"""
Relleno inteligente de formularios (comun/relleno.py y sgr-relleno.js).

Lo que se prueba aquí es la parte del servidor, que es la que decide: los
datos que viajan en cada opción, los valores que se proponen, lo que llega
desde una ficha y los botones de «Registrar desde esta ficha». El navegador
solo usa esos datos; si el JavaScript no carga, el formulario funciona igual.
"""

import json
import re

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from atencion.models import JuntaVecinos, Solicitante
from comun.relleno import quienes_mide
from gestion.models import MetaPeriodo, Periodo
from organizacion.models import Delegacion

from pruebas.test_evaluacion3 import Base

U = get_user_model()


def opcion(html, nombre, valor):
    """El <option value="valor"> del select «nombre», con sus atributos."""
    select = re.search(r'<select name="%s"[^>]*>(.*?)</select>' % nombre, html, re.S)
    assert select, f"no está el select {nombre}"
    hallada = re.search(r'<option value="%s"([^>]*)>' % valor, select.group(1))
    return hallada.group(1) if hallada else None


def atributos_del_select(html, nombre):
    return re.search(r'<select name="%s"([^>]*)>' % nombre, html).group(1)


class RellenoActividad(Base):
    def setUp(self):
        super().setUp()
        self.url = reverse("gestion:registro_actividad_nueva")
        self.vecino = Solicitante.objects.filter(activo=True, territorio__codigo="TER-01").first()

    def test_valores_propuestos(self):
        html = self.gestion.get(self.url).content.decode()
        # Tomás (perfil Gestión) no tiene cargo: no se lo propone como
        # funcionario, porque ninguna meta lo mide. Sí la delegación activa y hoy.
        self.assertNotIn("selected", opcion(html, "funcionario", self.gestion_user.pk) or "")
        self.assertIn("selected", opcion(html, "delegacion", self.del1.pk))
        self.assertIn('data-propuesto="1"', atributos_del_select(html, "delegacion"))
        self.assertIn(f'value="{timezone.localdate():%Y-%m-%d}"', html)

    def test_quien_tiene_cargo_queda_propuesto(self):
        # Felipe (Administrador) tiene cargo y permiso para el registro completo.
        felipe = self._cliente("felipe.araya@ejemplo.cl")
        html = felipe.get(self.url).content.decode()
        yo = U.objects.get(email="felipe.araya@ejemplo.cl")
        self.assertIn("selected", opcion(html, "funcionario", yo.pk))

    def test_datos_de_cada_opcion(self):
        html = self.gestion.get(self.url).content.decode()
        atributos = opcion(html, "solicitante", self.vecino.pk)
        self.assertIn(f'data-territorio="{self.vecino.territorio_id}"', atributos)
        self.assertIn('data-detalle="', atributos)
        self.assertIn("data-buscador", atributos_del_select(html, "solicitante"))
        rellena = re.search(r"data-rellena=\"([^\"]+)\"", atributos_del_select(html, "solicitante")).group(1)
        # El vecino completa su territorio y deja el origen en «comunidad».
        self.assertEqual(json.loads(rellena.replace("&quot;", '"')),
                         {"territorio": "territorio", "origen": "origen"})
        self.assertIn('data-origen="comunidad"', atributos)

    def test_la_asignacion_dice_a_quien_mide(self):
        html = self.gestion.get(self.url).content.decode()
        personal = MetaPeriodo.objects.get(funcionario=self.marcela, item__codigo="ITM-01",
                                           periodo=self.periodo)
        del_cargo = MetaPeriodo.objects.get(funcionario=None, item__codigo="ITM-01",
                                            cargo=personal.cargo, periodo=self.periodo)
        self.assertIn(f'data-mide="{self.marcela.pk}"', opcion(html, "asignacion", personal.pk))
        # En la meta donde Marcela tiene una asignación personal, la del cargo
        # ya no la mide a ella: manda la suya.
        mide_cargo = re.search(r'data-mide="([^"]*)"', opcion(html, "asignacion", del_cargo.pk) or "")
        self.assertNotIn(str(self.marcela.pk), (mide_cargo.group(1).split() if mide_cargo else []))

    def test_desde_la_ficha_llega_elegido(self):
        html = self.gestion.get(f"{self.url}?solicitante={self.vecino.pk}"
                                f"&territorio={self.vecino.territorio_id}&origen=comunidad").content.decode()
        self.assertIn("selected", opcion(html, "solicitante", self.vecino.pk))
        self.assertIn("selected", opcion(html, "territorio", self.vecino.territorio_id))

    def test_lo_completado_pasa_la_validacion(self):
        """Lo que el navegador completaría es justo lo que el servidor acepta."""
        from gestion.modelos_actividad import Actividad

        datos = self.datos("actividad")
        datos.update({"solicitante": self.vecino.pk, "territorio": self.vecino.territorio_id})
        antes = Actividad.objects.count()
        r = self.gestion.post(self.url, datos)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Actividad.objects.count(), antes + 1)
        nueva = Actividad.objects.order_by("-pk").first()
        self.assertEqual((nueva.solicitante_id, nueva.territorio_id),
                         (self.vecino.pk, self.vecino.territorio_id))

    @property
    def gestion_user(self):
        return U.objects.get(email="gestion@ejemplo.cl")


class QuienesMide(Base):
    def test_regla_de_la_asignacion_personal(self):
        asignaciones = MetaPeriodo.objects.filter(periodo=self.periodo, activo=True)
        mide = quienes_mide(asignaciones)
        personal = asignaciones.get(funcionario=self.marcela, item__codigo="ITM-01")
        self.assertEqual(mide[personal.pk], {self.marcela.pk})
        otra_del_cargo = asignaciones.filter(funcionario=None, cargo=personal.cargo).exclude(
            item=personal.item).first()
        if otra_del_cargo:
            self.assertIn(self.marcela.pk, mide[otra_del_cargo.pk])


class RellenoComunidad(Base):
    def test_participacion_filtra_juntas_por_territorio(self):
        html = self.gestion.get(reverse("atencion:participacion_nueva")).content.decode()
        filtro = json.loads(re.search(r'data-filtra="([^"]+)"', atributos_del_select(html, "junta"))
                            .group(1).replace("&quot;", '"'))
        self.assertEqual((filtro["segun"], filtro["dato"], filtro["de"], filtro["autoelige"]),
                         ("vecino", "territorio", "territorio", True))
        junta = JuntaVecinos.objects.filter(activo=True).first()
        self.assertIn(f'data-territorio="{junta.territorio_id}"', opcion(html, "junta", junta.pk))

    def test_valor_fuera_del_alcance_no_se_propone(self):
        """Un vecino de otra delegación en la dirección no aparece elegido."""
        marcela = self._cliente("marcela.rios@ejemplo.cl")
        ajeno = Solicitante.objects.exclude(territorio__delegacion=self.del1).filter(
            territorio__isnull=False).first()
        html = marcela.get(reverse("atencion:participacion_nueva") + f"?vecino={ajeno.pk}").content.decode()
        self.assertIsNone(opcion(html, "vecino", ajeno.pk))

    def test_gestion_social_propone_responsable_y_fechas(self):
        html = self.gestion.get(reverse("atencion:gestion_nueva")).content.decode()
        yo = U.objects.get(email="gestion@ejemplo.cl")
        self.assertIn("selected", opcion(html, "responsable", yo.pk) or "")
        self.assertIn("data-buscador", atributos_del_select(html, "beneficiario"))
        self.assertIn("data-filtra", atributos_del_select(html, "subtipo"))


class RegistrarDesdeLaFicha(Base):
    def test_botones_de_la_ficha_del_vecino(self):
        vecino = Solicitante.objects.filter(activo=True, territorio__isnull=False).first()
        html = self.gestion.get(reverse("atencion:vecino_detalle", args=[vecino.pk])).content.decode()
        self.assertIn("Registrar desde esta ficha", html)
        self.assertIn(reverse("gestion:registro_actividad_nueva") + f"?solicitante={vecino.pk}", html)
        self.assertIn(reverse("atencion:participacion_nueva") + f"?vecino={vecino.pk}", html)

    def test_consulta_no_ve_botones_para_crear(self):
        vecino = Solicitante.objects.filter(activo=True).first()
        html = self.consulta.get(reverse("atencion:vecino_detalle", args=[vecino.pk])).content.decode()
        self.assertNotIn("Registrar desde esta ficha", html)

    def test_una_actividad_anulada_no_recibe_evidencias(self):
        from gestion.modelos_actividad import Actividad

        anulada = Actividad.objects.get(codigo="ACT-E003")
        html = self.gestion.get(reverse("gestion:registro_actividad", args=[anulada.pk])).content.decode()
        self.assertNotIn("Adjuntar evidencia", html)
        viva = Actividad.objects.get(codigo="ACT-E001")
        html = self.gestion.get(reverse("gestion:registro_actividad", args=[viva.pk])).content.decode()
        self.assertIn("origen=actividad&amp;actividad=%d" % viva.pk, html)


class RellenoDelFuncionario(Base):
    def test_mis_actividades_y_agenda(self):
        marcela = self._cliente("marcela.rios@ejemplo.cl")
        html = marcela.get(reverse("gestion:actividad_nueva")).content.decode()
        periodo = Periodo.objects.get(codigo="PER-01")
        esperada = min(max(timezone.localdate(), periodo.inicio), periodo.termino)
        self.assertIn(f'value="{esperada:%Y-%m-%d}"', html)
        self.assertIn("data-sugerencias", html)

        html = marcela.get(reverse("gestion:compromiso_nuevo")).content.decode()
        bruto = re.search(r'name="solicitante"[^>]*data-sugerencias="([^"]*)"', html) or \
            re.search(r'data-sugerencias="([^"]*)"[^>]*name="solicitante"', html)
        sugerencias = json.loads(bruto.group(1).replace("&quot;", '"').replace("&#x27;", "'"))
        juntas = [s for s in sugerencias if s["detalle"].startswith("Junta de vecinos")]
        self.assertTrue(juntas)
        self.assertTrue(all(s["territorio"] and s["origen"] == "externo" for s in juntas))
