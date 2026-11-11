"""
Deja con regla propia a los períodos que ya estaban cerrados.

Desde la HU-25, cerrar un período copia la regla con que se medía como regla
propia del período, para que editar la regla general no altere su resultado.
Los períodos cerrados antes de este cambio no pasaron por ese paso: esta
migración se lo aplica, copiando la regla general activa —la que los estaba
midiendo— o, si no hay ninguna, los valores que propone el plan.
"""

from datetime import date

from django.db import migrations


def congelar(apps, schema_editor):
    Periodo = apps.get_model("gestion", "Periodo")
    ReglaCalculo = apps.get_model("gestion", "ReglaCalculo")

    general = ReglaCalculo.objects.filter(periodo__isnull=True, activo=True).first()
    excluir = {"id", "nombre", "periodo", "creada", "desactivada", "activo", "observacion"}

    for periodo in Periodo.objects.filter(estado="cerrado"):
        if ReglaCalculo.objects.filter(periodo=periodo, activo=True).exists():
            continue
        copia = ReglaCalculo(periodo=periodo, activo=True)
        if general is not None:
            for campo in ReglaCalculo._meta.concrete_fields:
                if campo.name not in excluir:
                    setattr(copia, campo.attname, getattr(general, campo.attname))
            base = f"{general.nombre} · {periodo.codigo}"[:80]
            de_donde = f"de la regla «{general.nombre}»"
        else:
            base = f"Propuesta del plan · {periodo.codigo}"[:80]
            de_donde = "con los valores que propone el plan"
        nombre, n = base, 2
        while ReglaCalculo.objects.filter(nombre=nombre).exists():
            sufijo = f" ({n})"
            nombre = base[:80 - len(sufijo)] + sufijo
            n += 1
        copia.nombre = nombre
        copia.observacion = (
            f"Copia congelada el {date.today():%d-%m-%Y} {de_donde}, para que "
            f"el resultado de «{periodo.nombre}», ya cerrado, no cambie si se "
            "edita la regla general."
        )
        copia.save()


class Migration(migrations.Migration):

    dependencies = [
        ("gestion", "0013_versiones_de_parametros"),
    ]

    operations = [
        migrations.RunPython(congelar, migrations.RunPython.noop),
    ]
