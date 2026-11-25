"""
Retención de datos personales de los vecinos (caso SEG-06 del protocolo).

    python manage.py aplicar_retencion               # solo informa, no cambia nada
    python manage.py aplicar_retencion --aplicar     # anonimiza

Un vecino se anonimiza cuando su último movimiento en el sistema (registro,
atención, actividad en que fue el usuario atendido o inscripción de regalos)
es anterior al plazo de conservación, y además no integra una junta de
vecinos ni tiene un caso social en curso.

Anonimizar no borra el registro: las atenciones, actividades e inscripciones
siguen existiendo y suman igual en los informes de su época, pero ya no dicen
de quién eran. Se reemplazan el RUT, el nombre, el teléfono, el correo y la
dirección; se quita el RUT del niño o niña de sus inscripciones de regalos, y
en la auditoría del vecino se borran las copias de esos datos. Queda un
evento de auditoría con cuántos vecinos se anonimizaron y con qué plazo, sin
datos personales.

El plazo por omisión (60 meses) es una **propuesta del equipo**: lo fija el
municipio según su política de retención. Se cambia con --meses o con la
variable SGR_RETENCION_MESES del .env. Las evidencias (fotos, actas) no se
tocan: respaldan puntajes de trimestres cerrados y su conservación se define
aparte.

Limitación conocida: el texto libre que alguien haya escrito en el detalle de
una atención o en una observación puede nombrar al vecino, y ese texto no se
revisa.
"""

import os
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

ANONIMO = "Vecino anonimizado"
ENTIDADES_VECINO = ("Vecino", "vecino", "Solicitante", "solicitante")


def restar_meses(dia, meses):
    total = dia.year * 12 + (dia.month - 1) - meses
    anio, mes = divmod(total, 12)
    mes += 1
    # El día 31 no existe en todos los meses: se usa el último del mes.
    for d in (dia.day, 30, 29, 28):
        try:
            return date(anio, mes, d)
        except ValueError:
            continue


def candidatos(corte):
    """Los vecinos cuyo último movimiento es anterior a ``corte``, con su fecha."""
    from atencion.models import Atencion, CasoSocial, Solicitante

    con_caso_abierto = set(Atencion.objects.filter(caso__estado=CasoSocial.Estado.EN_CURSO)
                           .values_list("solicitante_id", flat=True))
    qs = (Solicitante.objects.exclude(rut__startswith="ANON-")
          .exclude(participaciones__activo=True)
          .annotate(ult_atencion=Max("atenciones__registrada"),
                    ult_actividad=Max("actividades__fecha"),
                    ult_regalo=Max("regalos_inscritos__registrada"))
          .distinct())
    salida = []
    for v in qs:
        if v.pk in con_caso_abierto:
            continue
        fechas = [v.creada]
        for f in (v.ult_atencion, v.ult_regalo):
            if f is not None:
                fechas.append(timezone.localtime(f).date() if timezone.is_aware(f) else f.date())
        if v.ult_actividad is not None:
            fechas.append(v.ult_actividad)
        ultimo = max(fechas)
        if ultimo < corte:
            salida.append((v, ultimo))
    return salida


class Command(BaseCommand):
    help = "Anonimiza los vecinos sin movimiento dentro del plazo de conservación (por omisión solo informa)."

    def add_arguments(self, parser):
        parser.add_argument("--meses", type=int, default=int(os.environ.get("SGR_RETENCION_MESES", "60")),
                            help="plazo de conservación en meses (por omisión SGR_RETENCION_MESES o 60)")
        parser.add_argument("--aplicar", action="store_true", help="anonimiza; sin esto solo informa")
        # Solo para las pruebas automáticas: simula otra fecha de hoy.
        parser.add_argument("--al-dia", default="", help="(pruebas) fecha de hoy, AAAA-MM-DD")

    def handle(self, *args, **o):
        from atencion.modelos_regalos import InscripcionRegalo
        from atencion.models import Solicitante
        from comun.models import EventoAuditoria

        if o["meses"] < 12:
            raise CommandError("El plazo no puede ser menor a 12 meses: revisa --meses o SGR_RETENCION_MESES.")
        hoy = date.fromisoformat(o["al_dia"]) if o["al_dia"] else timezone.localdate()
        corte = restar_meses(hoy, o["meses"])
        lista = candidatos(corte)

        self.stdout.write(f"Plazo de conservación: {o['meses']} meses. Se anonimizan los vecinos sin movimiento desde antes del {corte:%d-%m-%Y}.")
        self.stdout.write(f"Vecinos que cumplen el plazo: {len(lista)}.")
        for v, ultimo in lista[:20]:
            # Solo el número interno y la fecha: el informe no repite datos personales.
            self.stdout.write(f"  vecino n.º {v.pk}: último movimiento el {ultimo:%d-%m-%Y}")
        if len(lista) > 20:
            self.stdout.write(f"  … y {len(lista) - 20} más.")

        if not o["aplicar"]:
            self.stdout.write("No se cambió nada. Para anonimizar, repite el comando con --aplicar.")
            return

        borrado = "[datos personales eliminados por retención]"
        with transaction.atomic():
            for v, _ in lista:
                Solicitante.objects.filter(pk=v.pk).update(
                    rut=f"ANON-{v.pk}", nombres=ANONIMO, apellidos="", telefono="", correo="",
                    direccion="", sector="", activo=False, desactivada=v.desactivada or hoy)
                for ins in InscripcionRegalo.objects.filter(apoderado_id=v.pk).only("pk"):
                    InscripcionRegalo.objects.filter(pk=ins.pk).update(rut_menor=f"ANON-{ins.pk}")
                eventos = EventoAuditoria.objects.filter(entidad__in=ENTIDADES_VECINO, objeto_id=v.pk)
                eventos.update(objeto_texto=f"{ANONIMO} n.º {v.pk}")
                eventos.exclude(antes="").update(antes=borrado)
                eventos.exclude(despues="").update(despues=borrado)
            EventoAuditoria.objects.create(
                quien=None, quien_texto="Tarea de retención de datos",
                accion=EventoAuditoria.Accion.EDITAR, entidad="Retención de datos",
                objeto_texto=f"{len(lista)} vecinos anonimizados",
                detalle=f"Plazo de {o['meses']} meses; sin movimiento desde antes del {corte:%d-%m-%Y}.")
        self.stdout.write(self.style.SUCCESS(f"Listo: {len(lista)} vecinos anonimizados."))
