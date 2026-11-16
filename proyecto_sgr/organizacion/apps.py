from django.apps import AppConfig
from django.db.models.signals import post_migrate


class OrganizacionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "organizacion"
    verbose_name = "Organización"

    def ready(self):
        # Los grupos Consulta y Gestión se arman después de migrar, cuando
        # Django ya creó los permisos de todos los modelos (organizacion/grupos.py).
        from organizacion.grupos import al_migrar

        post_migrate.connect(al_migrar, dispatch_uid="sgr_grupos_de_prueba")
