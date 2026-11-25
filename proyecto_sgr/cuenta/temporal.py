"""
Contraseñas temporales.

El administrador no inventa la contraseña de nadie: el sistema genera una al
azar, se muestra una sola vez para entregarla por un medio seguro, y la
persona tiene que cambiarla en su primer ingreso. En la base queda solo su
hash, como cualquier otra.
"""

import secrets

# Sin letras ni números que se confunden al dictarlos o copiarlos: 0/O, 1/l/I.
_LETRAS = "abcdefghjkmnpqrstuvwxyz"
_MAYUSCULAS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_NUMEROS = "23456789"


def generar():
    """Tres bloques de cuatro, con mayúsculas, minúsculas y números: Kq7m-Pw3x-Rt9z."""
    bloques = []
    for _ in range(3):
        bloque = [secrets.choice(_MAYUSCULAS), secrets.choice(_LETRAS),
                  secrets.choice(_NUMEROS), secrets.choice(_LETRAS)]
        bloques.append("".join(bloque))
    return "-".join(bloques)


def emitir(usuario, perfil):
    """Le pone una contraseña temporal y marca que debe cambiarla. Devuelve la contraseña."""
    clave = generar()
    usuario.set_password(clave)
    usuario.save(update_fields=["password"])
    perfil.debe_cambiar_clave = True
    perfil.save(update_fields=["debe_cambiar_clave"])
    return clave
