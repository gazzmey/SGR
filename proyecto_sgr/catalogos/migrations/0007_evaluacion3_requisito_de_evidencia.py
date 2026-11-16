"""
Evaluación 3: el ítem es la entidad Meta y declara su requisito de evidencia.

Los ítems que ya existen quedan con «requiere evidencia» y un texto por
omisión, para que sigan pasando la validación al editarlos.
"""

from django.db import migrations, models

POR_OMISION = "Acta, fotografía o lista de asistencia que respalde la actividad"


def completar(apps, schema_editor):
    Item = apps.get_model("catalogos", "Item")
    Item.objects.filter(evidencia_requerida="").update(evidencia_requerida=POR_OMISION)


class Migration(migrations.Migration):

    dependencies = [
        ("catalogos", "0006_medicion_del_item"),
    ]

    operations = [
        migrations.AddField(
            model_name="item", name="requiere_evidencia",
            field=models.BooleanField(
                default=True, verbose_name="requiere evidencia",
                help_text="Si las actividades de esta meta necesitan una evidencia aprobada para sumar."),
        ),
        migrations.AddField(
            model_name="item", name="evidencia_requerida",
            field=models.CharField(
                blank=True, max_length=160, verbose_name="evidencia que se exige",
                default=POR_OMISION,
                help_text="Qué documento respalda el registro. Por ejemplo: acta firmada y fotografía."),
        ),
        migrations.AlterModelOptions(
            name="item",
            options={"ordering": ["codigo"], "verbose_name": "meta", "verbose_name_plural": "metas"},
        ),
        migrations.AlterModelOptions(
            name="subatencion",
            options={"ordering": ["tipo_atencion__codigo", "codigo"],
                     "verbose_name": "subtipo de atención",
                     "verbose_name_plural": "subtipos de atención"},
        ),
        migrations.RunPython(completar, migrations.RunPython.noop),
    ]
