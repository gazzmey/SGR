"""
Recuperación de contraseña con un código de seis dígitos.

Django trae su propio flujo de recuperación por enlace firmado. Aquí se usa
un código porque es lo que pide el diseño de la entrega: la persona recibe
seis dígitos por correo y los escribe en pantalla.

Las tres reglas del diseño viven en el modelo, no en la vista, para que se
cumplan venga de donde venga la petición: el código vence a los diez
minutos, sirve una sola vez y admite tres intentos.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class CodigoRecuperacion(models.Model):
    """Código de un solo uso para crear una contraseña nueva."""

    VIGENCIA_MINUTOS = 10
    INTENTOS_MAXIMOS = 3
    # Espera mínima entre un envío y el siguiente. Sin ella, pedir códigos en
    # serie sería gratis: molestaría a la persona dueña del correo y daría una
    # forma barata de generar carga. El valor viene del diseño de la maqueta.
    ESPERA_REENVIO_SEGUNDOS = 45

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="codigos_recuperacion",
        verbose_name="usuario",
    )
    codigo = models.CharField("código", max_length=6)
    creado = models.DateTimeField("creado el", auto_now_add=True)
    expira = models.DateTimeField("vence el")
    usado = models.BooleanField(default=False)
    intentos = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "código de recuperación"
        verbose_name_plural = "códigos de recuperación"
        ordering = ["-creado"]

    def __str__(self):
        return f"{self.usuario} · {self.codigo}"

    # --- creación --------------------------------------------------------

    @classmethod
    def emitir(cls, usuario):
        """
        Anula los códigos anteriores de esa persona y emite uno nuevo.

        Se anulan los anteriores para que pedir un código nuevo invalide el
        viejo: si no, quedarían varios válidos a la vez.
        """
        cls.objects.filter(usuario=usuario, usado=False).update(usado=True)
        return cls.objects.create(
            usuario=usuario,
            codigo=f"{secrets.randbelow(1000000):06d}",
            expira=timezone.now() + timedelta(minutes=cls.VIGENCIA_MINUTOS),
        )

    # --- estado ----------------------------------------------------------

    @property
    def vencido(self):
        return timezone.now() >= self.expira

    @property
    def agotado(self):
        return self.intentos >= self.INTENTOS_MAXIMOS

    @property
    def vigente(self):
        return not (self.usado or self.vencido or self.agotado)

    @property
    def intentos_restantes(self):
        return max(0, self.INTENTOS_MAXIMOS - self.intentos)

    @property
    def segundos_restantes(self):
        return max(0, int((self.expira - timezone.now()).total_seconds()))

    # --- uso -------------------------------------------------------------

    def comprobar(self, escrito):
        """
        Compara el código y descuenta un intento si no coincide.

        Devuelve True solo si está vigente y el código calza. El contador de
        intentos se guarda siempre, porque si no, bastaría con reintentar sin
        límite.
        """
        if not self.vigente:
            return False

        if secrets.compare_digest(self.codigo, str(escrito or "").strip()):
            return True

        self.intentos += 1
        self.save(update_fields=["intentos"])
        return False

    def consumir(self):
        """Marca el código como usado. Se llama al guardar la contraseña."""
        self.usado = True
        self.save(update_fields=["usado"])
