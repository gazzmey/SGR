"""
Reglas de la guía de la evaluación 3, grupo 1:

* cierre semanal: una semana cerrada no admite gestiones nuevas;
* un registro aprobado ya no se modifica;
* el Tubo: todos consultan, cada funcionario modifica solo lo suyo, y se
  busca por código, RUT o nombre, con filtro por funcionario y por fechas.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse

from atencion.models import Solicitante
from gestion.modelos_actividad import Actividad, Evidencia
from gestion.modelos_agenda import Compromiso
from gestion.reglas import ReglaCalculo, vigente
from gestion.semanas import cierre_de, lunes_de, motivo_semana_cerrada

from pruebas.test_evaluacion3 import Base

U = get_user_model()


class CierreSemanal(Base):
    def setUp(self):
        super().setUp()
        self.cerrada = lunes_de(self.hoy) - timedelta(days=14)      # hace dos semanas
        self.abierta = self.hoy
        if not (self.periodo.inicio <= self.cerrada <= self.periodo.termino):
            self.skipTest("La semana cerrada de prueba cae fuera del período de demostración.")

    def copia(self, fecha):
        base = Actividad.objects.filter(funcionario=self.marcela, estado=Actividad.Estado.BORRADOR).first() \
            or Actividad.objects.filter(funcionario=self.marcela).first()
        return Actividad(
            codigo="ACT-9999", funcionario=self.marcela, delegacion=base.delegacion,
            periodo=base.periodo, item=base.item, asignacion=base.asignacion, fecha=fecha,
            cantidad=1, accion="Prueba del cierre semanal", detalle="Detalle suficiente para la prueba del cierre.",
        )

    def test_las_fechas_del_cierre(self):
        lunes = lunes_de(self.hoy)
        self.assertEqual(lunes.weekday(), 0)
        self.assertEqual(cierre_de(lunes, 1), lunes + timedelta(days=7))     # el lunes siguiente
        self.assertEqual(cierre_de(lunes + timedelta(days=6), 0), lunes + timedelta(days=6))

    def test_una_semana_cerrada_no_admite_actividades_nuevas(self):
        with self.assertRaises(ValidationError) as e:
            self.copia(self.cerrada).full_clean()
        self.assertIn("se cerró", str(e.exception))

    def test_la_semana_en_curso_si_las_admite(self):
        self.copia(self.abierta).full_clean()

    def test_los_dias_de_gracia_se_configuran(self):
        regla = vigente(self.periodo)
        self.assertTrue(motivo_semana_cerrada(self.cerrada, self.periodo))
        ReglaCalculo.objects.filter(pk=regla.pk).update(dias_gracia_semana=30)
        self.assertEqual(motivo_semana_cerrada(self.cerrada, self.periodo), "")
        self.copia(self.cerrada).full_clean()

    def test_completar_una_existente_de_una_semana_cerrada_si_se_puede(self):
        act = self.copia(self.abierta)
        act.save()
        Actividad.objects.filter(pk=act.pk).update(fecha=self.cerrada)
        act.refresh_from_db()
        act.resultado = "Se completó después, sin cambiar la fecha."
        act.full_clean()

    def test_no_se_mueve_la_fecha_hacia_una_semana_cerrada(self):
        act = self.copia(self.abierta)
        act.save()
        act.fecha = self.cerrada
        with self.assertRaises(ValidationError):
            act.full_clean()

    def test_por_la_pantalla_se_rechaza_y_no_se_guarda(self):
        c = self._cliente("marcela.rios@ejemplo.cl")
        formulario = c.get(reverse("gestion:actividad_nueva")).context["form"]
        item = formulario.fields["item"].queryset.first()
        antes = Actividad.objects.count()
        r = c.post(reverse("gestion:actividad_nueva"), {
            "item": item.pk, "fecha": self.cerrada.isoformat(), "cantidad": 1,
            "accion": "Reunión de una semana cerrada",
            "detalle": "Una reunión que se quiso ingresar cuando la semana ya estaba cerrada.",
        })
        self.assertEqual(Actividad.objects.count(), antes)
        self.assertContains(r, "se cerró")


class AprobadoNoSeModifica(Base):
    def test_una_actividad_aprobada_no_se_edita(self):
        act = Actividad.objects.filter(estado=Actividad.Estado.APROBADA, delegacion=self.del1).first()
        url = reverse("gestion:registro_actividad_editar", args=[act.pk])
        r = self.gestion.get(url)
        self.assertRedirects(r, reverse("gestion:registro_actividad", args=[act.pk]))
        detalle_antes = act.detalle
        self.gestion.post(url, {"detalle": "Intento de cambiar lo aprobado por la dirección."})
        act.refresh_from_db()
        self.assertEqual(act.detalle, detalle_antes)
        ficha = self.gestion.get(reverse("gestion:registro_actividad", args=[act.pk]))
        self.assertContains(ficha, "Ya no se edita")
        self.assertNotContains(ficha, 'href="%s"' % url)

    def test_una_pendiente_si_se_edita(self):
        act = Actividad.objects.filter(estado=Actividad.Estado.PENDIENTE, delegacion=self.del1).first()
        r = self.gestion.get(reverse("gestion:registro_actividad_editar", args=[act.pk]))
        self.assertEqual(r.status_code, 200)

    def test_una_evidencia_aprobada_no_se_edita(self):
        ev = Evidencia.objects.filter(decision=Evidencia.Decision.APROBADA, anulada=False,
                                      actividad__delegacion=self.del1).first()
        url = reverse("gestion:registro_evidencia_editar", args=[ev.pk])
        r = self.gestion.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertNotIn("/editar/", r["Location"])


class Tubo(Base):
    def setUp(self):
        super().setUp()
        self.de_camila = Compromiso.objects.filter(
            delegacion=self.del1, responsable__email="camila.otarola@ejemplo.cl",
            estado__in=Compromiso.ABIERTOS).first()
        self.ficha = reverse("gestion:compromiso_detalle", args=[self.de_camila.pk])

    def test_un_colega_lo_consulta_pero_no_lo_mueve(self):
        marcela = self._cliente("marcela.rios@ejemplo.cl")
        r = marcela.get(self.ficha)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "responsable del compromiso, lo mueve de estado")
        estado = self.de_camila.estado
        paso = "en_proceso" if estado != Compromiso.Estado.EN_PROCESO else "realizado"
        r = marcela.post(reverse("gestion:compromiso_paso", args=[self.de_camila.pk, paso]),
                         {"observacion": ""})
        self.assertEqual(r.status_code, 403)
        self.de_camila.refresh_from_db()
        self.assertEqual(self.de_camila.estado, estado)

    def test_el_responsable_si_lo_mueve(self):
        camila = self._cliente("camila.otarola@ejemplo.cl")
        pasos = camila.get(self.ficha).context["pasos"]
        self.assertTrue(pasos)
        r = camila.post(pasos[0]["url"], {"observacion": "Avance registrado en la prueba."})
        self.assertEqual(r.status_code, 302)
        self.de_camila.refresh_from_db()
        self.assertNotEqual(self.de_camila.cambios.count(), 0)

    def test_la_delegada_sigue_reasignando(self):
        r = self._cliente("soledad.guerrero@ejemplo.cl").get(self.ficha)
        self.assertIsNotNone(r.context["form_reasignar"])

    def _vecino(self):
        return Solicitante.objects.filter(activo=True, territorio__delegacion=self.del1).first()

    def test_el_formulario_enlaza_al_vecino_por_rut_o_por_nombre(self):
        from gestion.forms_agenda import CompromisoForm
        from organizacion.models import PerfilUsuario

        vecino = self._vecino()
        perfil = PerfilUsuario.objects.get(usuario=self.marcela)
        base = {"origen": "externo", "territorio": "Prueba",
                "descripcion": "Revisar la luminaria de la esquina y reponerla.",
                "responsable": self.marcela.pk,
                "vencimiento": (self.hoy + timedelta(days=10)).isoformat()}
        cuerpo, dv = vecino.rut.split("-")
        con_puntos = f"{int(cuerpo):,}".replace(",", ".") + "-" + dv
        f = CompromisoForm({**base, "solicitante": con_puntos}, perfil=perfil, periodo=self.periodo)
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(f.instance.vecino, vecino)
        self.assertEqual(f.cleaned_data["solicitante"], vecino.nombre)
        f = CompromisoForm({**base, "solicitante": vecino.nombre.upper()}, perfil=perfil, periodo=self.periodo)
        self.assertTrue(f.is_valid(), f.errors)
        self.assertEqual(f.instance.vecino, vecino)
        f = CompromisoForm({**base, "solicitante": "Junta de vecinos inventada"}, perfil=perfil, periodo=self.periodo)
        self.assertTrue(f.is_valid(), f.errors)
        self.assertIsNone(f.instance.vecino)

    def test_se_busca_por_rut_con_o_sin_puntos_y_por_nombre(self):
        vecino = self._vecino()
        Compromiso.objects.filter(pk=self.de_camila.pk).update(vecino=vecino)
        marcela = self._cliente("marcela.rios@ejemplo.cl")
        url = reverse("gestion:agenda")
        cuerpo, dv = vecino.rut.split("-")
        con_puntos = f"{int(cuerpo):,}".replace(",", ".") + "-" + dv
        for termino in (vecino.rut, con_puntos, cuerpo[-5:], vecino.apellidos.split(" ")[0]):
            r = marcela.get(url, {"q": termino})
            self.assertContains(r, self.de_camila.codigo, msg_prefix=termino)
        self.assertNotContains(marcela.get(url, {"q": "99.999.999-9"}), self.de_camila.codigo)

    def test_filtro_por_funcionario_y_por_fechas(self):
        url = reverse("gestion:agenda")
        c = self._cliente("marcela.rios@ejemplo.cl")
        camila = U.objects.get(email="camila.otarola@ejemplo.cl")
        r = c.get(url, {"quien": camila.pk, "situacion": "todos", "tam": 50})
        codigos = {f["obj"].codigo for f in r.context["cuerpo"]}
        self.assertIn(self.de_camila.codigo, codigos)
        self.assertTrue(all(f["obj"].responsable_id == camila.pk for f in r.context["cuerpo"]))
        opciones = dict(next(f for f in r.context["filtros"] if f["clave"] == "quien")["opciones"])
        self.assertIn(str(camila.pk), opciones)
        self.assertNotIn(str(U.objects.get(email="hector.pizarro@ejemplo.cl").pk), opciones,
                         "El filtro no ofrece gente de delegaciones que no se ven")
        from django.utils import timezone

        creado = timezone.localtime(self.de_camila.creado).date()
        dentro = c.get(url, {"situacion": "todos", "desde": creado.isoformat(),
                             "hasta": creado.isoformat(), "tam": 50})
        self.assertIn(self.de_camila.codigo, {f["obj"].codigo for f in dentro.context["cuerpo"]})
        fuera = c.get(url, {"situacion": "todos", "desde": (creado + timedelta(days=1)).isoformat(), "tam": 50})
        self.assertNotIn(self.de_camila.codigo, {f["obj"].codigo for f in fuera.context["cuerpo"]})
        self.assertIn("ingresado", fuera.context["descripcion_filtros"])

    def test_el_listado_busca_mientras_se_escribe(self):
        r = self._cliente("marcela.rios@ejemplo.cl").get(reverse("gestion:agenda"))
        self.assertContains(r, "data-buscar-vivo")
        self.assertContains(r, 'data-vivo="resultados"')
        self.assertContains(r, 'data-vivo="exportar"')
        self.assertContains(r, 'name="desde"')
