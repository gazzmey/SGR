"""Códigos de recuperación de contraseña."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CodigoRecuperacion",
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
                ("codigo", models.CharField(max_length=6, verbose_name="código")),
                (
                    "creado",
                    models.DateTimeField(auto_now_add=True, verbose_name="creado el"),
                ),
                ("expira", models.DateTimeField(verbose_name="vence el")),
                ("usado", models.BooleanField(default=False)),
                ("intentos", models.PositiveSmallIntegerField(default=0)),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="codigos_recuperacion",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="usuario",
                    ),
                ),
            ],
            options={
                "verbose_name": "código de recuperación",
                "verbose_name_plural": "códigos de recuperación",
                "ordering": ["-creado"],
            },
        ),
    ]
