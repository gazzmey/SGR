"""
Versiones de los parámetros de medición (HU-25 y HU-38).

Los parámetros que deciden un resultado —qué se mide (ítems), cuánto se pide
y cuánto pesa (metas y ponderadores) y con qué reglas se calcula— cambian con
el tiempo. La HU-25 pide que cambiarlos no borre la historia: cada cambio
guarda una versión nueva, con su vigencia, su autor y la versión anterior. La
HU-38 pide poder consultarla, para explicar por qué un resultado histórico se
calculó como se calculó.

Cómo se arma
------------
Cada versión es una **foto** de los campos del parámetro después del cambio,
más la lista de lo que cambió respecto de la anterior. La primera vez que se
toca un parámetro que todavía no tiene historia, antes de la versión nueva se
guarda la foto de cómo estaba: así la «versión anterior» existe aunque el
parámetro se haya creado antes de que hubiera historial.

Por qué se escribe desde las vistas y no con señales
----------------------------------------------------
Por la misma razón que la auditoría (``comun/auditoria.py``): una señal no
sabe quién hizo el cambio. Las versiones las escriben el motor de
mantenedores, el cierre de período y el comando de carga, que sí lo saben.

Y cómo eso protege los períodos cerrados
----------------------------------------
Las versiones dejan constancia, pero lo que impide que un cambio altere un
resultado cerrado son tres reglas que viven en otros lugares: las metas de
un período cerrado no se editan, la regla se congela como copia propia del
período al cerrarlo y ya no se edita, y un ítem usado en un período cerrado
no cambia su forma de medirse.
"""

from django.conf import settings
from django.db import models


class VersionParametro(models.Model):
    """Una versión de un ítem, una meta o una regla de cálculo."""

    class Tipo(models.TextChoices):
        ITEM = "item", "Ítem"
        META = "meta", "Meta y ponderador"
        REGLA = "regla", "Regla de cálculo"

    class Origen(models.TextChoices):
        PANTALLA = "pantalla", "Cambio desde el sistema"
        PREVIO = "previo", "Estado previo al historial"
        CIERRE = "cierre", "Congelada al cerrar el período"
        COMANDO = "comando", "Carga por comando"

    tipo = models.CharField(max_length=6, choices=Tipo.choices)
    objeto_id = models.PositiveIntegerField("identificador del parámetro")
    version = models.PositiveIntegerField("versión")
    etiqueta = models.CharField(
        "parámetro", max_length=200,
        help_text="Cómo se llamaba el parámetro en esta versión.",
    )
    periodo = models.ForeignKey(
        "gestion.Periodo", on_delete=models.PROTECT, null=True, blank=True,
        related_name="versiones", verbose_name="período",
    )
    vigencia = models.CharField(max_length=200)
    datos = models.JSONField(default=dict)
    cambios = models.JSONField(default=list)
    origen = models.CharField(max_length=8, choices=Origen.choices,
                              default=Origen.PANTALLA)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="versiones_parametros", verbose_name="autor",
    )
    creada = models.DateTimeField("registrada el", auto_now_add=True)

    class Meta:
        verbose_name = "versión de parámetro"
        verbose_name_plural = "versiones de parámetros"
        ordering = ["-creada", "-version"]
        constraints = [
            models.UniqueConstraint(fields=["tipo", "objeto_id", "version"],
                                    name="una_version_por_numero"),
        ]

    def __str__(self):
        return f"{self.etiqueta} · versión {self.version}"

    @property
    def nombre(self):
        return self.etiqueta

    @property
    def autor_nombre(self):
        if not self.autor_id:
            return "Sistema"
        return self.autor.get_full_name() or self.autor.get_username()
