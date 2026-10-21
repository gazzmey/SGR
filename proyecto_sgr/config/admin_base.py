"""Utilidades compartidas por los administradores de las aplicaciones."""

from django.contrib import admin, messages
from django.db.models import Q


class SoloActivosEnSelectores:
    """
    Limita los desplegables de clave foránea a los registros activos.

    El requisito es que los selectores ofrezcan opciones válidas. Si el registro
    que se está editando apunta a un elemento que fue desactivado después, ese
    elemento se mantiene en la lista para no perder el dato ni bloquear la
    edición.

    No se combina con ``autocomplete_fields``: el widget de autocompletado
    resuelve sus opciones consultando el administrador del modelo destino, de
    modo que ignoraría el queryset definido aquí y volvería a ofrecer los
    registros inactivos.
    """

    selectores_solo_activos = ()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in self.selectores_solo_activos:
            modelo = db_field.remote_field.model
            condicion = Q(activo=True)
            en_uso = self._claves_en_uso(request, db_field.name)
            if en_uso:
                condicion |= Q(pk__in=en_uso)
            kwargs["queryset"] = modelo.objects.filter(condicion)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def _claves_en_uso(self, request, nombre_campo):
        """
        Claves que el registro en edición ya tiene asignadas en ese campo.

        En un formulario normal el identificador de la dirección corresponde al
        propio registro. Dentro de un inline corresponde al registro padre, así
        que primero hay que ubicar el campo que enlaza con él.
        """
        coincidencia = getattr(request, "resolver_match", None)
        if coincidencia is None:
            return set()
        object_id = coincidencia.kwargs.get("object_id")
        if not object_id:
            return set()

        padre = getattr(self, "parent_model", None)
        if padre is None:
            filtro = {"pk": object_id}
        else:
            enlace = next(
                (campo.name for campo in self.model._meta.fields
                 if getattr(campo, "related_model", None) is padre),
                None,
            )
            if enlace is None:
                return set()
            filtro = {enlace: object_id}

        claves = self.model.objects.filter(**filtro).values_list(
            f"{nombre_campo}_id", flat=True
        )
        return {clave for clave in claves if clave is not None}


@admin.action(description="Marcar como activo")
def activar(modeladmin, request, queryset):
    actualizados = queryset.update(activo=True)
    modeladmin.message_user(
        request,
        f"{actualizados} registro(s) marcados como activos.",
        messages.SUCCESS,
    )


@admin.action(description="Marcar como inactivo")
def desactivar(modeladmin, request, queryset):
    actualizados = queryset.update(activo=False)
    modeladmin.message_user(
        request,
        f"{actualizados} registro(s) marcados como inactivos.",
        messages.SUCCESS,
    )
