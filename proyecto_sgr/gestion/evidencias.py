"""
Los archivos de las evidencias: qué se acepta, dónde se guarda y cómo se entrega.

Responde a HU-09 y a su caso CU-31 «Validar archivo». Las cuatro reglas:

1. **Solo formatos permitidos y hasta un tamaño máximo.** Los dos valores se
   configuran (``SGR_EVIDENCIA_FORMATOS`` y ``SGR_EVIDENCIA_MAX_MB``) y el
   mensaje de rechazo dice cuáles son, que es lo que piden CU-34 y CU-35.
2. **El contenido tiene que corresponder a la extensión.** Un ejecutable
   renombrado a ``.pdf`` no empieza como un PDF: se revisan los primeros bytes
   de los formatos conocidos.
3. **El nombre lo pone el sistema.** El archivo se guarda como
   ``evidencias/AAAA/MM/<identificador aleatorio>.<extensión>``. El nombre
   original solo se guarda como texto, para mostrarlo.
4. **No tiene dirección pública.** Se guarda en ``MEDIA_ROOT``, que Nginx no
   sirve, y lo entrega una vista que comprueba permisos y fija el tipo de
   contenido según la extensión aceptada, no según lo que declaró el navegador
   de quien lo subió.
"""

import math
import os
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

# Tipo de contenido con que se entrega cada formato conocido. Un formato que
# se agregue por configuración y no esté aquí se entrega siempre como
# descarga, nunca para abrirse en el navegador.
TIPOS = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
}

IMAGENES = {"jpg", "jpeg", "png"}

# Cómo empieza un archivo de cada formato conocido.
FIRMAS = {
    "pdf": b"%PDF-",
    "jpg": b"\xff\xd8\xff",
    "jpeg": b"\xff\xd8\xff",
    "png": b"\x89PNG\r\n\x1a\n",
}


def formatos():
    """Las extensiones aceptadas, en minúscula y sin punto."""
    return [f.strip().lower().lstrip(".") for f in settings.SGR_EVIDENCIA_FORMATOS if f.strip()]


def formatos_texto():
    """«PDF, JPG, JPEG y PNG»: para los mensajes."""
    nombres = [f.upper() for f in formatos()]
    if len(nombres) < 2:
        return "".join(nombres)
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


def accept():
    """El valor del atributo accept del selector de archivos."""
    return ",".join(f".{f}" for f in formatos())


def maximo_mb():
    return settings.SGR_EVIDENCIA_MAX_MB


def extension(nombre):
    return os.path.splitext(nombre or "")[1].lower().lstrip(".")


def tamano_texto(bytes_, hacia_arriba=False):
    """
    «340 KB», «1,2 MB». Coma decimal, como se escribe en Chile.

    ``hacia_arriba`` redondea al décimo superior: en el mensaje de rechazo, un
    archivo apenas sobre el límite no puede aparecer pesando lo mismo que el
    límite («pesa 5,0 MB y el máximo es 5 MB» no se entiende).
    """
    if bytes_ is None:
        return ""
    if bytes_ < 1024 * 1024:
        return f"{max(1, round(bytes_ / 1024))} KB"
    megas = bytes_ / (1024 * 1024)
    if hacia_arriba:
        megas = math.ceil(megas * 10) / 10
    return f"{megas:.1f} MB".replace(".", ",")


def tipo_contenido(nombre):
    return TIPOS.get(extension(nombre), "application/octet-stream")


def se_muestra_en_navegador(nombre):
    """PDF e imágenes se abren en una pestaña; lo demás solo se descarga."""
    return extension(nombre) in TIPOS


def es_imagen(nombre):
    return extension(nombre) in IMAGENES


def ruta_evidencia(instancia, nombre):
    """
    Dónde se guarda el archivo y con qué nombre.

    El identificador es aleatorio: no se puede adivinar el de otra evidencia,
    y el nombre que traía el archivo —que puede tener cualquier cosa— no
    llega nunca al disco.
    """
    return f"evidencias/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{extension(nombre)}"


def validar(archivo):
    """Rechaza el archivo con un motivo que la persona entienda, o no hace nada."""
    ext = extension(archivo.name)
    permitidos = formatos()

    if not ext:
        raise ValidationError(
            f"El archivo no tiene extensión, así que no se puede saber qué es. "
            f"Se aceptan {formatos_texto()}."
        )
    if ext not in permitidos:
        raise ValidationError(
            f"El formato .{ext} no está permitido. Se aceptan {formatos_texto()}."
        )
    if archivo.size == 0:
        raise ValidationError("El archivo está vacío. Vuelve a elegirlo desde el original.")
    if archivo.size > maximo_mb() * 1024 * 1024:
        raise ValidationError(
            f"El archivo pesa {tamano_texto(archivo.size, hacia_arriba=True)} y el máximo es "
            f"{maximo_mb()} MB. Redúcelo —en una foto, bajando la resolución— "
            f"y vuelve a intentarlo."
        )

    firma = FIRMAS.get(ext)
    if firma:
        archivo.seek(0)
        inicio = archivo.read(len(firma))
        archivo.seek(0)
        if inicio != firma:
            raise ValidationError(
                f"El archivo termina en .{ext} pero su contenido no es "
                f"{ext.upper()}. Puede que lo hayan renombrado: súbelo desde "
                f"el original."
            )
