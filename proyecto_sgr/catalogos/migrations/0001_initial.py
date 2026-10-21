from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Item",
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
                    "codigo",
                    models.CharField(
                        help_text="Identificador corto e irrepetible, por ejemplo ITM-01.",
                        max_length=10,
                        unique=True,
                        verbose_name="código",
                    ),
                ),
                ("nombre", models.CharField(max_length=120)),
                (
                    "descripcion",
                    models.CharField(
                        blank=True, max_length=200, verbose_name="descripción"
                    ),
                ),
                ("activo", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "ítem",
                "verbose_name_plural": "ítems",
                "ordering": ["codigo"],
            },
        ),
        migrations.CreateModel(
            name="TipoAtencion",
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
                    "codigo",
                    models.CharField(
                        help_text="Identificador corto e irrepetible, por ejemplo TA-01.",
                        max_length=10,
                        unique=True,
                        verbose_name="código",
                    ),
                ),
                ("nombre", models.CharField(max_length=120)),
                ("activo", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "tipo de atención",
                "verbose_name_plural": "tipos de atención",
                "ordering": ["codigo"],
            },
        ),
        migrations.CreateModel(
            name="SubAtencion",
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
                    "codigo",
                    models.CharField(
                        help_text="Identificador corto e irrepetible, por ejemplo SA-01.",
                        max_length=10,
                        unique=True,
                        verbose_name="código",
                    ),
                ),
                ("nombre", models.CharField(max_length=120)),
                ("activo", models.BooleanField(default=True)),
                (
                    "tipo_atencion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="subatenciones",
                        to="catalogos.tipoatencion",
                        verbose_name="tipo de atención",
                    ),
                ),
            ],
            options={
                "verbose_name": "subatención",
                "verbose_name_plural": "subatenciones",
                "ordering": ["tipo_atencion__codigo", "codigo"],
            },
        ),
    ]
