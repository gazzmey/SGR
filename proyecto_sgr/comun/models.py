"""
La auditoría: quién cambió qué, cuándo y desde dónde.

Vive en ``comun`` y no en una aplicación concreta porque registra eventos de
todas: una delegación que se desactiva, una evidencia que se aprueba, un
umbral que se cambia, un período que se reabre. Ponerla dentro de cualquiera
de ellas la ataría a ese módulo, y la auditoría es justamente lo que los
cruza.

Qué guarda, y por qué cada campo
--------------------------------
El caso INT-03 pide que estén disponibles «usuario, fecha, origen, acción,
antes y después». Esos seis son los campos obligatorios de este modelo. Los
otros dos —la entidad y el texto del objeto— existen para que el evento se
pueda leer dentro de un año, cuando el registro que lo originó quizá ya no
exista: por eso se guarda el **texto** del objeto y no solo su identificador.

Por qué el nombre del usuario se copia
--------------------------------------
``quien`` apunta al usuario, pero ``quien_texto`` guarda su nombre tal como
era en ese momento. Si la persona cambia de apellido, o su cuenta se da de
baja, el evento tiene que seguir diciendo quién lo hizo entonces. Una
auditoría que se reescribe sola cuando cambian los datos de referencia no
sirve como auditoría.

Lo que no se puede hacer
------------------------
No hay forma de editar ni borrar un evento: no existe formulario, la vista
es de solo lectura y el administrador de Django los muestra sin permitir
cambios. Es lo que comprueba INT-03 al intentar alterar la auditoría con un
perfil operativo.
"""

from django.conf import settings
from django.db import models


class EventoAuditoria(models.Model):
    """Un hecho que quedó registrado y que ya no se puede cambiar."""

    class Accion(models.TextChoices):
        CREAR = "crear", "Creó"
        EDITAR = "editar", "Editó"
        ESTADO = "estado", "Cambió el estado"
        VALIDAR = "validar", "Validó"
        RECHAZAR = "rechazar", "Rechazó"
        ANULAR = "anular", "Anuló"
        PERIODO = "periodo", "Movió el período"
        PARAMETRO = "parametro", "Cambió un parámetro del cálculo"
        AJUSTE = "ajuste", "Registró un ajuste"
        REASIGNAR = "reasignar", "Reasignó"
        REVISAR = "revisar", "Marcó una alerta como revisada"
        EXPORTAR = "exportar", "Exportó un informe"

    cuando = models.DateTimeField("fecha y hora", auto_now_add=True, db_index=True)
    quien = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="eventos_auditoria", null=True, blank=True,
        verbose_name="usuario",
    )
    quien_texto = models.CharField(
        "nombre del usuario", max_length=160, blank=True,
        help_text="Copiado al ocurrir el evento, para que no cambie después.",
    )
    accion = models.CharField("acción", max_length=12, choices=Accion.choices)

    entidad = models.CharField(
        max_length=60,
        help_text="Qué tipo de registro se tocó: Delegación, Evidencia, Meta…",
    )
    objeto_id = models.PositiveIntegerField(
        "identificador del registro", null=True, blank=True,
    )
    objeto_texto = models.CharField(
        "registro", max_length=200, blank=True,
        help_text="Cómo se llamaba el registro entonces. Sobrevive a que lo borren.",
    )
    delegacion = models.ForeignKey(
        "organizacion.Delegacion", on_delete=models.PROTECT,
        related_name="eventos_auditoria", null=True, blank=True,
        verbose_name="delegación",
    )

    antes = models.TextField(
        blank=True, help_text="Cómo estaba. Vacío cuando el registro se crea.",
    )
    despues = models.TextField(
        "después", blank=True,
        help_text="Cómo quedó. Vacío cuando el registro se desactiva o se borra.",
    )
    detalle = models.TextField(
        blank=True, help_text="El motivo o la explicación, cuando la hay.",
    )
    origen = models.GenericIPAddressField(
        "origen", null=True, blank=True,
        help_text="Dirección desde la que llegó la petición.",
    )

    class Meta:
        verbose_name = "evento de auditoría"
        verbose_name_plural = "eventos de auditoría"
        ordering = ["-cuando", "-pk"]
        indexes = [
            models.Index(fields=["entidad", "objeto_id"]),
            models.Index(fields=["-cuando", "accion"]),
        ]

    def __str__(self):
        return f"{self.cuando:%d-%m-%Y %H:%M} · {self.get_accion_display()} {self.entidad}"

    # --- lo que la pantalla muestra --------------------------------------

    @property
    def usuario_visible(self):
        if self.quien_texto:
            return self.quien_texto
        if self.quien_id:
            return self.quien.get_full_name() or self.quien.get_username()
        return "el sistema"

    @property
    def registro_visible(self):
        if self.objeto_texto:
            return self.objeto_texto
        if self.objeto_id:
            return f"{self.entidad} #{self.objeto_id}"
        return self.entidad

    @property
    def cambio(self):
        """El antes y el después en una línea, para la tabla."""
        if self.antes and self.despues:
            return f"{self.antes} → {self.despues}"
        if self.despues:
            return self.despues
        if self.antes:
            return self.antes
        return self.detalle or "—"

    def motivo_bloqueo(self):
        return "La auditoría no se modifica ni se desactiva."


class AlertaRevisada(models.Model):
    """
    La marca de que alguien ya miró una alerta.

    Las alertas no se guardan: se calculan cada vez a partir del estado
    actual, porque una alerta almacenada se queda desactualizada en cuanto
    cambia lo que la originó —un compromiso vencido que se cierra dejaría un
    aviso colgando—. Lo que sí se guarda es esto: que tal persona revisó tal
    alerta en tal momento.

    El caso TAB-06 pide que «la revisión no elimine el evento original», y
    esa separación es justo lo que lo garantiza: marcar revisada escribe una
    fila aquí y no toca el compromiso, la evidencia ni el avance que
    provocaron el aviso. Si la condición sigue dándose, la alerta sigue
    existiendo; lo único que cambia es que deja de aparecer entre las
    pendientes.
    """

    clave = models.CharField(
        max_length=120, unique=True,
        help_text=(
            "Identifica la alerta: su tipo y el registro que la originó. "
            "Por ejemplo «compromiso_vencido:34»."
        ),
    )
    tipo = models.CharField(max_length=40)
    titulo = models.CharField("título", max_length=200)
    detalle = models.TextField(blank=True)
    delegacion = models.ForeignKey(
        "organizacion.Delegacion", on_delete=models.PROTECT,
        related_name="alertas_revisadas", null=True, blank=True,
        verbose_name="delegación",
    )
    quien = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="alertas_revisadas", null=True, blank=True,
        verbose_name="revisada por",
    )
    cuando = models.DateTimeField("revisada el", auto_now_add=True)
    nota = models.TextField(blank=True)

    class Meta:
        verbose_name = "alerta revisada"
        verbose_name_plural = "alertas revisadas"
        ordering = ["-cuando"]

    def __str__(self):
        return f"{self.titulo} ({self.cuando:%d-%m-%Y})"

    @property
    def usuario_visible(self):
        if self.quien_id:
            return self.quien.get_full_name() or self.quien.get_username()
        return "el sistema"
