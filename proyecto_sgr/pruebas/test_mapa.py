"""
Mapa de presencia territorial (gestion/mapa.py y gestion/mapa.html).

Se prueba lo que decide el servidor: quién entra y con qué vista, qué
delegaciones ve, qué se cuenta como presencia, que no salga ningún dato de
vecinos y que la ubicación de un territorio se valide al guardarla. El
dibujo del mapa usa exactamente los datos que se comprueban aquí.
"""

import json
import re
from datetime import timedelta
from decimal import Decimal

from django import forms
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from atencion.models import Solicitante
from gestion import mapa as M
from gestion.modelos_actividad import Actividad
from gestion.modelos_agenda import Compromiso
from organizacion.forms import leer_ubicacion
from organizacion.models import Delegacion, Territorio

from pruebas.test_evaluacion3 import Base

U = get_user_model()
URL = reverse("gestion:mapa")


def datos_del_mapa(respuesta):
    html = respuesta.content.decode()
    bruto = re.search(r'<script id="datos-mapa" type="application/json">(.*?)</script>', html, re.S)
    assert bruto, "la página no trae los datos del mapa"
    return json.loads(bruto.group(1))


def por_codigo(datos):
    return {t["codigo"]: t for t in datos["territorios"]}


class QuienEntra(Base):
    def test_supervision_ve_el_mapa_completo(self):
        for correo in ("felipe.araya@ejemplo.cl", "pablo.fuentes@ejemplo.cl", "soledad.guerrero@ejemplo.cl"):
            r = self._cliente(correo).get(URL)
            self.assertEqual(r.status_code, 200, correo)
            self.assertEqual(datos_del_mapa(r)["modo"], M.COMPLETO, correo)

    def test_consulta_entra_por_el_permiso_de_django(self):
        r = self.consulta.get(URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(datos_del_mapa(r)["modo"], M.COMPLETO)
        # Puede mirar, pero no registrar: ningún botón para crear.
        for t in datos_del_mapa(r)["territorios"]:
            self.assertFalse([a for a in t["acciones"] if "nueva" in a["url"] or "nuevo" in a["url"]])

    def test_quien_registra_ve_solo_lo_suyo(self):
        r = self._cliente("marcela.rios@ejemplo.cl").get(URL)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Estás viendo solo lo tuyo")
        self.assertEqual(datos_del_mapa(r)["modo"], M.PERSONAL)

    def test_sin_permiso_no_entra(self):
        sin_perfil = U.objects.create_user("sin.perfil", "sin.perfil@ejemplo.cl", "x")
        c = Client()
        c.force_login(sin_perfil)
        self.assertEqual(c.get(URL).status_code, 403)

    def test_sin_sesion_va_al_ingreso(self):
        r = Client().get(URL)
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("cuenta:login"), r["Location"])

    def test_el_panel_y_el_menu_usan_la_misma_regla(self):
        from comun.modulos import areas_de

        for usuario in U.objects.filter(email__endswith="@ejemplo.cl"):
            en_el_panel = any(m.clave == "mapa" for a in areas_de(usuario) for m in a.modulos)
            self.assertEqual(en_el_panel, M.modo_de(usuario) is not None, usuario.email)

    def test_el_menu_lo_muestra(self):
        html = self._cliente("marcela.rios@ejemplo.cl").get(reverse("comun:panel")).content.decode()
        self.assertIn(URL, html)
        self.assertIn("Mapa de presencia", html)


class Alcance(Base):
    def test_cada_uno_ve_sus_delegaciones(self):
        pablo = self._cliente("pablo.fuentes@ejemplo.cl")
        codigos = set(por_codigo(datos_del_mapa(pablo.get(URL))))
        self.assertTrue(codigos)
        propios = set(Territorio.objects.filter(delegacion=self.del1).values_list("codigo", flat=True))
        self.assertTrue(codigos <= propios, codigos - propios)
        self.assertNotIn("TER-04", codigos)

    def test_una_delegacion_ajena_se_rechaza(self):
        del2 = Delegacion.objects.get(codigo="DEL-02")
        pablo = self._cliente("pablo.fuentes@ejemplo.cl")
        self.assertEqual(pablo.get(URL, {"delegacion": del2.pk}).status_code, 403)

    def test_quien_ve_todas_puede_elegir_una(self):
        del2 = Delegacion.objects.get(codigo="DEL-02")
        felipe = self._cliente("felipe.araya@ejemplo.cl")
        territorios = datos_del_mapa(felipe.get(URL, {"delegacion": del2.pk}))["territorios"]
        self.assertTrue(territorios)
        self.assertEqual({t["delegacion_id"] for t in territorios}, {del2.pk})


