"""
Cambia la contraseña de las cuentas de prueba sin escribirla en ningún archivo.

    python manage.py claves_de_prueba

Pide la contraseña dos veces sin mostrarla en pantalla y se la asigna a las
cuentas ficticias del dominio ``ejemplo.cl`` (incluidas ``consulta@ejemplo.cl``
y ``gestion@ejemplo.cl``). Con ``--solo`` se limita a algunas:

    python manage.py claves_de_prueba --solo consulta@ejemplo.cl gestion@ejemplo.cl

Existe para el servidor de AWS: las cuentas de la demostración se crearon con
una clave que está escrita en el repositorio, y la Evaluación 3 pide que las
credenciales se entreguen fuera de él. La contraseña pasa por
``set_password()`` —en la base queda solo el hash— y por los validadores de
``AUTH_PASSWORD_VALIDATORS``.
"""

import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Cambia la contraseña de las cuentas de prueba (dominio ejemplo.cl)."

    def add_arguments(self, parser):
        parser.add_argument("--solo", nargs="+", metavar="CORREO",
                            help="Solo estas cuentas.")

    def handle(self, *args, **opciones):
        Usuario = get_user_model()
        cuentas = Usuario.objects.filter(email__iendswith="@ejemplo.cl")
        if opciones["solo"]:
            cuentas = cuentas.filter(email__in=opciones["solo"])
        cuentas = list(cuentas.order_by("email"))
        if not cuentas:
            raise CommandError("No hay cuentas de prueba que cambiar.")

        self.stdout.write("Se cambiará la contraseña de %d cuentas:" % len(cuentas))
        for cuenta in cuentas:
            self.stdout.write("  " + cuenta.email)

        clave = getpass.getpass("Contraseña nueva: ")
        if clave != getpass.getpass("Repítela: "):
            raise CommandError("Las dos contraseñas no coinciden. No se cambió nada.")
        try:
            validate_password(clave, cuentas[0])
        except ValidationError as error:
            raise CommandError(" ".join(error.messages))

        for cuenta in cuentas:
            cuenta.set_password(clave)
            cuenta.save(update_fields=["password"])
        self.stdout.write(self.style.SUCCESS(
            "Listo. Entrega la contraseña por el medio de evaluación, no por el repositorio."))
