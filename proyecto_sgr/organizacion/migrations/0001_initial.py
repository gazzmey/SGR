from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Delegacion",
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
                        help_text="Identificador corto e irrepetible, por ejemplo DEL-01.",
                        max_length=10,
                        unique=True,
                        verbose_name="código",
                    ),
                ),
                ("nombre", models.CharField(max_length=120)),
                (
                    "activo",
                    models.BooleanField(
                        default=True,
                        help_text="Las delegaciones inactivas dejan de ofrecerse en los formularios.",
                        verbose_name="activa",
                    ),
                ),
            ],
            options={
                "verbose_name": "delegación",
                "verbose_name_plural": "delegaciones",
                "ordering": ["nombre"],
            },
        ),
        migrations.CreateModel(
            name="Rol",
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
                ("nombre", models.CharField(max_length=60, unique=True)),
                (
                    "descripcion",
                    models.CharField(
                        blank=True, max_length=200, verbose_name="descripción"
                    ),
                ),
                ("activo", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "rol",
                "verbose_name_plural": "roles",
                "ordering": ["nombre"],
            },
        ),
        migrations.CreateModel(
            name="PerfilUsuario",
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
                ("activo", models.BooleanField(default=True)),
                (
                    "delegacion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="perfiles",
                        to="organizacion.delegacion",
                        verbose_name="delegación",
                    ),
                ),
                (
                    "rol",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="perfiles",
                        to="organizacion.rol",
                        verbose_name="rol",
                    ),
                ),
                (
                    "usuario",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="perfil",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="usuario",
                    ),
                ),
            ],
            options={
                "verbose_name": "perfil de usuario",
                "verbose_name_plural": "perfiles de usuario",
                "ordering": ["usuario__username"],
            },
        ),
    ]