class QueCuenta(Base):
    def setUp(self):
        super().setUp()
        self.felipe = self._cliente("felipe.araya@ejemplo.cl")

    def test_registrado_y_verificado(self):
        vivas = Actividad.objects.filter(territorio=self.ter1, periodo=self.periodo).exclude(
            estado=Actividad.Estado.ANULADA)
        aprobadas = vivas.filter(estado=Actividad.Estado.APROBADA)
        t = por_codigo(datos_del_mapa(self.felipe.get(URL)))["TER-01"]
        self.assertEqual(t["registradas"], vivas.count())
        self.assertEqual(t["verificadas"], aprobadas.count())
        self.assertEqual(t["medida"], vivas.count())
        # La demostración tiene actividades sin evidencia en El Mirador, así
        # que lo verificado es menos que lo registrado.
        self.assertLess(t["verificadas"], t["registradas"])

        t = por_codigo(datos_del_mapa(self.felipe.get(URL, {"presencia": "verificada"})))["TER-01"]
        self.assertEqual(t["medida"], aprobadas.count())

    def test_una_anulada_no_es_presencia(self):
        ter2 = Territorio.objects.get(codigo="TER-02")
        antes = por_codigo(datos_del_mapa(self.felipe.get(URL)))["TER-02"]
        base = Actividad.objects.filter(territorio=self.ter1, estado=Actividad.Estado.APROBADA).first()
        Actividad.objects.filter(pk=base.pk).update(territorio=ter2, estado=Actividad.Estado.ANULADA,
                                                    fecha=self.hoy)
        despues = por_codigo(datos_del_mapa(self.felipe.get(URL)))["TER-02"]
        self.assertEqual((antes["ultima"], antes["registradas"]), (despues["ultima"], despues["registradas"]))

    def test_semaforo(self):
        self.assertEqual(M.semaforo(0), "verde")
        self.assertEqual(M.semaforo(M.VERDE_HASTA), "verde")
        self.assertEqual(M.semaforo(M.VERDE_HASTA + 1), "ambar")
        self.assertEqual(M.semaforo(M.AMBAR_HASTA), "ambar")
        self.assertEqual(M.semaforo(M.AMBAR_HASTA + 1), "rojo")
        self.assertEqual(M.semaforo(None), "rojo")
        self.assertEqual(M.semaforo(3, activo=False), "gris")

    def test_la_demostracion_muestra_los_tres_colores(self):
        colores = {t["semaforo"] for t in datos_del_mapa(self.felipe.get(URL))["territorios"]}
        self.assertTrue({"verde", "ambar", "rojo"} <= colores, colores)

    def test_filtro_por_tipo(self):
        datos = datos_del_mapa(self.felipe.get(URL, {"tipo": "reunion"}))
        reuniones = Actividad.objects.filter(territorio=self.ter1, periodo=self.periodo, tipo="reunion") \
            .exclude(estado=Actividad.Estado.ANULADA).count()
        self.assertEqual(por_codigo(datos)["TER-01"]["registradas"], reuniones)

    def test_la_agenda_reconoce_el_territorio_escrito(self):
        territorios = list(Territorio.objects.filter(delegacion=self.del1))
        reconoce = M._reconocedor(territorios)
        ter3 = Territorio.objects.get(codigo="TER-03")
        for escrito in ("Unidad vecinal 3 · San Juan", "unidad vecinal 3 - SAN JUAN", "San Juan", "TER-03"):
            self.assertEqual(reconoce.get((self.del1.pk, M.normalizar(escrito))), ter3.pk, escrito)
        self.assertIsNone(reconoce.get((self.del1.pk, M.normalizar("Otro sector"))))

    def test_compromisos_abiertos_y_vencidos(self):
        t = por_codigo(datos_del_mapa(self.felipe.get(URL)))["TER-01"]
        nombres = {M.normalizar(n) for n in (self.ter1.nombre, "El Mirador", self.ter1.codigo)}
        abiertos = [c for c in Compromiso.objects.filter(delegacion=self.del1, periodo=self.periodo,
                                                         estado__in=Compromiso.ABIERTOS)
                    if M.normalizar(c.territorio) in nombres]
        self.assertEqual(t["abiertos"], len(abiertos))
        self.assertEqual(t["vencidos"], sum(1 for c in abiertos if c.vencimiento < self.hoy))


