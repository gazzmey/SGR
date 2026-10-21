"""
Alinea el texto de ayuda de los códigos con los de la maqueta aprobada.

La Unidad 2 ponía como ejemplo ``TA-01`` y ``SA-01``. Las pantallas de la
segunda entrega usan prefijos de tres letras en los seis mantenedores
—DEL, ROL, USR, ITM, TAT, SAT— y los códigos que asigna
``comun.utilidades.proximo_codigo`` siguen esa convención, así que el texto
de ayuda tenía que decir lo mismo.

Esta migración **no cambia el esquema**. ``help_text`` es documentación: no
existe en la base de datos, y al aplicarla no se ejecuta ninguna sentencia
sobre las tablas. Existe porque Django compara el estado de los modelos con
el de las migraciones y avisa si no coinciden; sin ella,
``makemigrations --check`` fallaría aunque la base estuviera perfecta.

Por eso es segura respecto de la entrega de Back End: esa entrega sigue
leyendo y escribiendo las mismas columnas, con los mismos tipos.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogos", "0002_entrega2"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tipoatencion",
            name="codigo",
            field=models.CharField(
                help_text="Identificador corto e irrepetible, por ejemplo TAT-01.",
                max_length=10,
                unique=True,
                verbose_name="código",
            ),
        ),
        migrations.AlterField(
            model_name="subatencion",
            name="codigo",
            field=models.CharField(
                help_text="Identificador corto e irrepetible, por ejemplo SAT-01.",
                max_length=10,
                unique=True,
                verbose_name="código",
            ),
        ),
    ]
