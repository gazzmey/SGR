"""
Campos que la segunda entrega del Proyecto Integrado agrega a la Unidad 2.

Nada se elimina ni se renombra: la entrega de Back End sigue siendo válida
sobre esta misma base. En particular ``PerfilUsuario.delegacion`` se conserva
y ``delegaciones_autorizadas`` se suma.

Dos cuidados que esta migración tiene, y conviene saber explicar:

1. ``creada`` usa ``auto_now_add``, así que las filas que ya existan
   necesitan un valor de una sola vez. Se usa la fecha de la migración, y
   ``preserve_default=False`` hace que ese valor no quede en el modelo.

2. ``codigo`` se agrega con un valor por defecto igual para todos y recién
   después se vuelve único. Entre medio va un paso de datos que le da a cada
   fila su correlativo: sin él, la base rechazaría la restricción por
   duplicados en cuanto hubiera más de un registro.
"""

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


def numerar(apps, schema_editor, modelo, prefijo):
    """Le da a cada fila existente su código correlativo, por orden de alta."""
    Modelo = apps.get_model("organizacion", modelo)
    for numero, fila in enumerate(Modelo.objects.order_by("pk"), start=1):
        fila.codigo = f"{prefijo}-{numero:02d}"
        fila.save(update_fields=["codigo"])


def numerar_roles(apps, schema_editor):
    numerar(apps, schema_editor, "Rol", "ROL")


def numerar_perfiles(apps, schema_editor):
    numerar(apps, schema_editor, "PerfilUsuario", "USR")


class Migration(migrations.Migration):

    dependencies = [
        ("organizacion", "0001_initial"),
    ]

    operations = [
        # --- Delegación: dónde atiende y cómo contactarla -----------------
        migrations.AddField(
            model_name="delegacion",
            name="zona",
            field=models.CharField(
                choices=[("Urbana", "Urbana"), ("Rural", "Rural"), ("Costera", "Costera")],
                default="Urbana",
                help_text="Determina en qué informes territoriales se agrupa.",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="delegacion",
            name="direccion",
            field=models.CharField(blank=True, max_length=160, verbose_name="dirección"),
        ),
        migrations.AddField(
            model_name="delegacion",
            name="comuna",
            field=models.CharField(default="La Serena", max_length=80),
        ),
        migrations.AddField(
            model_name="delegacion",
            name="telefono",
            field=models.CharField(blank=True, max_length=20, verbose_name="teléfono"),
        ),
        migrations.AddField(
            model_name="delegacion",
            name="horario",
            field=models.CharField(
                blank=True,
                help_text="Por ejemplo: Lun a vie · 08:30 a 14:00.",
                max_length=120,
                verbose_name="horario de atención",
            ),
        ),
        migrations.AddField(
            model_name="delegacion",
            name="creada",
            field=models.DateField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="creada el",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="delegacion",
            name="desactivada",
            field=models.DateField(blank=True, null=True, verbose_name="desactivada el"),
        ),
        migrations.AlterField(
            model_name="delegacion",
            name="nombre",
            field=models.CharField(max_length=120, unique=True),
        ),
        migrations.AlterModelOptions(
            name="delegacion",
            options={
                "ordering": ["codigo"],
                "verbose_name": "delegación",
                "verbose_name_plural": "delegaciones",
            },
        ),

        # --- Rol: alcance y permisos --------------------------------------
        migrations.AddField(
            model_name="rol",
            name="codigo",
            field=models.CharField(
                default="ROL-00",
                help_text="Identificador corto e irrepetible, por ejemplo ROL-01.",
                max_length=10,
                verbose_name="código",
            ),
        ),
        migrations.AddField(
            model_name="rol",
            name="alcance",
            field=models.CharField(
                choices=[
                    ("propia", "Su delegación"),
                    ("varias", "Varias delegaciones"),
                    ("todas", "Todas las delegaciones"),
                ],
                default="propia",
                help_text="Sobre qué delegaciones puede actuar quien tiene el rol.",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="rol",
            name="permisos",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Lista de claves de permiso. Ver comun/permisos.py.",
            ),
        ),
        migrations.AddField(
            model_name="rol",
            name="creada",
            field=models.DateField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="creado el",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="rol",
            name="desactivada",
            field=models.DateField(blank=True, null=True, verbose_name="desactivado el"),
        ),
        migrations.RunPython(numerar_roles, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="rol",
            name="codigo",
            field=models.CharField(
                default="ROL-00",
                help_text="Identificador corto e irrepetible, por ejemplo ROL-01.",
                max_length=10,
                unique=True,
                verbose_name="código",
            ),
        ),
        migrations.AlterModelOptions(
            name="rol",
            options={
                "ordering": ["codigo"],
                "verbose_name": "rol",
                "verbose_name_plural": "roles",
            },
        ),

        # --- Perfil: cargo y delegaciones autorizadas ---------------------
        migrations.AddField(
            model_name="perfilusuario",
            name="codigo",
            field=models.CharField(
                default="USR-00",
                help_text="Identificador corto e irrepetible, por ejemplo USR-01.",
                max_length=10,
                verbose_name="código",
            ),
        ),
        migrations.AddField(
            model_name="perfilusuario",
            name="cargo",
            field=models.CharField(
                blank=True,
                help_text="Informativo. Lo que habilita pantallas es el rol.",
                max_length=80,
            ),
        ),
        migrations.AddField(
            model_name="perfilusuario",
            name="delegaciones_autorizadas",
            field=models.ManyToManyField(
                blank=True,
                help_text="Si hay más de una, la cabecera ofrece el selector para cambiar.",
                related_name="perfiles_autorizados",
                to="organizacion.delegacion",
                verbose_name="delegaciones autorizadas",
            ),
        ),
        migrations.AddField(
            model_name="perfilusuario",
            name="creada",
            field=models.DateField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name="creado el",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="perfilusuario",
            name="desactivada",
            field=models.DateField(blank=True, null=True, verbose_name="desactivado el"),
        ),
        migrations.RunPython(numerar_perfiles, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="perfilusuario",
            name="codigo",
            field=models.CharField(
                default="USR-00",
                help_text="Identificador corto e irrepetible, por ejemplo USR-01.",
                max_length=10,
                unique=True,
                verbose_name="código",
            ),
        ),
        migrations.AlterField(
            model_name="perfilusuario",
            name="delegacion",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="perfiles",
                to="organizacion.delegacion",
                verbose_name="delegación base",
            ),
        ),
        migrations.AlterModelOptions(
            name="perfilusuario",
            options={
                "ordering": ["codigo"],
                "verbose_name": "perfil de usuario",
                "verbose_name_plural": "perfiles de usuario",
            },
        ),
    ]
