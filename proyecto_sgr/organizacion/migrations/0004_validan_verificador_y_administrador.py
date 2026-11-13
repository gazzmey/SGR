"""
Validar evidencias queda solo en el Verificador y el Administrador.

La regla de separación de funciones es que nadie apruebe su propio trabajo.
En el código eso se cumple de dos maneras: nadie decide sobre una evidencia
o un compromiso propio, y un rol no puede tener a la vez «registrar
actividades» y «validar evidencias» (``comun.permisos.INCOMPATIBLES``).

Esta migración deja los roles que ya existen de acuerdo con eso:

    · el Administrador recibe «validar evidencias», que antes no tenía;
    · el Verificador lo conserva;
    · cualquier otro rol lo pierde, si alguien se lo había marcado;
    · a quien valida se le quita «registrar actividades», si lo tuviera.

Los roles se reconocen por su código de la carga inicial (ROL-02, ROL-05) o
por su nombre, para no depender de uno solo.
"""

from django.db import migrations

VALIDAR = "validar_evidencia"
REGISTRAR = "registrar_actividad"


def _valida(rol):
    nombre = (rol.nombre or "").strip().lower()
    return rol.codigo in ("ROL-02", "ROL-05") or nombre in ("verificador", "administrador")


def aplicar(apps, schema_editor):
    Rol = apps.get_model("organizacion", "Rol")
    for rol in Rol.objects.all():
        antes = list(rol.permisos or [])
        permisos = list(antes)
        if _valida(rol):
            if VALIDAR not in permisos:
                permisos.append(VALIDAR)
            if REGISTRAR in permisos:
                permisos.remove(REGISTRAR)
        elif VALIDAR in permisos:
            permisos.remove(VALIDAR)
        if permisos != antes:
            rol.permisos = permisos
            rol.save(update_fields=["permisos"])


class Migration(migrations.Migration):

    dependencies = [
        ("organizacion", "0003_perfilusuario_cargo_asignado"),
    ]

    operations = [
        migrations.RunPython(aplicar, migrations.RunPython.noop),
    ]
