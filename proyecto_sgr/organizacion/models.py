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
from django.core.exceptions import ValidationError
from django.db import models

from comun.rut import limpiar_rut, validar_rut


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
    delegado = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="delegaciones_a_cargo", null=True, blank=True,
        verbose_name="delegado",
        help_text=(
            "Quien encabeza la delegación. Tiene que ser un usuario activo "
            "que trabaje en ella o tenga alcance sobre ella."
        ),
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
        territorios = self.territorios.filter(activo=True).count()
        if territorios:
            return (
                f"Tiene {territorios} "
                f"{'territorio activo' if territorios == 1 else 'territorios activos'}. "
                "Desactívalos o muévelos a otra delegación antes."
            )
        return ""

    def clean(self):
        super().clean()
        if self.delegado_id:
            perfil = getattr(self.delegado, "perfil", None)
            if not self.delegado.is_active or perfil is None or not perfil.activo:
                raise ValidationError({
                    "delegado": "El delegado tiene que ser un usuario activo del sistema.",
                })
            alcanza = perfil.rol.alcance == Rol.Alcance.TODAS or (
                self.pk and perfil.delegaciones_visibles().filter(pk=self.pk).exists())
            if not alcanza:
                raise ValidationError({
                    "delegado": (
                        "%s no trabaja en esta delegación ni tiene alcance sobre "
                        "ella. Asígnale la delegación en su ficha de usuario "
                        "antes de nombrarlo delegado." % perfil.nombre
                    ),
                })


class Territorio(models.Model):
    """
    El sector o unidad vecinal que atiende una delegación.

    En la segunda entrega era un texto libre en la ficha del vecino. Como
    entidad propia, el territorio se relaciona con su delegación y lo usan
    los vecinos, las juntas de vecinos, los hitos y las actividades.
    """

    codigo = models.CharField(
        "código", max_length=10, unique=True,
        help_text="Identificador corto e irrepetible, por ejemplo TER-01.",
    )
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(
        "descripción", blank=True,
        help_text="Qué calles, poblaciones o sectores comprende.",
    )
    delegacion = models.ForeignKey(
        Delegacion, on_delete=models.PROTECT,
        related_name="territorios", verbose_name="delegación",
    )
    activo = models.BooleanField(default=True)
    creada = models.DateField("creado el", auto_now_add=True)
    desactivada = models.DateField("desactivado el", null=True, blank=True)

    class Meta:
        verbose_name = "territorio"
        verbose_name_plural = "territorios"
        ordering = ["codigo"]
        constraints = [
            models.UniqueConstraint(
                fields=["delegacion", "nombre"],
                name="un_nombre_de_territorio_por_delegacion",
            ),
        ]

    def __str__(self):
        return f"{self.codigo} — {self.nombre}"

    def clean(self):
        super().clean()
        # Un territorio nuevo, o uno que se cambia de delegación, no puede
        # quedar en una delegación inactiva. Uno que ya estaba en ella se
        # puede seguir editando.
        if self.delegacion_id and not self.delegacion.activo:
            anterior = (Territorio.objects.filter(pk=self.pk)
                        .values_list("delegacion_id", flat=True).first()
                        if self.pk else None)
            if anterior != self.delegacion_id:
                raise ValidationError({
                    "delegacion": "Esa delegación está inactiva: elige una activa.",
                })

    def motivo_bloqueo(self):
        """Lo que impide desactivarlo: quien todavía depende de él."""
        partes = []
        vecinos = self.vecinos.filter(activo=True).count()
        if vecinos:
            partes.append(f"{vecinos} {'vecino activo' if vecinos == 1 else 'vecinos activos'}")
        juntas = self.juntas.filter(activo=True).count()
        if juntas:
            partes.append(f"{juntas} {'junta de vecinos activa' if juntas == 1 else 'juntas de vecinos activas'}")
        hitos = self.hitos.filter(activo=True).count()
        if hitos:
            partes.append(f"{hitos} {'hito activo' if hitos == 1 else 'hitos activos'}")
        if partes:
            return (
                "Tiene " + ", ".join(partes) + ". Muévelos a otro territorio o "
                "desactívalos antes."
            )
        return ""

    def motivo_bloqueo_activar(self):
        if not self.delegacion.activo:
            return "Su delegación está inactiva. Actívala primero."
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
    grupo = models.ForeignKey(
        "auth.Group", on_delete=models.PROTECT,
        related_name="roles_sgr", null=True, blank=True,
        verbose_name="grupo de Django",
        help_text=(
            "Los permisos de Django (ver, crear, editar, desactivar) que el "
            "rol entrega sobre las 17 entidades. Lo configura el "
            "administrador; no se edita desde el formulario general."
        ),
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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Cambiar el grupo o el estado del rol cambia lo que pueden hacer sus
        # usuarios: se les actualiza el grupo de Django en el mismo momento.
        for perfil in self.perfiles.select_related("usuario"):
            perfil.sincronizar_grupos()


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
    rut = models.CharField(
        "RUT", max_length=12, unique=True, null=True, blank=True,
        validators=[validar_rut],
        help_text="Ficticio, con dígito verificador. Por ejemplo 11111111-1.",
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

    def save(self, *args, **kwargs):
        # Un RUT vacío se guarda como NULL: la restricción de unicidad admite
        # varios NULL, pero no dos textos vacíos.
        self.rut = limpiar_rut(self.rut) or None
        super().save(*args, **kwargs)
        self.sincronizar_grupos()

    def sincronizar_grupos(self):
        """
        Deja al usuario de Django en el grupo de su rol, y solo en ese.

        Solo se tocan los grupos que algún rol administra: un grupo que el
        administrador asignó a mano desde Django Admin no se quita. Un
        perfil o un rol inactivo no conserva ningún grupo de rol.
        """
        from django.contrib.auth.models import Group

        administrados = set(
            Group.objects.filter(roles_sgr__isnull=False).values_list("pk", flat=True)
        )
        if not administrados:
            return
        actuales = set(self.usuario.groups.values_list("pk", flat=True))
        deseado = (self.rol.grupo_id
                   if self.activo and self.rol.activo and self.rol.grupo_id else None)
        quitar = (actuales & administrados) - {deseado}
        if quitar:
            self.usuario.groups.remove(*quitar)
        if deseado and deseado not in actuales:
            self.usuario.groups.add(deseado)

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
