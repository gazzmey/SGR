"""
SEG-06 del protocolo de pruebas: retención de datos personales de los vecinos.

El comando ``aplicar_retencion`` anonimiza a los vecinos sin movimiento dentro
del plazo de conservación, salvo los que integran una junta o tienen un caso
social en curso. Por omisión solo informa.
"""

import io
import os
from datetime import date

from django.core.management import call_command
from django.core.management.base import CommandError

from atencion.models import Atencion, CasoSocial, Solicitante
from atencion.modelos_regalos import InscripcionRegalo
from comun.models import EventoAuditoria

from pruebas.test_evaluacion3 import Base

FUTURO = "2040-01-01"   # con 60 meses, el corte queda en 2035: todo lo de la demostración es anterior


def correr(*args):
    salida = io.StringIO()
    call_command("aplicar_retencion", *args, stdout=salida)
    return salida.getvalue()


class Retencion(Base):
    def setUp(self):
        super().setUp()
        self.protegidos = set(Solicitante.objects.filter(participaciones__activo=True).values_list("pk", flat=True))
        self.protegidos |= set(Atencion.objects.filter(caso__estado=CasoSocial.Estado.EN_CURSO)
                               .values_list("solicitante_id", flat=True))
        self.todos = set(Solicitante.objects.values_list("pk", flat=True))

    def test_hoy_no_hay_nadie_vencido(self):
        texto = correr("--aplicar")
        self.assertIn("Vecinos que cumplen el plazo: 0.", texto)
        self.assertFalse(Solicitante.objects.filter(rut__startswith="ANON-").exists())

    def test_sin_aplicar_solo_informa_y_no_muestra_datos_personales(self):
        v = Solicitante.objects.exclude(pk__in=self.protegidos).first()
        texto = correr("--al-dia", FUTURO)
        self.assertIn("No se cambió nada", texto)
        self.assertNotIn(v.rut, texto)
        self.assertNotIn(v.nombres, texto)
        self.assertFalse(Solicitante.objects.filter(rut__startswith="ANON-").exists())

    def test_anonimiza_los_vencidos_y_respeta_juntas_y_casos_abiertos(self):
        self.assertTrue(self.protegidos, "la demostración tiene vecinos en juntas o con casos abiertos")
        v = Solicitante.objects.exclude(pk__in=self.protegidos).first()
        rut_original = v.rut
        # Un evento de auditoría con la copia de sus datos, como deja el mantenedor.
        EventoAuditoria.objects.create(accion=EventoAuditoria.Accion.EDITAR, entidad="Vecino", objeto_id=v.pk,
                                       objeto_texto=str(v), antes=f"teléfono {v.telefono}", despues="teléfono 999")
        correr("--al-dia", FUTURO, "--aplicar")
        v.refresh_from_db()
        self.assertEqual(v.rut, f"ANON-{v.pk}")
        self.assertEqual((v.nombres, v.apellidos, v.telefono, v.correo, v.direccion), ("Vecino anonimizado", "", "", "", ""))
        self.assertFalse(v.activo)
        # Sus atenciones siguen existiendo: los informes de su época no cambian.
        self.assertEqual(Atencion.objects.filter(solicitante=v).count(),
                         Atencion.objects.filter(solicitante_id=v.pk).count())
        # La auditoría del vecino ya no guarda sus datos.
        ev = EventoAuditoria.objects.filter(entidad="Vecino", objeto_id=v.pk)
        self.assertFalse(ev.filter(objeto_texto__contains=rut_original).exists())
        self.assertFalse(ev.exclude(antes="").exclude(antes__startswith="[datos personales").exists())
        # Los protegidos quedan como estaban.
        self.assertFalse(Solicitante.objects.filter(pk__in=self.protegidos, rut__startswith="ANON-").exists())
        # Los niños inscritos por vecinos anonimizados pierden su RUT.
        anon = Solicitante.objects.filter(rut__startswith="ANON-")
        self.assertFalse(InscripcionRegalo.objects.filter(apoderado__in=anon).exclude(rut_menor__startswith="ANON-").exists())
        # Y queda un evento del proceso, sin datos personales.
        proceso = EventoAuditoria.objects.get(entidad="Retención de datos")
        self.assertIn("60 meses", proceso.detalle)

    def test_es_repetible(self):
        correr("--al-dia", FUTURO, "--aplicar")
        n = Solicitante.objects.filter(rut__startswith="ANON-").count()
        texto = correr("--al-dia", FUTURO, "--aplicar")
        self.assertIn("Vecinos que cumplen el plazo: 0.", texto)
        self.assertEqual(Solicitante.objects.filter(rut__startswith="ANON-").count(), n)

    def test_el_plazo_viene_del_env_y_no_puede_ser_absurdo(self):
        os.environ["SGR_RETENCION_MESES"] = "6"
        try:
            with self.assertRaises(CommandError):
                call_command("aplicar_retencion", stdout=io.StringIO())
        finally:
            del os.environ["SGR_RETENCION_MESES"]
