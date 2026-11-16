"""
Los grupos de Django de los perfiles de prueba: **Consulta** y **Gestión**.

La Evaluación 3 pide configurar grupos y permisos con Django. Los dos
grupos se arman con los permisos que Django crea solo para cada modelo
(``view``, ``add``, ``change``, ``delete``) de las 17 entidades:

* Consulta: ``view`` de las 17. Ve todo, no cambia nada.
* Gestión: las cuatro operaciones de las 17. No administra privilegios: el
  formulario de privilegios del rol pide la acción «Gestionar usuarios y
  roles», que este grupo no tiene.

Cuándo se arma
--------------
Al terminar cada ``migrate`` (señal ``post_migrate``), cuando Django ya
creó los permisos de todos los modelos. Hace solo lo que falta:

* si el grupo no existe, lo crea con sus permisos, crea el rol que lo usa
  y deja al rol Administrador en el grupo Gestión;
* si existe pero quedó sin permisos, se los vuelve a poner.

Un grupo que el administrador ajustó a mano desde Django Admin no se toca:
la señal corre en cada despliegue y no puede pisar esa decisión.
"""

from django.db import transaction

DESCRIPCIONES = {
    "Consulta": ("ROL-07", "Consulta", "Consulta las 17 entidades del sistema sin poder "
                 "crear, editar, desactivar ni anular nada."),
    "Gestión": ("ROL-08", "Gestión", "Crea, edita, desactiva y anula registros de las 17 "
                "entidades. No administra privilegios de roles ni usuarios."),
}


def permisos_del_grupo(nombre):
    from django.contrib.auth.models import Permission
    from django.db.models import Q

    from comun.entidades import ENTIDADES, GRUPOS

    condicion = Q()
    for entidad in ENTIDADES:
        for accion in GRUPOS[nombre]:
            condicion |= Q(content_type__app_label=entidad.app,
                           codename=entidad.codename(accion))
    return Permission.objects.filter(condicion)


@transaction.atomic
def asegurar_grupos(salida=None):
    """Crea o completa los dos grupos y sus roles. Se puede llamar varias veces."""
    from django.contrib.auth.models import Group

    from comun import permisos as P
    from comun.entidades import GRUPOS
    from comun.utilidades import proximo_codigo
    from organizacion.models import Rol

    for nombre in GRUPOS:
        grupo, creado = Group.objects.get_or_create(name=nombre)
        if creado or not grupo.permissions.exists():
            grupo.permissions.set(permisos_del_grupo(nombre))
            if salida:
                salida(f"  Grupo de Django «{nombre}»: {grupo.permissions.count()} permisos")
        if not creado:
            continue

        if not Rol.objects.filter(grupo=grupo).exists():
            codigo, rol_nombre, descripcion = DESCRIPCIONES[nombre]
            rol = Rol.objects.filter(nombre=rol_nombre).first()
            if rol is None:
                if Rol.objects.filter(codigo=codigo).exists():
                    codigo = proximo_codigo(Rol, "ROL")
                rol = Rol(codigo=codigo, nombre=rol_nombre,
                          descripcion=descripcion, alcance=Rol.Alcance.TODAS, permisos=[])
            rol.grupo = grupo
            rol.save()

        if nombre == "Gestión":
            # Quien administra usuarios y catálogos administra también las
            # entidades nuevas: el rol Administrador entra al grupo Gestión.
            for rol in Rol.objects.filter(grupo__isnull=True):
                if P.GESTIONAR_USUARIO in (rol.permisos or []):
                    rol.grupo = grupo
                    rol.save()


def al_migrar(sender, **kwargs):
    """Receptor de post_migrate: actúa una vez, con la última app migrada."""
    from django.apps import apps

    con_modelos = [a for a in apps.get_app_configs() if a.models_module is not None]
    if not con_modelos or sender.name != con_modelos[-1].name:
        return
    asegurar_grupos()
