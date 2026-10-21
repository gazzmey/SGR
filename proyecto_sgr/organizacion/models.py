"""
Estructura organizacional del SGR: delegaciones, roles y perfiles de usuario.

Los tres modelos tienen un campo ``activo`` porque la operación municipal
necesita retirar una delegación o un rol de circulación sin borrar los
registros históricos que lo referencian.

Sobre esta entrega
------------------
Los modelos vienen de la Unidad 2 de Back End y aquí se amplían con lo que
pide la segunda entrega del Proyecto Integrado. Lo importante del cambio en
``PerfilUsuario``: se **suma** ``delegaciones_autorizadas`` y se conserva
``delegacion``. Quien trabaja en una sola delegación mantiene su contexto
fijo; quien tiene varias ve el selector de la cabecera. Reemplazar el campo
habría invalidado la entrega anterior.
"""

from django.conf import settings
from django.db import models


class Delegacion(models.Model):
    """Unidad territorial donde se presta atención a la comunidad."""

    class Zona(models.TextChoices):
        URBANA = "Urbana", "Urbana"
        RURAL = "Rural", "Rural"
        COSTERA = "Costera", "Costera"

    codigo = models.CharField(
        "código", max_length=10, unique=True,
        help_text="Identificador corto e irrepetible, por ejemplo DEL-01.",
    )
    nombre = models.CharField(max_length=120, unique=True)
    zona = models.CharField(
        max_length=10, choices=Zona.choices, default=Zona.URBANA,
        help_text="Determina en qué informes territoriales se agrupa.",
    )
    direccion = models.CharField("dirección", max_length=160, blank=True)
    comuna = models.CharField(max_length=80, default="La Serena")
    telefono = models.CharField("teléfono", max_length=20, blank=True)
    horario = models.CharField(
        "horario de atención", max_length=120, blank=True,
        help_text="Por ejemplo: Lun a vie · 08:30 a 14:00.",
    )
    activo = models.BooleanField(
        "activa", default=True,
        help_text="Las delegaciones inactivas dejan de ofrecerse en los formularios.",
    )
    creada = models.DateField("creada el", auto_now_add=True)
    desactivada = models.DateField("desactivada el", null=True, blank=True)

    class Meta:
        verbose_name = "delegación"
        verbose_name_plural = "delegaciones"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"

    def motivo_bloqueo(self):
        """
        Por qué no se puede desactivar, o cadena vacía si se puede.

        Es el reflejo de ``on_delete=PROTECT``: antes de dejar que alguien
        desactive una delegación comprobamos que no queden perfiles
        apuntando a ella.
        """
        cuantos = self.perfiles.count()
        if cuantos:
            return (
                f"Tiene {cuantos} "
                f"{'perfil de usuario asignado' if cuantos == 1 else 'perfiles de usuario asignados'}. "
                "Reasigna esos usuarios a otra delegación antes de desactivarla."
            )
        return ""


class Rol(models.Model):
    """
    Función que cumple un usuario dentro del sistema.

    ``permisos`` guarda la lista de acciones que el rol habilita. Se usa un
    JSONField porque la lista es corta, se lee entera y nunca se consulta por
    uno de sus elementos desde la base de datos; MariaDB 10.2.7 en adelante lo
    soporta sin extensiones.
    """

    class Alcance(models.TextChoices):
        PROPIA = "propia", "Su delegación"
        VARIAS = "varias", "Varias delegaciones"
        TODAS = "todas", "Todas las delegaciones"

    codigo = models.CharField(
        "código", max_length=10, unique=True, default="ROL-00",
        help_text="Identificador corto e irrepetible, por ejemplo ROL-01.",
    )
    nombre = models.CharField(max_length=60, unique=True)
    descripcion = models.CharField("descripción", max_length=200, blank=True)
    alcance = models.CharField(
        max_length=10, choices=Alcance.choices, default=Alcance.PROPIA,
        help_text="Sobre qué delegaciones puede actuar quien tiene el rol.",
    )
    permisos = models.JSONField(
        default=list, blank=True,
        help_text="Lista de claves de permiso. Ver comun/permisos.py.",
    )
    activo = models.BooleanField(default=True)
    creada = models.DateField("creado el", auto_now_add=True)
    desactivada = models.DateField("desactivado el", null=True, blank=True)

    class Meta:
        verbose_name = "rol"
        verbose_name_plural = "roles"
        ordering = ["codigo"]

    def __str__(self):
        return self.nombre

    def motivo_bloqueo(self):
        cuantos = self.perfiles.count()
        if cuantos:
            return (
                f"Tiene {cuantos} {'usuario asignado' if cuantos == 1 else 'usuarios asignados'}. "
                "Quítales el rol antes de desactivarlo."
            )
        return ""


