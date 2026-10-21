"""Entidades nuevas de la segunda entrega: solicitante y atención."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import atencion.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalogos", "0002_entrega2"),
        ("organizacion", "0002_entrega2"),
    ]

    operations = [
        migrations.CreateModel(
            name="Solicitante",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "rut",
                    models.CharField(
                        help_text="Con dígito verificador, por ejemplo 11111111-1.",
                        max_length=12,
                        unique=True,
                        validators=[atencion.models.validar_rut],
                        verbose_name="RUT",
                    ),
                ),
                ("nombre", models.CharField(max_length=120)),
                (
                    "telefono",
                    models.CharField(blank=True, max_length=20, verbose_name="teléfono"),
                ),
                (
                    "territorio",
                    models.CharField(
                        blank=True,
                        help_text="Unidad vecinal o sector al que pertenece.",
                        max_length=80,
                    ),
                ),
                (
                    "creada",
                    models.DateField(auto_now_add=True, verbose_name="registrado el"),
                ),
            ],
            options={
                "verbose_name": "solicitante",
                "verbose_name_plural": "solicitantes",
                "ordering": ["nombre"],
            },
        ),
        migrations.CreateModel(
            name="Atencion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "detalle",
                    models.TextField(
                        help_text="Qué pidió la persona y qué se le respondió."
                    ),
                ),
                (
                    "documento",
                    models.CharField(
                        blank=True,
                        help_text="Obligatorio cuando la subatención lo exige.",
                        max_length=120,
                        verbose_name="documento de respaldo",
                    ),
                ),
                (
                    "registrada",
                    models.DateTimeField(auto_now_add=True, verbose_name="registrada el"),
                ),
                (
                    "delegacion",
                    models.ForeignKey(
                        help_text="La delegación activa de quien registró la atención.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="atenciones",
                        to="organizacion.delegacion",
                        verbose_name="delegación",
                    ),
                ),
                (
                    "funcionario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="atenciones",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="funcionario",
                    ),
                ),
                (
                    "solicitante",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="atenciones",
                        to="atencion.solicitante",
                        verbose_name="solicitante",
                    ),
                ),
                (
                    "subatencion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="atenciones",
                        to="catalogos.subatencion",
                        verbose_name="subatención",
                    ),
                ),
            ],
            options={
                "verbose_name": "atención",
                "verbose_name_plural": "atenciones",
                "ordering": ["-registrada"],
            },
        ),
    ]
