"""
Gráficos del tablero (guía de la evaluación 3, grupo 3): carga de trabajo,
estado de los compromisos y tendencia semanal.

Cada cifra que dibuja el tablero se compara con un conteo hecho aparte,
directo sobre la base, para que el gráfico no pueda mostrar algo distinto de
lo registrado.
"""

from datetime import timedelta

from django.db.models import Count
from django.urls import reverse

from gestion import graficos as G
from gestion.modelos_actividad import Actividad
from gestion.modelos_agenda import Compromiso
from gestion.semanas import lunes_de
from organizacion.models import PerfilUsuario

from pruebas.test_evaluacion3 import Base


class Graficos(Base):
    def setUp(self):
        super().setUp()
        self.delegada = self._cliente("soledad.guerrero@ejemplo.cl")
        self.personas = list(PerfilUsuario.objects.filter(delegacion=self.del1))

    def test_el_tablero_muestra_los_tres_graficos(self):
        r = self.delegada.get(reverse("gestion:tablero"))
        self.assertEqual(r.status_code, 200)
        for titulo in ("Carga de trabajo", "Estado de los compromisos", "Tendencia semanal"):
            self.assertContains(r, titulo)
        self.assertContains(r, 'class="gr-tend"')
        # Cada barra se describe en texto para un lector de pantalla.
        self.assertContains(r, 'role="img" aria-label="Marcela Ríos:')

    def test_la_carga_coincide_con_lo_registrado(self):
        carga = G.carga_de_trabajo(self.del1, self.periodo, self.personas)
        self.assertTrue(carga["filas"])
        for fila in carga["filas"]:
            usuario = fila["perfil"].usuario_id
            base = Actividad.objects.filter(periodo=self.periodo, delegacion=self.del1,
                                            funcionario_id=usuario)
            tramos = {t["clave"]: t["n"] for t in fila["tramos"]}
            self.assertEqual(tramos["aprobadas"], base.filter(estado=Actividad.Estado.APROBADA).count())
            self.assertEqual(tramos["pendientes"], base.filter(estado=Actividad.Estado.PENDIENTE).count())
            self.assertEqual(fila["total"], base.exclude(estado=Actividad.Estado.ANULADA).count())
            self.assertAlmostEqual(sum(t["ancho"] for t in fila["tramos"]), 100, delta=0.1)
        # Ordenada de mayor a menor, y la barra más larga ocupa todo el ancho.
        totales = [f["total"] for f in carga["filas"]]
        self.assertEqual(totales, sorted(totales, reverse=True))
        self.assertEqual(carga["filas"][0]["ancho"], 100)
        # Quien no tiene actividades no aparece como barra vacía.
        self.assertTrue(all(f["total"] > 0 for f in carga["filas"]))

    def test_una_actividad_anulada_no_carga(self):
        act = Actividad.objects.filter(delegacion=self.del1, periodo=self.periodo,
                                       estado=Actividad.Estado.PENDIENTE).first()
        antes = G.carga_de_trabajo(self.del1, self.periodo, self.personas)
        total = next(f["total"] for f in antes["filas"] if f["perfil"].usuario_id == act.funcionario_id)
        Actividad.objects.filter(pk=act.pk).update(estado=Actividad.Estado.ANULADA)
        despues = G.carga_de_trabajo(self.del1, self.periodo, self.personas)
        nuevo = next((f["total"] for f in despues["filas"] if f["perfil"].usuario_id == act.funcionario_id), 0)
        self.assertEqual(nuevo, total - 1)

    def test_los_compromisos_por_estado(self):
        datos = G.estado_de_compromisos(self.del1, self.periodo, al_dia=self.hoy)
        consulta = Compromiso.que_cuentan(
            Compromiso.objects.filter(periodo=self.periodo, delegacion=self.del1))
        esperado = dict(consulta.values_list("estado").annotate(n=Count("pk")))
        self.assertEqual(datos["total"], consulta.count())
        for tramo in datos["tramos"]:
            estado = next(e for e in Compromiso.Estado if e.label == tramo["rotulo"])
            self.assertEqual(tramo["n"], esperado.get(estado, 0), tramo["rotulo"])
        self.assertEqual(datos["vencidos"], consulta.filter(
            estado__in=Compromiso.ABIERTOS, vencimiento__lt=self.hoy).count())

    def test_un_compromiso_vencido_se_cuenta_como_vencido(self):
        abierto = Compromiso.objects.filter(periodo=self.periodo, delegacion=self.del1,
                                            estado__in=Compromiso.ABIERTOS).first()
        antes = G.estado_de_compromisos(self.del1, self.periodo, al_dia=self.hoy)["vencidos"]
        Compromiso.objects.filter(pk=abierto.pk).update(vencimiento=self.hoy - timedelta(days=3))
        ya_vencido = abierto.vencimiento < self.hoy
        despues = G.estado_de_compromisos(self.del1, self.periodo, al_dia=self.hoy)["vencidos"]
        self.assertEqual(despues, antes if ya_vencido else antes + 1)

    def test_la_tendencia_cuenta_por_semana(self):
        datos = G.tendencia_semanal(self.del1, self.periodo, al_dia=self.hoy)
        semanas = datos["semanas"]
        self.assertTrue(semanas)
        self.assertEqual(semanas[0]["inicio"], lunes_de(self.periodo.inicio))
        for anterior, siguiente in zip(semanas, semanas[1:]):
            self.assertEqual(siguiente["inicio"] - anterior["inicio"], timedelta(days=7))
        fin = min(self.periodo.termino, self.hoy)
        base = (Actividad.objects.filter(periodo=self.periodo, delegacion=self.del1,
                                         fecha__gte=self.periodo.inicio, fecha__lte=fin)
                .exclude(estado=Actividad.Estado.ANULADA))
        self.assertEqual(sum(s["registradas"] for s in semanas), base.count())
        self.assertEqual(sum(s["aprobadas"] for s in semanas),
                         base.filter(estado=Actividad.Estado.APROBADA).count())
        for s in semanas:
            self.assertLessEqual(s["aprobadas"], s["registradas"])
            del_lunes = base.filter(fecha__gte=s["inicio"], fecha__lte=s["inicio"] + timedelta(days=6))
            self.assertEqual(s["registradas"], del_lunes.count())
        self.assertEqual(datos["maximo"], max(s["registradas"] for s in semanas))
        self.assertIn("aria-label", datos["svg"])

    def test_un_periodo_que_aun_no_empieza_no_dibuja_nada(self):
        datos = G.tendencia_semanal(self.del1, self.periodo, al_dia=self.periodo.inicio - timedelta(days=1))
        self.assertEqual(datos["semanas"], [])
        self.assertEqual(datos["maximo"], 0)
