"""
Evaluación 3: el solicitante pasa a ser el vecino, con su CRUD propio.

* ``nombre`` se renombra a ``nombres`` y se agrega ``apellidos``. La
  migración siguiente reparte el nombre que ya estaba entre los dos campos.
* El ``territorio`` de texto se renombra a ``sector`` y se conserva como
  referencia; el nuevo ``territorio`` apunta al catálogo.
* Se agregan correo, dirección y estado.
* Nacen las juntas de vecinos y la participación de cada vecino en ellas.
* La gestión social (``CasoSocial``) suma fecha de atención, actuaciones,
  derivación, resultado, estado y motivo de anulación.

Los renombres son ``RenameField``: conservan los datos. Un ``RemoveField``
seguido de ``AddField`` los habría borrado.
"""

import django.db.models.deletion
from django.db import migrations, models

import comun.rut


class Migration(migrations.Migration):

    dependencies = [
        ("atencion", "0003_regalos_para_ninos"),
        ("organizacion", "0005_evaluacion3_territorios"),
    ]

    operations = [
        # --- vecino --------------------------------------------------------
        migrations.RenameField(model_name="solicitante", old_name="nombre", new_name="nombres"),
        migrations.RenameField(model_name="solicitante", old_name="territorio", new_name="sector"),
        migrations.AlterField(
            model_name="solicitante",
            name="sector",
            field=models.CharField(
                blank=True, max_length=80, verbose_name="sector registrado antes",
                help_text=("El texto libre de la segunda entrega, antes del catálogo de "
                           "territorios. Se conserva como referencia histórica."),
            ),
        ),
        migrations.AddField(
            model_name="solicitante", name="apellidos",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="solicitante", name="correo",
            field=models.EmailField(blank=True, max_length=150, verbose_name="correo"),
        ),
        migrations.AddField(
            model_name="solicitante", name="direccion",
            field=models.CharField(blank=True, max_length=160, verbose_name="dirección"),
        ),
        migrations.AddField(
            model_name="solicitante", name="territorio",
            field=models.ForeignKey(
                blank=True, null=True,
                help_text="La unidad vecinal donde vive. Define a qué junta puede integrarse.",
                on_delete=django.db.models.deletion.PROTECT, related_name="vecinos",
                to="organizacion.territorio", verbose_name="territorio",
            ),
        ),
        migrations.AddField(
            model_name="solicitante", name="activo",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="solicitante", name="desactivada",
            field=models.DateField(blank=True, null=True, verbose_name="desactivado el"),
        ),
        migrations.AlterField(
            model_name="solicitante", name="rut",
            field=models.CharField(
                help_text="Ficticio, con dígito verificador. Por ejemplo 11111111-1.",
                max_length=12, unique=True, verbose_name="RUT",
                validators=[comun.rut.validar_rut],
            ),
        ),
        migrations.AlterModelOptions(
            name="solicitante",
            options={"ordering": ["apellidos", "nombres"],
                     "verbose_name": "vecino", "verbose_name_plural": "vecinos"},
        ),

        # --- juntas de vecinos --------------------------------------------
        migrations.CreateModel(
            name="JuntaVecinos",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(
                    help_text="Identificador corto e irrepetible, por ejemplo JV-01.",
                    max_length=10, unique=True, verbose_name="código")),
                ("nombre", models.CharField(max_length=120, unique=True)),
                ("direccion", models.CharField(
                    help_text="Dónde funciona la sede o dónde se reúne.",
                    max_length=160, verbose_name="dirección")),
                ("fecha_constitucion", models.DateField(
                    help_text="Cuándo se constituyó legalmente. No puede ser futura.",
                    verbose_name="fecha de constitución")),
                ("activo", models.BooleanField(default=True, verbose_name="activa")),
                ("creada", models.DateField(auto_now_add=True, verbose_name="creada el")),
                ("desactivada", models.DateField(blank=True, null=True,
                                                 verbose_name="desactivada el")),
                ("delegacion", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="juntas",
                    to="organizacion.delegacion", verbose_name="delegación")),
                ("territorio", models.ForeignKey(
                    help_text="Tiene que ser un territorio de la delegación elegida.",
                    on_delete=django.db.models.deletion.PROTECT, related_name="juntas",
                    to="organizacion.territorio", verbose_name="territorio")),
            ],
            options={"verbose_name": "junta de vecinos",
                     "verbose_name_plural": "juntas de vecinos", "ordering": ["codigo"]},
        ),
        migrations.CreateModel(
            name="ParticipacionJunta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(
                    help_text="Identificador corto e irrepetible, por ejemplo PJ-01.",
                    max_length=10, unique=True, verbose_name="código")),
                ("dirigente", models.BooleanField(
                    default=False, verbose_name="es dirigente",
                    help_text="Marca si integra la directiva. Un socio sin cargo no es dirigente.")),
                ("cargo", models.CharField(
                    choices=[("socio", "Socio o socia"), ("presidente", "Presidencia"),
                             ("vicepresidente", "Vicepresidencia"), ("secretario", "Secretaría"),
                             ("tesorero", "Tesorería"), ("director", "Director o directora")],
                    default="socio", max_length=16,
                    help_text="Los dirigentes tienen un cargo de la directiva; el resto, «Socio o socia».")),
                ("fecha_incorporacion", models.DateField(
                    help_text="No puede ser anterior a la constitución de la junta ni futura.",
                    verbose_name="fecha de incorporación")),
                ("activo", models.BooleanField(default=True, verbose_name="vigente")),
                ("creada", models.DateField(auto_now_add=True, verbose_name="registrada el")),
                ("desactivada", models.DateField(blank=True, null=True,
                                                 verbose_name="terminada el")),
                ("junta", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="participaciones",
                    to="atencion.juntavecinos", verbose_name="junta de vecinos")),
                ("vecino", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="participaciones",
                    to="atencion.solicitante", verbose_name="vecino")),
            ],
            options={"verbose_name": "participación en junta",
                     "verbose_name_plural": "participaciones en juntas",
                     "ordering": ["junta", "-dirigente", "vecino"]},
        ),

        # --- gestión social ------------------------------------------------
        migrations.AddField(
            model_name="casosocial", name="fecha_atencion",
            field=models.DateField(
                blank=True, null=True, verbose_name="fecha de atención",
                help_text="Cuándo se atendió a la persona. No puede ser posterior al ingreso del caso."),
        ),
        migrations.AddField(
            model_name="casosocial", name="actuaciones",
            field=models.TextField(
                blank=True,
                help_text="Lo que se hizo en el caso: llamados, coordinaciones, trámites."),
        ),
        migrations.AddField(
            model_name="casosocial", name="derivacion",
            field=models.CharField(
                blank=True, max_length=160, verbose_name="derivación",
                help_text="A qué institución o programa se derivó, si corresponde."),
        ),
        migrations.AddField(
            model_name="casosocial", name="resultado",
            field=models.TextField(blank=True, help_text="Cómo terminó el caso para la persona."),
        ),
        migrations.AddField(
            model_name="casosocial", name="estado",
            field=models.CharField(
                choices=[("en_curso", "En curso"), ("cerrado", "Cerrado"), ("anulado", "Anulado")],
                default="en_curso", max_length=10,
                help_text=("Se calcula solo: cerrado cuando se entrega lo último que falta. "
                           "Anulado no se revierte.")),
        ),
        migrations.AddField(
            model_name="casosocial", name="motivo_anulacion",
            field=models.TextField(blank=True, verbose_name="motivo de la anulación"),
        ),
        migrations.AlterModelOptions(
            name="casosocial",
            options={"ordering": ["-ingreso", "-codigo"], "verbose_name": "gestión social",
                     "verbose_name_plural": "gestiones sociales"},
        ),
    ]
