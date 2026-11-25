"""
Reglas de la guía de la evaluación 3, grupo 2:

* contraseña temporal al crear un usuario y cambio obligatorio al entrar;
* «solicitud de más antecedentes» en la revisión de evidencias;
* reglas del cliente: siete actividades por día, coordinaciones que no
  ponderan, el delegado como usuario no contabiliza, sin nombre y teléfono
  del usuario no hay puntaje y las felicitaciones valen con el respaldo del
  delegado.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse

from atencion.models import Solicitante
from comun.models import EventoAuditoria
from comun.resultado import CLAVE as CLAVE_RESULTADO
from gestion.calculo import _aprobadas_por_item, reconocimientos_de
from gestion.modelos_actividad import Actividad, Evidencia
from gestion.modelos_ajustes import Reconocimiento
from gestion.modelos_agenda import Compromiso
from organizacion.models import PerfilUsuario

from pruebas.test_evaluacion3 import Base, rut

U = get_user_model()


class ClaveTemporal(Base):
    def crear(self):
        admin = self._cliente("felipe.araya@ejemplo.cl")
        r = admin.post(reverse("organizacion:usuario_nuevo"), self.datos("usuario"))
        self.assertEqual(r.status_code, 302)
        perfil = PerfilUsuario.objects.get(usuario__email="paula.prueba@ejemplo.cl")
        texto = admin.session[CLAVE_RESULTADO]["texto"]
        clave = texto.split(" es ")[1].split(" ")[0]
        return admin, perfil, clave

    def test_la_cuenta_nace_con_una_temporal_que_se_muestra_una_vez(self):
        _, perfil, clave = self.crear()
        self.assertTrue(perfil.debe_cambiar_clave)
        self.assertTrue(perfil.usuario.check_password(clave))
        self.assertRegex(clave, r"^[A-Za-z0-9]{4}-[A-Za-z0-9]{4}-[A-Za-z0-9]{4}$")

    def test_hasta_cambiarla_no_pasa_de_la_pantalla_de_cambio(self):
        _, perfil, clave = self.crear()
        c = Client()
        r = c.post(reverse("cuenta:login"), {"username": perfil.correo, "password": clave}, follow=True)
        self.assertEqual(r.redirect_chain[-1][0], reverse("cuenta:cambiar_clave"))
        for url in (reverse("comun:panel"), reverse("gestion:agenda"), "/admin/"):
            self.assertRedirects(c.get(url), reverse("cuenta:cambiar_clave"),
                                 fetch_redirect_response=False, msg_prefix=url)

    def test_la_nueva_no_puede_ser_la_temporal_y_despues_entra(self):
        _, perfil, clave = self.crear()
        c = Client()
        c.post(reverse("cuenta:login"), {"username": perfil.correo, "password": clave})
        r = c.post(reverse("cuenta:cambiar_clave"), {"new_password1": clave, "new_password2": clave})
        self.assertContains(r, "distinta de la contraseña temporal")
        nueva = "Mi-Clave-Propia-2026"
        r = c.post(reverse("cuenta:cambiar_clave"), {"new_password1": nueva, "new_password2": nueva})
        self.assertRedirects(r, reverse("comun:panel"), fetch_redirect_response=False)
        perfil.refresh_from_db()
        self.assertFalse(perfil.debe_cambiar_clave)
        self.assertEqual(c.get(reverse("gestion:agenda")).status_code, 200)
        self.assertFalse(perfil.usuario.__class__.objects.get(pk=perfil.usuario_id).check_password(clave))

    def test_el_administrador_emite_otra_y_queda_en_la_auditoria(self):
        admin = self._cliente("felipe.araya@ejemplo.cl")
        perfil = PerfilUsuario.objects.get(usuario__email="marcela.rios@ejemplo.cl")
        admin.post(reverse("organizacion:usuario_clave_temporal", args=[perfil.pk]))
        perfil.refresh_from_db()
        self.assertTrue(perfil.debe_cambiar_clave)
        evento = EventoAuditoria.objects.filter(entidad="Usuario").latest("pk")
        self.assertIn("temporal", evento.despues)
        clave = admin.session[CLAVE_RESULTADO]["texto"].split(" es ")[1].split(" ")[0]
        self.assertNotIn(clave, evento.despues + evento.detalle + evento.antes)

    def test_nadie_emite_la_suya_ni_sin_permiso(self):
        felipe = PerfilUsuario.objects.get(usuario__email="felipe.araya@ejemplo.cl")
        marcela = PerfilUsuario.objects.get(usuario__email="marcela.rios@ejemplo.cl")
        self.assertEqual(self._cliente("felipe.araya@ejemplo.cl").post(
            reverse("organizacion:usuario_clave_temporal", args=[felipe.pk])).status_code, 403)
        self.assertEqual(self._cliente("marcela.rios@ejemplo.cl").post(
            reverse("organizacion:usuario_clave_temporal", args=[marcela.pk])).status_code, 403)

    def test_recuperar_por_correo_tambien_saca_la_marca(self):
        from cuenta.models import CodigoRecuperacion

        perfil = PerfilUsuario.objects.get(usuario__email="marcela.rios@ejemplo.cl")
        PerfilUsuario.objects.filter(pk=perfil.pk).update(debe_cambiar_clave=True)
        c = Client()
        c.post(reverse("cuenta:recuperar"), {"correo": perfil.correo})
        codigo = CodigoRecuperacion.objects.filter(usuario=perfil.usuario).first().codigo
        c.post(reverse("cuenta:codigo"), {"codigo": codigo})
        c.post(reverse("cuenta:nueva_clave"), {"new_password1": "Otra-Clave-Larga-9", "new_password2": "Otra-Clave-Larga-9"})
        perfil.refresh_from_db()
        self.assertFalse(perfil.debe_cambiar_clave)


class MasAntecedentes(Base):
    def setUp(self):
        super().setUp()
        self.ev = Evidencia.objects.filter(
            decision=Evidencia.Decision.PENDIENTE, anulada=False,
            actividad__delegacion=self.del1).exclude(actividad__funcionario__email="pablo.fuentes@ejemplo.cl").first()
        self.url = reverse("gestion:evidencia_decidir", args=[self.ev.pk, "antecedentes"])

    def test_el_verificador_los_pide_con_su_motivo(self):
        pablo = self._cliente("pablo.fuentes@ejemplo.cl")
        r = pablo.post(self.url, {"motivo": "Falta la lista de asistencia firmada por la directiva."})
        self.assertEqual(r.status_code, 302)
        self.ev.refresh_from_db()
        self.assertEqual(self.ev.decision, Evidencia.Decision.ANTECEDENTES)
        self.assertEqual(self.ev.actividad.estado, Actividad.Estado.ANTECEDENTES)
        self.assertEqual(EventoAuditoria.objects.latest("pk").accion, EventoAuditoria.Accion.ANTECEDENTES)

    def test_sin_motivo_no_se_piden(self):
        self._cliente("pablo.fuentes@ejemplo.cl").post(self.url, {"motivo": "falta"})
        self.ev.refresh_from_db()
        self.assertEqual(self.ev.decision, Evidencia.Decision.PENDIENTE)

    def test_vuelve_al_autor_que_completa_y_queda_pendiente(self):
        self._cliente("pablo.fuentes@ejemplo.cl").post(
            self.url, {"motivo": "Falta la lista de asistencia firmada por la directiva."})
        autor = self.ev.actividad.funcionario
        c = self._cliente(autor.email)
        ficha = c.get(reverse("gestion:actividad_detalle", args=[self.ev.actividad_id]))
        self.assertTrue(ficha.context["puede_adjuntar"])
        self.assertContains(ficha, "Te piden más antecedentes")
        self.assertContains(c.get(reverse("comun:panel")), "Te piden más antecedentes")
        self.assertEqual(c.get(reverse("gestion:evidencia_nueva", args=[self.ev.actividad_id])).status_code, 200)

    def test_no_cuenta_como_rechazo_ni_suma(self):
        antes = _aprobadas_por_item(self.periodo, funcionario=self.ev.actividad.funcionario)
        self._cliente("pablo.fuentes@ejemplo.cl").post(
            self.url, {"motivo": "Falta la lista de asistencia firmada por la directiva."})
        self.assertFalse(Evidencia.objects.filter(pk=self.ev.pk, decision=Evidencia.Decision.RECHAZADA).exists())
        self.assertEqual(_aprobadas_por_item(self.periodo, funcionario=self.ev.actividad.funcionario), antes)

    def test_la_pantalla_del_verificador_ofrece_el_boton(self):
        r = self._cliente("pablo.fuentes@ejemplo.cl").get(reverse("gestion:evidencia_detalle", args=[self.ev.pk]))
        self.assertContains(r, "Pedir más antecedentes")


class LimiteDiario(Base):
    def nueva(self, fecha, n):
        base = Actividad.objects.filter(funcionario=self.marcela).first()
        return Actividad(
            codigo=f"ACT-8{n:03d}", funcionario=self.marcela, delegacion=base.delegacion,
            periodo=base.periodo, item=base.item, asignacion=base.asignacion, fecha=fecha,
            cantidad=1, accion="Actividad del límite diario", detalle="Detalle suficiente para la prueba del límite.")

    def test_la_octava_del_mismo_dia_se_rechaza(self):
        dia = self.hoy
        ya = Actividad.objects.filter(funcionario=self.marcela, fecha=dia).exclude(estado="anulada").count()
        for n in range(7 - ya):
            self.nueva(dia, n).save()
        with self.assertRaises(ValidationError) as e:
            self.nueva(dia, 99).full_clean()
        self.assertIn("máximo por día", str(e.exception))

    def test_las_anuladas_no_cuentan(self):
        dia = self.hoy
        ya = Actividad.objects.filter(funcionario=self.marcela, fecha=dia).exclude(estado="anulada").count()
        for n in range(7 - ya):
            a = self.nueva(dia, n)
            a.save()
        Actividad.objects.filter(pk=a.pk).update(estado=Actividad.Estado.ANULADA)
        self.nueva(dia, 99).full_clean()


class NoPuntuan(Base):
    def setUp(self):
        super().setUp()
        self.act = Actividad.objects.filter(estado=Actividad.Estado.APROBADA, funcionario=self.marcela).first()
        self.suma = lambda: _aprobadas_por_item(self.periodo, funcionario=self.marcela).get(self.act.item_id, 0)
        self.antes = self.suma()

    def test_una_coordinacion_preparatoria_no_pondera(self):
        Actividad.objects.filter(pk=self.act.pk).update(tipo=Actividad.Tipo.COORDINACION)
        self.act.refresh_from_db()
        self.assertEqual(self.suma(), self.antes - self.act.cantidad)
        self.assertIn("coordinación preparatoria", self.act.motivo_no_puntua)
        self.assertFalse(self.act.puntua)

    def vecino(self, rut_, telefono="51 2 200 100", nombres="Rosa"):
        return Solicitante.objects.create(rut=rut_, nombres=nombres, apellidos="Prueba",
                                          telefono=telefono, territorio=self.ter1)

    def test_sin_nombre_y_telefono_del_usuario_no_puntua(self):
        Actividad.objects.filter(pk=self.act.pk).update(
            origen=Actividad.Origen.COMUNIDAD, solicitante=self.vecino(rut(901), telefono=""))
        self.act.refresh_from_db()
        self.assertEqual(self.suma(), self.antes - self.act.cantidad)
        self.assertIn("teléfono", self.act.motivo_no_puntua)
        Actividad.objects.filter(pk=self.act.pk).update(solicitante=self.vecino(rut(902)))
        self.assertEqual(self.suma(), self.antes)
        Actividad.objects.filter(pk=self.act.pk).update(solicitante=None)
        self.assertEqual(self.suma(), self.antes - self.act.cantidad)

    def test_si_el_usuario_es_el_delegado_no_contabiliza(self):
        soledad = PerfilUsuario.objects.get(usuario__email="soledad.guerrero@ejemplo.cl")
        self.assertTrue(soledad.rut)
        Actividad.objects.filter(pk=self.act.pk).update(solicitante=self.vecino(soledad.rut))
        self.act.refresh_from_db()
        self.assertEqual(self.suma(), self.antes - self.act.cantidad)
        self.assertIn("delegado", self.act.motivo_no_puntua)

    def test_una_solicitud_del_delegado_no_cuenta_en_el_tubo(self):
        soledad = PerfilUsuario.objects.get(usuario__email="soledad.guerrero@ejemplo.cl")
        cmp = Compromiso.objects.filter(delegacion=self.del1).first()
        todos = Compromiso.que_cuentan(Compromiso.objects.filter(delegacion=self.del1)).count()
        Compromiso.objects.filter(pk=cmp.pk).update(vecino=self.vecino(soledad.rut))
        self.assertEqual(Compromiso.que_cuentan(Compromiso.objects.filter(delegacion=self.del1)).count(), todos - 1)

    def test_la_ficha_lo_explica(self):
        Actividad.objects.filter(pk=self.act.pk).update(tipo=Actividad.Tipo.COORDINACION)
        r = self._cliente("marcela.rios@ejemplo.cl").get(reverse("gestion:actividad_detalle", args=[self.act.pk]))
        self.assertContains(r, "No puntúa")


class Felicitaciones(Base):
    def setUp(self):
        super().setUp()
        self.perfil = PerfilUsuario.objects.get(usuario=self.marcela)

    def registrar(self, correo):
        c = self._cliente(correo)
        r = c.post(reverse("gestion:reconocimiento_nuevo"), {
            "tipo": "felicitacion", "funcionario": self.marcela.pk, "periodo": self.periodo.pk,
            "fecha": max(self.periodo.inicio, self.hoy - timedelta(days=1)).isoformat(),
            "medio": "correo", "presentado_por": "Junta de vecinos de prueba",
            "situacion": "Felicita la atención en la entrega de beneficios.",
            "respaldo": "Correo del 20-11 al delegado", "informado_a": ""})
        self.assertEqual(r.status_code, 302, getattr(r, "context", None) and r.context["form"].errors)
        return Reconocimiento.objects.latest("pk")

    def test_la_que_registra_el_delegado_queda_respaldada(self):
        antes, _ = reconocimientos_de(self.perfil, self.periodo)
        registro = self.registrar("soledad.guerrero@ejemplo.cl")
        self.assertIsNotNone(registro.respaldada_por_id)
        self.assertEqual(reconocimientos_de(self.perfil, self.periodo)[0], antes + 1)

    def test_otra_espera_el_respaldo_del_delegado(self):
        antes, _ = reconocimientos_de(self.perfil, self.periodo)
        registro = self.registrar("valentina.cortes@ejemplo.cl")
        self.assertIsNone(registro.respaldada_por_id)
        self.assertEqual(reconocimientos_de(self.perfil, self.periodo)[0], antes)
        url = reverse("gestion:reconocimiento_respaldar", args=[registro.pk])
        self.assertEqual(self._cliente("valentina.cortes@ejemplo.cl").post(url).status_code, 403)
        ficha = self._cliente("soledad.guerrero@ejemplo.cl").get(
            reverse("gestion:reconocimiento_detalle", args=[registro.pk]))
        self.assertContains(ficha, "Respaldar la felicitación")
        self._cliente("soledad.guerrero@ejemplo.cl").post(url)
        registro.refresh_from_db()
        self.assertIsNotNone(registro.respaldada_por_id)
        self.assertEqual(reconocimientos_de(self.perfil, self.periodo)[0], antes + 1)
