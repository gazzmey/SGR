"""
Rutas del proyecto.

Cada aplicación trae su propio archivo de rutas y aquí se montan bajo un
prefijo. Así el nombre completo de una ruta dice de dónde viene
—``organizacion:delegaciones``, ``catalogos:items``— y ninguna aplicación
necesita saber en qué dirección la montaron.

El administrador de Django se conserva. En la entrega de Back End era la
única interfaz; aquí sigue disponible para el superusuario, pero la
operación normal ocurre en las pantallas del SGR.
"""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuenta/", include("cuenta.urls")),
    path("gestion/", include("organizacion.urls")),
    path("catalogo/", include("catalogos.urls")),
    path("periodo/", include("gestion.urls")),
    path("atencion/", include("atencion.urls")),
    # El panel se monta en la raíz y va al final, por orden de lectura: de lo
    # específico a lo general.
    path("", include("comun.urls")),
]

# Páginas de error con la identidad del sistema. Solo se usan con DEBUG=False;
# con DEBUG=True Django muestra su propia página de depuración, que es lo que
# se quiere mientras se desarrolla.
handler403 = "comun.views.sin_permiso"
handler404 = "comun.views.no_encontrado"

if settings.DEBUG:
    # El servidor de desarrollo sirve los archivos estáticos solo si está
    # declarado. En producción los sirve WhiteNoise, configurado en settings.
    from django.conf.urls.static import static

    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

admin.site.site_header = "Sistema de Gestión de Resultados"
admin.site.site_title = "SGR"
admin.site.index_title = "Administración de datos"
