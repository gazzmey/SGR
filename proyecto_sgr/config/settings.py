"""
Configuración del Sistema de Gestión de Resultados (SGR).

Proyecto Integrado · segunda entrega. Parte de la Unidad 2 de Back End y le
suma las pantallas propias: los seis mantenedores, el acceso con recuperación
de contraseña y el ingreso de atención ciudadana.

La aplicación se conecta mediante mysqlclient. Las credenciales nunca se
escriben en este archivo: se leen de variables de entorno o del archivo .env
local, que está excluido del control de versiones.

Sobre el motor: Django usa el backend ``django.db.backends.mysql`` tanto para
MySQL como para MariaDB, y mysqlclient habla el mismo protocolo con los dos. El
proyecto se desarrolló contra MariaDB y funciona sin cambiar una línea sobre
MySQL 8: solo cambia a qué servidor apuntan las variables de entorno.
"""

from pathlib import Path

from .entorno import booleano, cargar_env, lista, texto

BASE_DIR = Path(__file__).resolve().parent.parent

cargar_env(BASE_DIR / ".env")

SECRET_KEY = texto("SGR_SECRET_KEY", "clave-solo-para-desarrollo-local")

DEBUG = booleano("SGR_DEBUG", True)

ALLOWED_HOSTS = lista("SGR_ALLOWED_HOSTS", "127.0.0.1,localhost")

# Necesario desde Django 4 para los formularios cuando la aplicación se
# publica detrás de un dominio o IP pública.
CSRF_TRUSTED_ORIGINS = [
    f"http://{host}" for host in ALLOWED_HOSTS if host not in {"*"}
] + [
    f"https://{host}" for host in ALLOWED_HOSTS if host not in {"*"}
]

# --- endurecimiento para HTTPS ------------------------------------------
#
# «manage.py check --deploy» reclama estas cuatro, y tiene razón: sin ellas
# la cookie de sesión y el testigo CSRF viajan por una conexión que alguien
# puede leer. Pero encenderlas sobre HTTP **rompe el inicio de sesión**: el
# navegador deja de mandar una cookie marcada como segura por un canal que
# no lo es, y la persona queda sin poder entrar sin ningún mensaje que lo
# explique.
#
# Por eso van detrás de una variable, apagadas por omisión. El día que el
# servidor tenga certificado se define SGR_HTTPS=1 y las cuatro se encienden
# juntas, que es como corresponde: media medida —cookie segura sin
# redirección, por ejemplo— deja agujeros y además confunde.
#
# Mientras SGR_HTTPS no esté definida, «check --deploy» va a seguir avisando.
# Ese aviso es correcto y se deja a la vista: describe el riesgo real de
# publicar sobre HTTP, y taparlo sería mentirle a quien revise el proyecto.
HTTPS = booleano("SGR_HTTPS", booleano("SGR_COOKIES_SEGURAS", False))

SECURE_SSL_REDIRECT = HTTPS
SECURE_HSTS_SECONDS = 31536000 if HTTPS else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = HTTPS
SECURE_HSTS_PRELOAD = False

# Detrás de Nginx, Django ve una conexión HTTP aunque el visitante llegue por
# HTTPS. Sin esto, SECURE_SSL_REDIRECT entra en un bucle de redirecciones.
if HTTPS:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Aplicaciones del SGR
    "comun",
    "organizacion",
    "catalogos",
    "atencion",
    "cuenta",
    "gestion",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Sirve los archivos estáticos en el servidor AWS.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                # Deja la delegación activa y el perfil al alcance de la
                # plantilla base, que los muestra en la cabecera.
                "comun.contexto.sesion_sgr",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# --- Base de datos -------------------------------------------------------
# Backend mysql de Django a través de mysqlclient. Sirve igual para MariaDB y
# para MySQL 8; los valores provienen del entorno.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": texto("SGR_DB_NAME", "sgr"),
        "USER": texto("SGR_DB_USER", "sgr_app"),
        "PASSWORD": texto("SGR_DB_PASSWORD", ""),
        "HOST": texto("SGR_DB_HOST", "127.0.0.1"),
        "PORT": texto("SGR_DB_PORT", "3306"),
        "OPTIONS": {
            "charset": "utf8mb4",
            # Hace que el motor rechace datos inválidos en vez de truncarlos.
            # STRICT_TRANS_TABLES existe en MariaDB y en MySQL por igual.
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-cl"
TIME_ZONE = "America/Santiago"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Acceso --------------------------------------------------------------
# El login propio reemplaza al del administrador: la gente entra con su
# correo institucional, no con un nombre de usuario.
LOGIN_URL = "cuenta:login"
LOGIN_REDIRECT_URL = "comun:panel"
LOGOUT_REDIRECT_URL = "cuenta:login"

# --- Correo --------------------------------------------------------------
# En desarrollo el código de recuperación se imprime en la consola donde
# corre runserver: así el recorrido completo se puede probar sin servidor de
# correo. En AWS se define SGR_EMAIL_BACKEND con el SMTP que corresponda y el
# mismo código se envía de verdad, sin tocar una línea.
EMAIL_BACKEND = texto(
    "SGR_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = texto("SGR_EMAIL_HOST", "")
EMAIL_PORT = int(texto("SGR_EMAIL_PORT", "587") or 587)
EMAIL_HOST_USER = texto("SGR_EMAIL_USER", "")
EMAIL_HOST_PASSWORD = texto("SGR_EMAIL_PASSWORD", "")
EMAIL_USE_TLS = booleano("SGR_EMAIL_TLS", True)
DEFAULT_FROM_EMAIL = texto("SGR_EMAIL_FROM", "sgr@ejemplo.cl")

# Muestra el código en pantalla además de enviarlo por correo. Sirve para la
# demostración y para las pruebas; en producción se deja en off.
SGR_MOSTRAR_CODIGO = booleano("SGR_MOSTRAR_CODIGO", DEBUG)

# --- Seguridad en producción ---------------------------------------------
# Solo se aplican cuando DEBUG está apagado, para no estorbar en local.
if not DEBUG:
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = False  # el token viaja en formularios, no por JS
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
    # Las cookies seguras siguen la misma variable que el resto del
    # endurecimiento HTTPS, definida más arriba. Tenerlas en su propia
    # variable dejaba encender media protección —cookie segura sin
    # redirección— y además hacía que dos ajustes del mismo archivo se
    # pisaran entre sí según cuál quedara más abajo.
    SESSION_COOKIE_SECURE = HTTPS
    CSRF_COOKIE_SECURE = HTTPS

MESSAGE_STORAGE = "django.contrib.messages.storage.session.SessionStorage"