class Privacidad(Base):
    def test_no_sale_ningun_dato_de_vecinos(self):
        html = self._cliente("felipe.araya@ejemplo.cl").get(URL).content.decode()
        for vecino in Solicitante.objects.all():
            for dato in (vecino.direccion, vecino.rut, vecino.telefono):
                if dato and len(dato) > 5:
                    self.assertNotIn(dato, html)
        claves = set()
        for t in datos_del_mapa(self._cliente("felipe.araya@ejemplo.cl").get(URL))["territorios"]:
            claves |= set(t)
        self.assertFalse(claves & {"direccion", "rut", "telefono", "vecinos", "correo"})

    def test_la_vista_personal_no_nombra_a_nadie_mas(self):
        r = self._cliente("marcela.rios@ejemplo.cl").get(URL)
        html = r.content.decode()
        for otro in ("Jorge Salinas", "Camila Otárola", "Pablo Fuentes"):
            self.assertNotIn(otro, html)
        datos = datos_del_mapa(r)
        self.assertTrue(all(not t["quienes"] for t in datos["territorios"]))
        # Y cuenta solo lo suyo.
        suyas = Actividad.objects.filter(territorio=self.ter1, periodo=self.periodo).exclude(
            estado=Actividad.Estado.ANULADA).filter(funcionario=self.marcela)
        self.assertEqual(por_codigo(datos)["TER-01"]["registradas"], suyas.count())

    def test_la_vista_completa_dice_quienes_fueron(self):
        t = por_codigo(datos_del_mapa(self._cliente("felipe.araya@ejemplo.cl").get(URL)))["TER-01"]
        self.assertTrue(t["quienes"])
        self.assertLessEqual(len(t["quienes"]), 3)