class PerfilUsuario(models.Model):
    """
    Datos del SGR que acompañan a un usuario de Django.

    El perfil no reemplaza al modelo ``User``: lo complementa indicando el rol
    que cumple la persona y la delegación donde trabaja.
    """

    codigo = models.CharField(
        "código", max_length=10, unique=True, default="USR-00",
        help_text="Identificador corto e irrepetible, por ejemplo USR-01.",
    )
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil",
        verbose_name="usuario",
    )
    cargo = models.CharField(
        max_length=80, blank=True,
        help_text="Informativo. Lo que habilita pantallas es el rol.",
    )
    cargo_asignado = models.ForeignKey(
        "gestion.Cargo",
        on_delete=models.PROTECT,
        related_name="perfiles",
        null=True, blank=True,
        verbose_name="cargo con metas",
        help_text=(
            "El cargo del catálogo, que decide con qué ítems y metas se mide "
            "a esta persona. El campo «cargo» de arriba es el texto que se "
            "muestra; este es el que usa el cálculo."
        ),
    )
    rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        related_name="perfiles",
        verbose_name="rol",
    )
    delegacion = models.ForeignKey(
        Delegacion,
        on_delete=models.PROTECT,
        related_name="perfiles",
        verbose_name="delegación base",
    )
    delegaciones_autorizadas = models.ManyToManyField(
        Delegacion,
        blank=True,
        related_name="perfiles_autorizados",
        verbose_name="delegaciones autorizadas",
        help_text="Si hay más de una, la cabecera ofrece el selector para cambiar.",
    )
    activo = models.BooleanField(default=True)
    creada = models.DateField("creado el", auto_now_add=True)
    desactivada = models.DateField("desactivado el", null=True, blank=True)

    class Meta:
        verbose_name = "perfil de usuario"
        verbose_name_plural = "perfiles de usuario"
        ordering = ["codigo"]

    def __str__(self):
        nombre = self.usuario.get_full_name() or self.usuario.username
        return f"{nombre} ({self.rol})"

    # --- lo que el resto del sistema le pregunta al perfil ---------------

    @property
    def nombre(self):
        return self.usuario.get_full_name() or self.usuario.username

    @property
    def correo(self):
        return self.usuario.email

    @property
    def iniciales(self):
        partes = [p for p in self.nombre.split() if p]
        return "".join(p[0] for p in partes[:2]).upper() or "SG"

    def delegaciones_visibles(self):
        """
        Las delegaciones entre las que puede moverse esta persona.

        El alcance del rol manda: con «todas» ve el sistema completo, con
        «varias» ve las que le autorizaron, y con «su delegación» solo la
        suya. Esto es lo que alimenta el selector de la cabecera y, más
        importante, lo que limita cada listado en el servidor.
        """
        if self.rol.alcance == Rol.Alcance.TODAS:
            return Delegacion.objects.filter(activo=True)
        if self.rol.alcance == Rol.Alcance.VARIAS:
            autorizadas = self.delegaciones_autorizadas.filter(activo=True)
            if autorizadas.exists():
                return autorizadas
        return Delegacion.objects.filter(pk=self.delegacion_id)

    def puede(self, clave):
        """True si el rol de esta persona habilita esa acción."""
        return bool(
            self.activo and self.rol.activo and clave in (self.rol.permisos or [])
        )

    def motivo_bloqueo(self):
        """
        No se puede dejar al sistema sin nadie que gestione el acceso.

        Es una regla de negocio, no de base de datos, y por eso vive aquí:
        es la clase la que sabe qué significa quedarse sin administradores.

        La comprobación se hace en Python y no con un filtro sobre el
        JSONField a propósito: son pocos perfiles, se entiende de un vistazo
        y funciona igual en cualquier motor.
        """
        from comun.permisos import GESTIONAR_USUARIO

        if not self.activo or GESTIONAR_USUARIO not in (self.rol.permisos or []):
            return ""

        otros = [
            perfil
            for perfil in PerfilUsuario.objects.filter(activo=True)
            .exclude(pk=self.pk)
            .select_related("rol")
            if GESTIONAR_USUARIO in (perfil.rol.permisos or [])
        ]
        if otros:
            return ""
        return (
            "Es el único usuario activo que puede gestionar el acceso. "
            "Si se desactiva, nadie podría volver a administrar usuarios ni "
            "catálogos. Nombra a otro administrador antes."
        )
