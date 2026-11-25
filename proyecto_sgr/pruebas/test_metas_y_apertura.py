"""
Defectos DEF-04 y DEF-05 del protocolo de pruebas (casos PAR-02 y PAR-03).

* DEF-04: un período se podía abrir con un cargo cuyas ponderaciones no
  sumaban 100 %. Ahora la apertura lo impide y dice qué cargo falta.
* DEF-05: un ítem con unidad porcentaje aceptaba metas sobre 100.
"""

from datetime import date

from django.core.exceptions import ValidationError
from django.urls import reverse

from catalogos.models import Item
from gestion.models import Cargo, MetaPeriodo, Periodo

from pruebas.test_evaluacion3 import Base


class AperturaConPonderaciones(Base):
    def setUp(self):
        super().setUp()
        self.coord = self._cliente("valentina.cortes@ejemplo.cl")
        self.p = Periodo.objects.create(codigo="PER-T9", nombre="Abr – Jun 2027 prueba", anio=2027, numero=2,
                                        inicio=date(2027, 4, 1), termino=date(2027, 6, 30))
        self.cargo = Cargo.objects.get(codigo="CAR-01")
        self.m1 = MetaPeriodo.objects.create(periodo=self.p, item=Item.objects.get(codigo="ITM-01"),
                                             cargo=self.cargo, meta=10, ponderador=40)
        self.m2 = MetaPeriodo.objects.create(periodo=self.p, item=Item.objects.get(codigo="ITM-02"),
                                             cargo=self.cargo, meta=20, ponderador=59)

    def abrir(self):
        self.coord.post(reverse("gestion:periodo_paso", args=[self.p.pk, "abrir"]))
        self.p.refresh_from_db()
        return self.p.estado

    def test_con_99_no_se_abre(self):
        self.assertEqual(self.p.cargos_sin_100(), [(self.cargo, 99)])
        self.assertEqual(self.abrir(), Periodo.Estado.BORRADOR)

    def test_con_100_si_se_abre(self):
        MetaPeriodo.objects.filter(pk=self.m2.pk).update(ponderador=60)
        self.assertEqual(self.p.cargos_sin_100(), [])
        self.assertEqual(self.abrir(), Periodo.Estado.ABIERTO)


class MetaEnPorcentaje(Base):
    def test_un_item_en_porcentaje_no_acepta_meta_sobre_100(self):
        item = Item.objects.get(codigo="ITM-06")
        self.assertEqual(item.unidad, Item.Unidad.PORCENTAJE)
        p = Periodo.objects.get(codigo="PER-D02")
        m = MetaPeriodo(periodo=p, item=item, cargo=Cargo.objects.get(codigo="CAR-02"), meta=120, ponderador=10)
        with self.assertRaises(ValidationError) as e:
            m.full_clean()
        self.assertIn("meta", e.exception.message_dict)
        m.meta = 80
        m.full_clean()


class DosPeriodosAbiertos(Base):
    """DEF-12: con el trimestre siguiente ya abierto, se sigue registrando en el de hoy."""

    def test_el_periodo_en_curso_es_el_que_contiene_hoy(self):
        from gestion.views_actividad import periodo_abierto

        actual = Periodo.objects.get(codigo="PER-01")
        futuro = Periodo.objects.create(codigo="PER-T8", nombre="Abr – Jun 2027 futuro", anio=2027, numero=2,
                                        inicio=date(2027, 4, 1), termino=date(2027, 6, 30), estado=Periodo.Estado.ABIERTO)
        self.assertEqual(Periodo.en_curso(), actual)
        self.assertEqual(periodo_abierto(), actual)
        r = self._cliente("marcela.rios@ejemplo.cl").get(reverse("gestion:actividad_nueva"))
        self.assertContains(r, actual.nombre)
        self.assertEqual(Periodo.en_curso(al_dia=date(2027, 5, 1)), futuro)
