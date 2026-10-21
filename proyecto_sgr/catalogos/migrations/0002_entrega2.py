"""
Campos que la segunda entrega agrega a los catálogos de la Unidad 2.

``descripcion`` pasa de CharField a TextField en ítems y subatenciones
porque el texto que se pide ahí —qué cuenta como registro válido, qué
incluye la subatención— no cabe en 200 caracteres. Ampliar el tipo no pierde
datos: lo que había sigue estando.
"""

import django.utils.timezone
from django.db import migrations, models

AREAS = [
    ("Territorial", "Territorial"),
    ("Inspección", "Inspección"),
    ("Social", "Social"),
    ("Transversal", "Transversal"),
]


class Migration(migrations.Migration):

    dependencies = [
        ("catalogos", "0001_initial"),
    ]

    operations = [
        # --- Ítem: área, unidad, meta y ponderador ------------------------
        migrations.AlterField(
            model_name="item",
            name="nombre",
            field=models.CharField(max_length=120, unique=True),
        ),
        migrations.AlterField(
            model_name="item",
            name="descripcion",
            field=models.TextField(
                blank=True,
                help_text=(
                    "Qué cuenta como registro válido. Es lo que evita discusiones "
                    "al cerrar el período."
                ),
                verbose_name="descripción",
            ),
        ),
        migrations.AddField(
            model_name="item",
            name="area",
            field=models.CharField(
                choices=AREAS, default="Transversal", max_length=12, verbose_name="área"
            ),
        ),
        migrations.AddField(
            model_name="item",
            name="unidad",
            field=models.CharField(
                choices=[
                    ("Cantidad", "Cantidad"),
                    ("Porcentaje", "Porcentaje"),
                    ("Horas", "Horas"),
                ],
                default="Cantidad",
                max_length=12,
                verbose_name="unidad de medida",
            ),
        ),
        migrations.AddField(
            model_name="item",
            name="meta",
            field=models.PositiveIntegerField(
                default=0,
                help_text="En la unidad de medida elegida.",
                verbose_name="meta del período",
            ),
        ),
        migrations.AddField(
            model_name="item",
            name="ponderador",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text=(
                    "Porcentaje del resultado total. Entre todos los activos "
                    "deben sumar 100 %."
                ),
            ),
        ),
        migrations.AddField(
            model_name="item",
            name="creada",
            field=models.DateField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="creado el",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="item",
            name="desactivada",
            field=models.DateField(blank=True, null=True, verbose_name="desactivado el"),
        ),

        # --- Tipo de atención: área y descripción -------------------------
        migrations.AlterField(
            model_name="tipoatencion",
            name="nombre",
            field=models.CharField(max_length=120, unique=True),
        ),
        migrations.AddField(
            model_name="tipoatencion",
            name="descripcion",
            field=models.TextField(
                blank=True,
                help_text="Qué requerimientos entran en esta clasificación.",
                verbose_name="descripción",
            ),
        ),
        migrations.AddField(
            model_name="tipoatencion",
            name="area",
            field=models.CharField(
                choices=AREAS, default="Transversal", max_length=12, verbose_name="área"
            ),
        ),
        migrations.AddField(
            model_name="tipoatencion",
            name="creada",
            field=models.DateField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="creado el",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="tipoatencion",
            name="desactivada",
            field=models.DateField(blank=True, null=True, verbose_name="desactivado el"),
        ),

        # --- Subatención: descripción y documento de respaldo -------------
        migrations.AlterField(
            model_name="subatencion",
            name="nombre",
            field=models.CharField(max_length=120, unique=True),
        ),
        migrations.AddField(
            model_name="subatencion",
            name="descripcion",
            field=models.TextField(
                blank=True,
                help_text="Qué incluye, qué requisitos tiene y cómo se resuelve.",
                verbose_name="descripción",
            ),
        ),
        migrations.AddField(
            model_name="subatencion",
            name="documento",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Si está marcado, el ingreso de atención no deja guardar "
                    "sin adjuntarlo."
                ),
                verbose_name="exige documento de respaldo",
            ),
        ),
        migrations.AddField(
            model_name="subatencion",
            name="creada",
            field=models.DateField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="creada el",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="subatencion",
            name="desactivada",
            field=models.DateField(blank=True, null=True, verbose_name="desactivada el"),
        ),
    ]
