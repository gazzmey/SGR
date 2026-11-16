"""
Evaluación 3: trimestre, asignación por persona, hitos y los antecedentes
de la actividad y de la evidencia.

* El período es el **trimestre**: suma año y número (1 a 4). La migración
  siguiente los calcula desde la fecha de inicio de los que ya existen.
* La meta del período es la **asignación de meta**: suma funcionario y
  observación. La restricción de unicidad pasa a incluir al funcionario.
  Se agrega la nueva *antes* de quitar la anterior: en MySQL/MariaDB el
  índice de la restricción vieja es el que usa la clave foránea del
  período, y quitarlo primero falla («needed in a foreign key constraint»).
* Nacen los hitos.
* La actividad suma asignación, hito, tipo, origen, solicitante, territorio,
  responsable, fecha de compromiso, apoyo, avance y resultado.
* La evidencia puede respaldar una actividad **o** una gestión social, con
  una restricción que exige exactamente una de las dos.
"""

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestion", "0015_tope_acordado_120"),
        ("atencion", "0004_evaluacion3_vecinos_y_juntas"),
        ("organizacion", "0005_evaluacion3_territorios"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # --- trimestre -----------------------------------------------------
        migrations.AddField(
            model_name="periodo", name="anio",
            field=models.PositiveSmallIntegerField(
                default=2026, verbose_name="año",
                help_text="El año al que pertenece el trimestre.",
                validators=[django.core.validators.MinValueValidator(2000),
                            django.core.validators.MaxValueValidator(2100)]),
        ),
        migrations.AddField(
            model_name="periodo", name="numero",
            field=models.PositiveSmallIntegerField(
                default=1, verbose_name="número de trimestre", help_text="Del 1 al 4.",
                validators=[django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(4)]),
        ),
        migrations.AlterModelOptions(
            name="periodo",
            options={"ordering": ["-inicio"], "verbose_name": "trimestre",
                     "verbose_name_plural": "trimestres"},
        ),

        # --- asignación de meta -------------------------------------------
        migrations.AddField(
            model_name="metaperiodo", name="funcionario",
            field=models.ForeignKey(
                blank=True, null=True,
                help_text=("A quién se le asigna. Si se indica, esta meta vale solo para esa "
                           "persona y reemplaza a la de su cargo en ese ítem; si se deja en "
                           "blanco, vale para todo el cargo."),
                on_delete=django.db.models.deletion.PROTECT, related_name="metas_personales",
                to=settings.AUTH_USER_MODEL, verbose_name="funcionario"),
        ),
        migrations.AddField(
            model_name="metaperiodo", name="observacion",
            field=models.TextField(
                blank=True, verbose_name="observación",
                help_text="Por qué se asignó así. Queda en la ficha y en el historial."),
        ),
        migrations.AlterField(
            model_name="metaperiodo", name="ponderador",
            field=models.PositiveSmallIntegerField(
                help_text="Cuánto pesa este ítem en el resultado, entre 0 y 100.",
                validators=[django.core.validators.MaxValueValidator(100)]),
        ),
        migrations.AlterField(
            model_name="metaperiodo", name="creada",
            field=models.DateField(auto_now_add=True, verbose_name="fecha de asignación"),
        ),
        migrations.AddConstraint(
            model_name="metaperiodo",
            constraint=models.UniqueConstraint(
                fields=("periodo", "cargo", "item", "funcionario"),
                name="una_asignacion_por_periodo_cargo_item_persona"),
        ),
        migrations.RemoveConstraint(
            model_name="metaperiodo", name="una_meta_por_periodo_cargo_item",
        ),
        migrations.AlterModelOptions(
            name="metaperiodo",
            options={"ordering": ["periodo", "cargo", "item"],
                     "verbose_name": "asignación de meta",
                     "verbose_name_plural": "asignaciones de meta"},
        ),

        # --- hitos ---------------------------------------------------------
        migrations.CreateModel(
            name="Hito",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True,
                                           serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(
                    help_text="Identificador corto e irrepetible, por ejemplo HIT-01.",
                    max_length=10, unique=True, verbose_name="código")),
                ("nombre", models.CharField(max_length=120)),
                ("descripcion", models.TextField(help_text="Qué se hace y para quién.",
                                                 verbose_name="descripción")),
                ("periodicidad", models.CharField(
                    choices=[("unica", "Una sola vez"), ("semanal", "Semanal"),
                             ("mensual", "Mensual"), ("trimestral", "Trimestral"),
                             ("anual", "Anual")],
                    default="unica", max_length=12)),
                ("fecha_inicio", models.DateField(verbose_name="fecha de inicio")),
                ("fecha_termino", models.DateField(
                    help_text="No puede ser anterior al inicio.", verbose_name="fecha de término")),
                ("activo", models.BooleanField(default=True)),
                ("creada", models.DateField(auto_now_add=True, verbose_name="creado el")),
                ("desactivada", models.DateField(blank=True, null=True,
                                                 verbose_name="desactivado el")),
                ("delegacion", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT, related_name="hitos",
                    to="organizacion.delegacion", verbose_name="delegación")),
                ("territorio", models.ForeignKey(
                    blank=True, null=True,
                    help_text="Opcional. Si se indica, tiene que ser de la misma delegación.",
                    on_delete=django.db.models.deletion.PROTECT, related_name="hitos",
                    to="organizacion.territorio", verbose_name="territorio")),
                ("responsables", models.ManyToManyField(
                    help_text="Al menos una persona que trabaje en la delegación.",
                    related_name="hitos_a_cargo", to=settings.AUTH_USER_MODEL,
                    verbose_name="responsables")),
            ],
            options={"verbose_name": "hito", "verbose_name_plural": "hitos",
                     "ordering": ["fecha_inicio", "codigo"]},
        ),

        # --- actividad -----------------------------------------------------
        migrations.AddField(
            model_name="actividad", name="asignacion",
            field=models.ForeignKey(
                blank=True, null=True,
                help_text="La meta a la que suma. Define el ítem y el período.",
                on_delete=django.db.models.deletion.PROTECT, related_name="actividades",
                to="gestion.metaperiodo", verbose_name="asignación de meta"),
        ),
        migrations.AddField(
            model_name="actividad", name="hito",
            field=models.ForeignKey(
                blank=True, null=True,
                help_text="Opcional: el hito planificado al que corresponde.",
                on_delete=django.db.models.deletion.PROTECT, related_name="actividades",
                to="gestion.hito", verbose_name="hito"),
        ),
        migrations.AddField(
            model_name="actividad", name="tipo",
            field=models.CharField(
                choices=[("terreno", "Terreno"), ("oficina", "Oficina"), ("reunion", "Reunión"),
                         ("coordinacion", "Coordinación"), ("otra", "Otra")],
                default="terreno", max_length=14, verbose_name="tipo de actividad"),
        ),
        migrations.AddField(
            model_name="actividad", name="origen",
            field=models.CharField(
                choices=[("planificada", "Planificada por la delegación"),
                         ("comunidad", "Solicitud de la comunidad"),
                         ("municipio", "Encargo del municipio"),
                         ("derivacion", "Derivación de otra unidad")],
                default="planificada", max_length=12),
        ),
        migrations.AddField(
            model_name="actividad", name="solicitante",
            field=models.ForeignKey(
                blank=True, null=True,
                help_text="El vecino que la pidió, si vino de la comunidad.",
                on_delete=django.db.models.deletion.PROTECT, related_name="actividades",
                to="atencion.solicitante", verbose_name="solicitante"),
        ),
        migrations.AddField(
            model_name="actividad", name="territorio",
            field=models.ForeignKey(
                blank=True, null=True,
                help_text="Dónde ocurrió. Tiene que ser de la misma delegación.",
                on_delete=django.db.models.deletion.PROTECT, related_name="actividades",
                to="organizacion.territorio", verbose_name="territorio"),
        ),
        migrations.AddField(
            model_name="actividad", name="responsable",
            field=models.ForeignKey(
                blank=True, null=True,
                help_text="Quién responde por el seguimiento. Por omisión, quien la registra.",
                on_delete=django.db.models.deletion.PROTECT, related_name="actividades_a_cargo",
                to=settings.AUTH_USER_MODEL, verbose_name="responsable"),
        ),
        migrations.AddField(
            model_name="actividad", name="fecha_compromiso",
            field=models.DateField(
                blank=True, null=True, verbose_name="fecha de compromiso",
                help_text=("Hasta cuándo hay plazo para el seguimiento. No puede ser anterior "
                           "a la fecha de la actividad.")),
        ),
        migrations.AddField(
            model_name="actividad", name="apoyo",
            field=models.CharField(
                blank=True, max_length=160,
                help_text="Quién o qué apoyó: otra unidad, un vehículo, materiales."),
        ),
        migrations.AddField(
            model_name="actividad", name="avance",
            field=models.PositiveSmallIntegerField(
                default=100, verbose_name="avance (%)",
                help_text="Cuánto del trabajo está hecho, de 0 a 100.",
                validators=[django.core.validators.MinValueValidator(0),
                            django.core.validators.MaxValueValidator(100)]),
        ),
        migrations.AddField(
            model_name="actividad", name="resultado",
            field=models.TextField(blank=True, help_text="Qué se logró. Opcional."),
        ),

        # --- evidencia -----------------------------------------------------
        migrations.AlterField(
            model_name="evidencia", name="actividad",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="evidencias", to="gestion.actividad", verbose_name="actividad"),
        ),
        migrations.AddField(
            model_name="evidencia", name="caso",
            field=models.ForeignKey(
                blank=True, null=True,
                help_text="Si respalda una gestión social en vez de una actividad.",
                on_delete=django.db.models.deletion.PROTECT, related_name="evidencias",
                to="atencion.casosocial", verbose_name="gestión social"),
        ),
        migrations.AddField(
            model_name="evidencia", name="tipo",
            field=models.CharField(
                choices=[("acta", "Acta"), ("fotografia", "Fotografía"),
                         ("lista", "Lista de asistencia"), ("informe", "Informe"),
                         ("oficio", "Oficio o carta"), ("otro", "Otro documento")],
                default="acta", max_length=12),
        ),
        migrations.AddField(
            model_name="evidencia", name="observacion",
            field=models.TextField(
                blank=True, verbose_name="observación",
                help_text="Lo que conviene saber al revisarla. Opcional."),
        ),
        migrations.AddConstraint(
            model_name="evidencia",
            constraint=models.CheckConstraint(
                check=(models.Q(actividad__isnull=False, caso__isnull=True)
                       | models.Q(actividad__isnull=True, caso__isnull=False)),
                name="evidencia_de_un_solo_origen"),
        ),
    ]