class Ubicacion(Base):
    def test_leer_la_ubicacion(self):
        self.assertEqual(leer_ubicacion("-29.8705, -71.2365"),
                         (Decimal("-29.870500"), Decimal("-71.236500")))
        self.assertEqual(leer_ubicacion("-29,8705; -71,2365"),
                         (Decimal("-29.870500"), Decimal("-71.236500")))
        self.assertIsNone(leer_ubicacion("  "))
        for malo, mensaje in (("-71.2365, -29.8705", "al revés"),
                              ("-33.45, -70.66", "fuera de la Región de Coquimbo"),
                              ("29.87, 71.23", "fuera de la Región de Coquimbo"),
                              ("-29.87", "separadas por una coma"),
                              ("norte, sur", "deben ser números")):
            with self.assertRaises(forms.ValidationError, msg=malo) as error:
                leer_ubicacion(malo)
            self.assertIn(mensaje, " ".join(error.exception.messages), malo)

    def test_se_guarda_y_se_borra_desde_la_ficha(self):
        ter7 = Territorio.objects.get(codigo="TER-07")
        url = reverse("organizacion:territorio_editar", args=[ter7.pk])
        datos = {"nombre": ter7.nombre, "delegacion": ter7.delegacion_id,
                 "descripcion": ter7.descripcion, "ubicacion": "-29.9205, -71.2501"}
        r = self.gestion.post(url, datos)
        self.assertEqual(r.status_code, 302)
        ter7.refresh_from_db()
        self.assertEqual((ter7.latitud, ter7.longitud), (Decimal("-29.920500"), Decimal("-71.250100")))
        self.assertContains(self.gestion.get(reverse("organizacion:territorio_detalle", args=[ter7.pk])),
                            "-29.92050, -71.25010")
        self.assertIn('value="-29.92050, -71.25010"', self.gestion.get(url).content.decode())

        self.gestion.post(url, dict(datos, ubicacion=""))
        ter7.refresh_from_db()
        self.assertIsNone(ter7.latitud)

    def test_una_ubicacion_mala_no_se_guarda(self):
        ter7 = Territorio.objects.get(codigo="TER-07")
        url = reverse("organizacion:territorio_editar", args=[ter7.pk])
        r = self.gestion.post(url, {"nombre": ter7.nombre, "delegacion": ter7.delegacion_id,
                                    "descripcion": ter7.descripcion, "ubicacion": "-71.25, -29.92"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "al revés")
        ter7.refresh_from_db()
        self.assertIsNone(ter7.latitud)

    def test_sin_ubicar_aparece_en_su_lista(self):
        r = self._cliente("felipe.araya@ejemplo.cl").get(URL)
        self.assertContains(r, "Sin ubicar en el mapa")
        self.assertIsNone(por_codigo(datos_del_mapa(r))["TER-07"]["lat"])


class RegistrarDesdeElMapa(Base):
    def test_las_acciones_segun_quien_mira(self):
        felipe = por_codigo(datos_del_mapa(self._cliente("felipe.araya@ejemplo.cl").get(URL)))["TER-01"]
        self.assertIn(reverse("gestion:registro_actividad_nueva") + f"?territorio={self.ter1.pk}",
                      felipe["acciones"][0]["url"])
        marcela = por_codigo(datos_del_mapa(self._cliente("marcela.rios@ejemplo.cl").get(URL)))["TER-01"]
        urls = [a["url"] for a in marcela["acciones"]]
        self.assertIn(reverse("gestion:actividad_nueva") + f"?territorio={self.ter1.pk}", urls)
        self.assertTrue(any(u.startswith(reverse("gestion:compromiso_nuevo") + "?territorio=") for u in urls))

    def test_mis_actividades_recibe_el_territorio(self):
        marcela = self._cliente("marcela.rios@ejemplo.cl")
        html = marcela.get(reverse("gestion:actividad_nueva"), {"territorio": self.ter1.pk}).content.decode()
        self.assertRegex(html, r'<option value="%d" selected>' % self.ter1.pk)
        ajeno = Territorio.objects.get(codigo="TER-04")
        html = marcela.get(reverse("gestion:actividad_nueva"), {"territorio": ajeno.pk}).content.decode()
        self.assertNotIn('<option value="%d"' % ajeno.pk, html)

    def test_mis_actividades_guarda_el_territorio(self):
        marcela = self._cliente("marcela.rios@ejemplo.cl")
        html = marcela.get(reverse("gestion:actividad_nueva")).content.decode()
        item = re.search(r'<select name="item"[^>]*>.*?<option value="(\d+)"', html, re.S).group(1)
        fecha = re.search(r'name="fecha" value="([0-9-]+)"', html).group(1)
        r = marcela.post(reverse("gestion:actividad_nueva"), {
            "item": item, "fecha": fecha, "cantidad": 1,
            "accion": "Recorrido por la unidad vecinal",
            "detalle": "Recorrido con la directiva para revisar luminarias del sector.",
            "contacto": "", "territorio": self.ter1.pk,
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Actividad.objects.order_by("-pk").first().territorio, self.ter1)

    def test_compromiso_con_el_territorio_puesto(self):
        marcela = self._cliente("marcela.rios@ejemplo.cl")
        del2 = Delegacion.objects.get(codigo="DEL-02")
        r = marcela.get(reverse("gestion:compromiso_nuevo"),
                        {"territorio": "Unidad vecinal 3 · San Juan", "delegacion": del2.pk})
        html = r.content.decode()
        self.assertIn('value="Unidad vecinal 3 · San Juan"', html)
        # La Antena no es suya: el compromiso queda en su delegación.
        self.assertIn("en la delegación <b>Las Compañías</b>", html)
        self.assertNotIn("<b>La Antena</b>", html)


class SinDatos(Base):
    def test_un_trimestre_sin_actividad(self):
        from gestion.models import Periodo

        otro = Periodo.objects.exclude(pk=self.periodo.pk).filter(activo=True).first()
        if otro is None:
            self.skipTest("La demostración no tiene otro trimestre visible.")
        r = self._cliente("felipe.araya@ejemplo.cl").get(URL, {"periodo": otro.pk})
        self.assertEqual(r.status_code, 200)
        for t in datos_del_mapa(r)["territorios"]:
            if Actividad.objects.filter(territorio_id=t["id"], periodo=otro).exists():
                continue
            self.assertEqual(t["registradas"], 0)

    def test_fecha_de_referencia_de_un_trimestre_cerrado(self):
        from gestion.models import Periodo

        pasado = Periodo.objects.filter(activo=True, termino__lt=self.hoy).first()
        if pasado is None:
            self.skipTest("La demostración no tiene un trimestre ya terminado.")
        r = self._cliente("felipe.araya@ejemplo.cl").get(URL, {"periodo": pasado.pk})
        self.assertEqual(datos_del_mapa(r)["referencia"], pasado.termino.strftime("%d-%m-%Y"))
        self.assertLess(pasado.termino, self.hoy + timedelta(days=1))


class Comparacion(Base):
    """«Cambio vs. trimestre anterior»: el anterior, a la misma altura."""

    def test_compara_con_el_anterior_a_la_misma_altura(self):
        from gestion.models import Periodo

        r = self._cliente("felipe.araya@ejemplo.cl").get(URL)
        datos = datos_del_mapa(r)
        self.assertIsNotNone(datos["comparacion"])
        anterior = Periodo.objects.get(codigo="PER-D01")
        corte = anterior.inicio + timedelta(days=(self.hoy - self.periodo.inicio).days)
        ter2 = Territorio.objects.get(codigo="TER-02")
        esperado = (Actividad.objects.filter(periodo=anterior, territorio=ter2, fecha__lte=corte)
                    .exclude(estado=Actividad.Estado.ANULADA).count())
        t = por_codigo(datos)["TER-02"]
        self.assertEqual(t["anterior"], esperado)
        self.assertEqual(t["cambio"], t["medida"] - esperado)
        # En la demostración Los Aromos bajó y El Mirador subió.
        self.assertLess(t["cambio"], 0)
        self.assertGreater(por_codigo(datos)["TER-01"]["cambio"], 0)
        self.assertContains(r, "Vs. anterior")

    def test_sin_anterior_no_hay_comparacion(self):
        from gestion.models import Periodo

        anterior = Periodo.objects.get(codigo="PER-D01")
        datos = datos_del_mapa(self._cliente("felipe.araya@ejemplo.cl").get(URL, {"periodo": anterior.pk}))
        self.assertIsNone(datos["comparacion"])
        self.assertTrue(all(t["anterior"] is None for t in datos["territorios"]))


class UbicarConUnClic(Base):
    def setUp(self):
        super().setUp()
        self.ter7 = Territorio.objects.get(codigo="TER-07")
        self.url = reverse("gestion:mapa_ubicar", args=[self.ter7.pk])

    def test_guarda_y_queda_en_la_auditoria(self):
        from comun.models import EventoAuditoria

        r = self.gestion.post(self.url, {"lat": "-29.920500", "lng": "-71.250100"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["ok"])
        self.ter7.refresh_from_db()
        self.assertEqual((self.ter7.latitud, self.ter7.longitud), (Decimal("-29.920500"), Decimal("-71.250100")))
        self.assertTrue(EventoAuditoria.objects.filter(detalle__icontains="mapa de presencia").exists())

    def test_misma_validacion_que_la_ficha(self):
        r = self.gestion.post(self.url, {"lat": "-33.45", "lng": "-70.66"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("Región de Coquimbo", r.json()["error"])
        self.ter7.refresh_from_db()
        self.assertIsNone(self.ter7.latitud)

    def test_sin_permiso_o_sin_post(self):
        marcela = self._cliente("marcela.rios@ejemplo.cl")
        self.assertEqual(marcela.post(self.url, {"lat": "-29.92", "lng": "-71.25"}).status_code, 403)
        self.assertEqual(self.gestion.get(self.url).status_code, 405)
        otro = reverse("gestion:mapa_ubicar", args=[999999])
        self.assertEqual(self.gestion.post(otro, {"lat": "-29.92", "lng": "-71.25"}).status_code, 404)

    def test_el_mapa_ofrece_ubicar_solo_a_quien_puede(self):
        self.assertIsNotNone(datos_del_mapa(self.gestion.get(URL))["ubicar"])
        self.assertIsNone(datos_del_mapa(self._cliente("marcela.rios@ejemplo.cl").get(URL))["ubicar"])


class SalidaATerreno(Base):
    URL = reverse("gestion:mapa_salida")

    def setUp(self):
        super().setUp()
        self.ter2 = Territorio.objects.get(codigo="TER-02")
        self.ter3 = Territorio.objects.get(codigo="TER-03")
        self.valentina = self._cliente("valentina.cortes@ejemplo.cl")
        self.yo = U.objects.get(email="valentina.cortes@ejemplo.cl")

    def test_hoja_de_ruta_en_el_orden_pedido(self):
        r = self.valentina.get(self.URL, {"t": f"{self.ter3.pk},{self.ter2.pk}"})
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertLess(html.index(self.ter3.nombre), html.index(self.ter2.nombre))
        self.assertContains(r, "Dejarla planificada")
        self.assertContains(r, "km de la parada anterior")

    def test_planifica_un_hito_por_parada(self):
        from gestion.modelos_hitos import Hito

        manana = self.hoy + timedelta(days=1)
        antes = Hito.objects.count()
        r = self.valentina.post(self.URL, {"t": [self.ter2.pk, self.ter3.pk], "fecha": str(manana),
                                           "responsables": [self.yo.pk], "nombre": ""})
        self.assertEqual(r.status_code, 302)
        nuevos = list(Hito.objects.order_by("-pk")[:2])
        self.assertEqual(Hito.objects.count(), antes + 2)
        self.assertEqual({h.territorio_id for h in nuevos}, {self.ter2.pk, self.ter3.pk})
        self.assertTrue(all(h.fecha_inicio == manana and h.fecha_termino == manana for h in nuevos))
        self.assertTrue(all(list(h.responsables.all()) == [self.yo] for h in nuevos))
        # El mapa ya los cuenta.
        t = por_codigo(datos_del_mapa(self.valentina.get(URL)))["TER-02"]
        self.assertGreaterEqual(t["hitos"], 1)

    def test_no_se_planifica_en_el_pasado_ni_con_gente_de_otra_delegacion(self):
        from gestion.modelos_hitos import Hito

        antes = Hito.objects.count()
        r = self.valentina.post(self.URL, {"t": [self.ter2.pk], "fecha": str(self.hoy - timedelta(days=1)),
                                           "responsables": [self.yo.pk]})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "no para una fecha pasada")
        ter4 = Territorio.objects.get(codigo="TER-04")
        r = self.valentina.post(self.URL, {"t": [self.ter2.pk, ter4.pk], "fecha": str(self.hoy + timedelta(days=2)),
                                           "responsables": [self.marcela.pk]})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "ni tiene alcance")
        self.assertEqual(Hito.objects.count(), antes)

    def test_quien_no_crea_hitos_solo_la_imprime(self):
        marcela = self._cliente("marcela.rios@ejemplo.cl")
        r = marcela.get(self.URL, {"t": self.ter2.pk})
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'name="responsables"')
        self.assertContains(r, "Para llevarla impresa")
        self.assertContains(r, "Imprimir hoja de ruta")
        r = marcela.post(self.URL, {"t": [self.ter2.pk], "fecha": str(self.hoy + timedelta(days=1)),
                                    "responsables": [self.marcela.pk]})
        self.assertEqual(r.status_code, 403)

    def test_fuera_del_alcance_queda_fuera(self):
        pablo = self._cliente("pablo.fuentes@ejemplo.cl")
        ter4 = Territorio.objects.get(codigo="TER-04")
        r = pablo.get(self.URL, {"t": f"{self.ter2.pk},{ter4.pk}"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Un territorio quedó fuera")
        self.assertNotContains(r, ter4.nombre)
        r = pablo.get(self.URL, {"t": str(ter4.pk)})
        self.assertEqual(r.status_code, 302)

    def test_la_hoja_no_trae_datos_de_vecinos(self):
        html = self.valentina.get(self.URL, {"t": f"{self.ter2.pk},{self.ter3.pk}"}).content.decode()
        for vecino in Solicitante.objects.all():
            for dato in (vecino.direccion, vecino.rut, vecino.telefono):
                if dato and len(dato) > 5:
                    self.assertNotIn(dato, html)
