"""
La meta de un ítem tiene que ser mayor que cero (RN-002).

Con meta cero el cumplimiento sería una división por cero: cualquier avance
daría 100 % o infinito según cómo se calcule, y el resultado del período
dejaría de significar algo. La regla se pone en el modelo, con un validador,
para que valga también desde el administrador de Django y desde cualquier
script, no solo desde el formulario.

El paso de datos corrige las filas que ya existan con meta cero antes de
aplicar el validador. Hoy no debería haber ninguna —los datos de demostración
traen metas reales—, pero una base que venga de la entrega anterior sí puede
tenerlas, y entonces el ítem quedaría guardado con un valor que su propio
modelo considera inválido.

``MinValueValidator`` no crea una restricción en la base de datos: Django lo
aplica al validar. Por eso el paso de datos es necesario y no basta con la
definición del campo.
"""

import django.core.validators
from django.db import migrations, models


def subir_metas_en_cero(apps, schema_editor):
    """Las metas en cero pasan a 1, el mínimo que la regla permite."""
    Item = apps.get_model("catalogos", "Item")
    Item.objects.filter(meta=0).update(meta=1)


def volver_atras(apps, schema_editor):
    """
    Al revertir no se tocan los datos.

    Devolver las metas a cero sería inventar información: no sabemos cuáles
    estaban en cero antes de la migración, y dejarlas en 1 no rompe nada.
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalogos", "0003_codigos_de_ejemplo"),
    ]

    operations = [
        migrations.RunPython(subir_metas_en_cero, volver_atras),
        migrations.AlterField(
            model_name="item",
            name="meta",
            field=models.PositiveIntegerField(
                default=1,
                help_text=(
                    "En la unidad de medida elegida. Tiene que ser mayor que "
                    "cero: con meta cero el cumplimiento sería una división "
                    "por cero, y cualquier avance daría 100 % o infinito "
                    "según cómo se calcule."
                ),
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name="meta del período",
            ),
        ),
    ]
