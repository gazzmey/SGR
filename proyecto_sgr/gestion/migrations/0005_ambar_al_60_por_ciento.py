"""
Corrige la frontera del semáforo entre ámbar y rojo: 60 % y no 80 %.

Por qué
-------
El lote CAL-E del plan de pruebas da el resultado verificable textual: «Con
esperado 50 %: avance 29,99 % = rojo; 30 % = ámbar». Esa frontera de 30
sobre un esperado de 50 está en el **60 %** de lo esperado.

Con el umbral en 80 %, la frontera caía en 40 y el 30 % del lote daba rojo,
contradiciendo el resultado que el plan declara verificable. La suite de
pruebas no lo detectaba porque estaba escrita con los valores 39,99 y 40 —los
que produce la implementación— en vez de los 29,99 y 30 del plan. Ambos
quedaron corregidos junto con esta migración.

Qué toca de los datos existentes
--------------------------------
Solo las filas que siguen siendo el valor por omisión antiguo: umbral en 80 y
**sin aprobar**. Una regla aprobada formalmente no se toca aunque tenga 80,
porque entonces el 80 es una decisión de alguien y no un resto del valor por
omisión. Y el cambio queda registrado en su observación, para que nadie
encuentre mañana un número distinto al que configuró sin saber por qué.
"""

from django.db import migrations, models

ANTES, DESPUES = 80, 60

NOTA = (
    "\n\n[Migración 0005] El umbral del ámbar se corrigió de 80 % a 60 %. "
    "El lote CAL-E del plan exige que, con un avance esperado de 50 %, el "
    "29,99 % sea rojo y el 30 % sea ámbar; esa frontera está en el 60 % de "
    "lo esperado. Con 80 % el ámbar partía en 40 % y el lote no cuadraba."
)


def corregir(apps, schema_editor):
    Regla = apps.get_model("gestion", "ReglaCalculo")
    for regla in Regla.objects.filter(umbral_ambar=ANTES, aprobada=False):
        regla.umbral_ambar = DESPUES
        regla.observacion = (regla.observacion or "") + NOTA
        regla.save(update_fields=["umbral_ambar", "observacion"])


def deshacer(apps, schema_editor):
    """
    No se revierte el dato.

    Volver a poner 80 en todas las filas devolvería el valor antiguo también
    a quien lo haya configurado a mano después, y no hay forma de distinguir
    unas de otras. La nota en la observación queda como rastro.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("gestion", "0004_actividad_cantidad"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reglacalculo",
            name="umbral_ambar",
            field=models.PositiveSmallIntegerField(
                default=60,
                help_text=(
                    "Porcentaje del avance esperado por debajo del cual el "
                    "semáforo pasa de ámbar a rojo. Con 60 y un esperado de "
                    "50 %, el ámbar llega hasta el 30 % y bajo eso es rojo."
                ),
                verbose_name="umbral del ámbar",
            ),
        ),
        migrations.RunPython(corregir, deshacer),
    ]
