"""
Evaluación 3: territorio como entidad, delegado de la delegación, RUT del
funcionario y grupo de Django del rol.

Todo lo que se agrega admite vacío en la base: los registros que ya
existen siguen siendo válidos y se completan desde las pantallas.
"""

import django.core.validators  # noqa: F401
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import comun.rut


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("organizacion", "0004_validan_verificador_y_administrador"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="delegacion",
            name="delegado",
            field=models.ForeignKey(
                blank=True, null=True,
                help_text=("Quien encabeza la delegación. Tiene que ser un usuario activo "
                           "que trabaje en ella o tenga alcance sobre ella."),
                on_delete=django.db.models.deletion.PROTECT,
                related_name="delegaciones_a_cargo",
                to=settings.AUTH_USER_MODEL, verbose_name="delegado",
            ),
        ),
        migrations.CreateModel(
            name="Territorio",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(
                    help_text="Identificador corto e irrepetible, por ejemplo TER-01.",
                    max_length=10, unique=True, verbose_name="código")),
                ("nombre", models.CharField(max_length=120)),
                ("descripcion", models.TextField(
                    blank=True, help_text="Qué calles, poblaciones o sectores comprende.",
                    verbose_name="descripción")),
                ("activo", models.BooleanField(default=True)),
                ("creada", models.DateField(auto_now_add=True, verbose_name="creado el")),
                ("desactivada", models.DateField(blank=True, null=True,
                                                 verbose_name="desactivado el")),
                ("delegacion", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="territorios", to="organizacion.delegacion",
                    verbose_name="delegación")),
            ],
            options={
                "verbose_name": "territorio",
                "verbose_name_plural": "territorios",
                "ordering": ["codigo"],
            },
        ),
        migrations.AddConstraint(
            model_name="territorio",
            constraint=models.UniqueConstraint(
                fields=("delegacion", "nombre"),
                name="un_nombre_de_territorio_por_delegacion",
            ),
        ),
        migrations.AddField(
            model_name="rol",
            name="grupo",
            field=models.ForeignKey(
                blank=True, null=True,
                help_text=("Los permisos de Django (ver, crear, editar, desactivar) que el "
                           "rol entrega sobre las 17 entidades. Lo configura el "
                           "administrador; no se edita desde el formulario general."),
                on_delete=django.db.models.deletion.PROTECT,
                related_name="roles_sgr", to="auth.group",
                verbose_name="grupo de Django",
            ),
        ),
        migrations.AddField(
            model_name="perfilusuario",
            name="rut",
            field=models.CharField(
                blank=True, null=True, max_length=12, unique=True,
                validators=[comun.rut.validar_rut], verbose_name="RUT",
                help_text="Ficticio, con dígito verificador. Por ejemplo 11111111-1.",
            ),
        ),
    ]
