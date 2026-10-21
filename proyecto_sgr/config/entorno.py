"""
Lectura de variables de entorno y del archivo .env.

Se implementa aquí para no añadir dependencias externas al proyecto. Las
variables del sistema tienen prioridad sobre el archivo .env, de modo que en
AWS basta con definirlas en el servicio sin tocar ningún archivo.
"""

from pathlib import Path


def cargar_env(ruta: Path) -> None:
    """Carga el archivo .env en os.environ sin pisar lo que ya exista."""
    import os

    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        os.environ.setdefault(clave.strip(), valor.strip())


def texto(clave: str, defecto: str = "") -> str:
    import os

    return os.environ.get(clave, defecto)


def booleano(clave: str, defecto: bool = False) -> bool:
    import os

    valor = os.environ.get(clave)
    if valor is None:
        return defecto
    return valor.strip().lower() in {"1", "true", "on", "si", "sí", "yes"}


def lista(clave: str, defecto: str = "") -> list:
    import os

    crudo = os.environ.get(clave, defecto)
    return [x.strip() for x in crudo.split(",") if x.strip()]
