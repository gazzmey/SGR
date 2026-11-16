"""
Completa los datos nuevos de la Evaluación 3 en lo que ya estaba registrado.

* Año y número de cada trimestre, desde su fecha de inicio.
* La asignación de meta de cada actividad: la del cargo de quien la
  registró, en ese período y ese ítem. Si no hay, queda vacía, que es lo
  que corresponde a una actividad registrada sin meta configurada.
* El responsable de cada actividad: quien la registró.

No cambia ningún resultado: el cálculo sigue mirando período, ítem y cargo,
y la asignación que se completa es justamente la que ya usaba.
"""

from django.db import migrations
from django.db.models import F


def completar(apps, schema_editor):
    Periodo = apps.get_model("gestion", "Periodo")
    MetaPeriodo = apps.get_model("gestion", "MetaPeriodo")
    Actividad = apps.get_model("gestion", "Actividad")

    for periodo in Periodo.objects.all():
        periodo.anio = periodo.inicio.year
        periodo.numero = (periodo.inicio.month - 1) // 3 + 1
        periodo.save(update_fields=["anio", "numero"])

    for meta in MetaPeriodo.objects.filter(funcionario__isnull=True):
        (Actividad.objects
         .filter(periodo_id=meta.periodo_id, item_id=meta.item_id,
                 funcionario__perfil__cargo_asignado_id=meta.cargo_id,
                 asignacion__isnull=True)
         .update(asignacion=meta))

    Actividad.objects.filter(responsable__isnull=True).update(responsable=F("funcionario"))


class Migration(migrations.Migration):

    dependencies = [
        ("gestion", "0016_evaluacion3_hitos_y_asignaciones"),
    ]

    operations = [
        migrations.RunPython(completar, migrations.RunPython.noop),
    ]
