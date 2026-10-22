# Sistema de Gestión de Resultados (SGR) — Proyecto Integrado, Segunda Entrega

Aplicación Django conectada a MariaDB para las delegaciones municipales de
La Serena. Esta entrega incorpora las **pantallas propias** del sistema: el
acceso con recuperación de contraseña, los seis mantenedores y el ingreso de
atención ciudadana. Todo lo que se ve guarda en la base de datos; el
administrador de Django se conserva, pero ya no es la única interfaz.



---

## 1. Integrantes y aportes


| Integrante | Aporte en esta entrega |
|---|---|
| José Alday | Mantenedores de Delegaciones y Roles: formularios, vistas, rutas y validaciones. Tabla de permisos (`comun/permisos.py`) y el mixin que la aplica en el servidor. Configuración de `DATABASES` y del despliegue. |
| José Briceño | Mantenedor de Usuarios: formulario sobre dos modelos (`User` + `PerfilUsuario`) en una transacción, delegaciones autorizadas y la regla que protege al último administrador. Contexto de delegación activa en la sesión. |
| Adán Cuello | Acceso y recuperación de contraseña en cuatro pasos: modelo `CodigoRecuperacion`, vistas del recorrido, envío por correo y las tres reglas del código. Comando de carga de datos ficticios. |
| Carlos Silva | Mantenedores de Ítems, Tipos de atención y Subatenciones, con la regla del 100 % de ponderadores. Ingreso de atención ciudadana: validación de RUT, selector dependiente y documento obligatorio. Documentación. |

Los cuatro revisaron el proyecto completo y pueden explicar la configuración
de `DATABASES`, los modelos, las migraciones, las relaciones, la
personalización del administrador y —nuevo en esta entrega— cómo una vista de
clase se convierte en seis mantenedores distintos.

---

## 2. Las pantallas

| # | Pantalla | Dirección | Qué hace |
|---|---|---|---|
| 1 | Iniciar sesión | `/cuenta/ingresar/` | Entrada con el correo institucional. |
| 2 | Recuperar contraseña | `/cuenta/recuperar/` | Paso 1: pide el correo y envía un código. |
| 3 | Validar código | `/cuenta/recuperar/codigo/` | Paso 3: los seis dígitos, con vigencia e intentos. |
| 4 | Crear contraseña | `/cuenta/recuperar/clave/` | Paso 4: la contraseña nueva, con los validadores de Django. |
| 5 | Mi panel | `/` | Entrada al sistema; muestra solo los módulos del rol. |
| 6 | Delegaciones | `/gestion/delegaciones/` | Mantenedor completo. |
| 7 | Roles y permisos | `/gestion/roles/` | Mantenedor completo, con la tabla de permisos. |
| 8 | Usuarios | `/gestion/usuarios/` | Mantenedor completo sobre `User` + `PerfilUsuario`. |
| 9 | Ítems y metas | `/catalogo/items/` | Mantenedor completo, con la regla del 100 %. |
| 10 | Tipos de atención | `/catalogo/tipos-atencion/` | Mantenedor completo. |
| 11 | Subatenciones | `/catalogo/subatenciones/` | Mantenedor completo, dependiente del tipo. |
| 12 | Ingreso de atención | `/atencion/ingreso/` | Registro de atención ciudadana. |
| 13 | Atenciones registradas | `/atencion/registradas/` | Consulta de lo registrado en la delegación. |

Las once que exige la entrega son las primeras once; las dos últimas
completan el módulo de atención ciudadana.

### Lo que se construyó después de las once

La entrega pedía once pantallas. Se agregaron las siguientes para que el
sistema funcione de punta a punta y no solo en las pantallas evaluadas: un
registro que no puede validarse, o un resultado que nadie calcula, dejan el
recorrido cortado a la mitad.

| Pantalla | Dirección | Qué hace |
|---|---|---|
| Períodos | `/periodo/periodos/` | Mantenedor, más el ciclo abrir → cerrar → reabrir. |
| Cargos | `/periodo/cargos/` | Mantenedor del cargo que decide con qué metas se mide a cada persona. |
| Metas y ponderadores | `/periodo/metas/` | La meta por período, cargo e ítem, con la regla del 100 %. |
| Reglas de cálculo | `/periodo/reglas/` | Tope, umbrales y convención de días, configurables sin tocar código. |
| Mis actividades | `/periodo/actividades/` | Registro, listado y ficha de lo que cada persona hizo. |
| Validar evidencias | `/periodo/validar/` | La cola del verificador: aprobar, rechazar con motivo o anular. |
| Agenda de compromisos | `/periodo/agenda/` | La agenda colectiva, con plazos, estados, reasignación e historial. |
| Mi resultado | `/periodo/mi-resultado/` | Cumplimiento por ítem, aporte ponderado, avance esperado y semáforo. |
| Tablero de delegación | `/periodo/tablero/` | El resultado de cada persona de la delegación y el indicador de la agenda. |
| Alertas | `/periodo/alertas/` | Las cinco condiciones que requieren atención, con sus umbrales a la vista. |
| Auditoría | `/periodo/auditoria/` | Historial de operaciones críticas. Solo listado: no hay creación, edición ni borrado. |
| Informes | `/periodo/informes/` | Cuatro informes consolidados con filtros, y exportación a Excel, CSV y PDF. |

La cadena que forman, y que es la razón del orden en que se construyeron:

```
período → metas y ponderadores → actividad → evidencia → validación
       → cálculo → resultado y tablero
                 ↑
         agenda de compromisos
```

Cada mantenedor tiene además sus pantallas de creación, edición y ficha, con
las mismas cinco rutas en los seis casos:

```
''              listado con búsqueda, filtros, orden, paginador y exportación
'nueva/'        formulario de creación
'<pk>/'         ficha de consulta
'<pk>/editar/'  formulario de edición
'<pk>/estado/'  activar o desactivar (solo POST)
```

---

## 3. Un patrón, seis mantenedores

Los seis mantenedores hacen lo mismo: listar con búsqueda, filtros, orden y
paginador; exportar lo que está filtrado; crear, editar y consultar; activar y
desactivar respetando las relaciones protegidas. Ese comportamiento está
escrito **una sola vez**, en `comun/mantenedor.py`, y cada entidad declara qué
columnas tiene y por dónde se busca:

```python
class DelegacionesLista(ListaMantenedor):
    model = Delegacion
    permiso = P.GESTIONAR_USUARIO
    busca = ["codigo", "nombre", "comuna", "direccion"]
    filtros = [Filtro("zona", "Zona", Delegacion.Zona.choices), filtro_estado(femenino=True)]
    columnas = [Columna("codigo", "Código", clase="mono"), ...]
```

Una sola plantilla dibuja los seis listados
(`templates/comun/mantenedor_lista.html`) y otra los doce formularios de
creación y edición. Si hubiera que cambiar cómo funciona el paginador, se
cambia en un lugar y los seis cambian con él.

### El estado del listado vive en la dirección

```
?q=companias&zona=Rural&estado=activos&orden=nombre&dir=desc&p=2&tam=25
```

Son los mismos parámetros que usaba la maqueta en JavaScript, ahora resueltos
por el servidor. Por eso un listado filtrado se puede compartir, marcar como
favorito y recargar sin perder nada, y por eso la exportación a Excel entrega
exactamente lo que se ve en pantalla: usa el mismo `get_queryset()`.

### La búsqueda sin tildes la hace la base de datos

Buscar `companias` encuentra «Las Compañías». No hay código que quite tildes:
las tablas se crean con la colación `utf8mb4_unicode_ci`, que compara
ignorando mayúsculas y acentos, así que `nombre__icontains="companias"` ya
encuentra el registro. Por eso la colación de §5.2 no es un detalle: con otra
colación, esa búsqueda no encontraría nada.

---

## 4. Modelos y relaciones

| Aplicación | Modelo | Qué guarda |
|---|---|---|
| `organizacion` | `Delegacion` | Unidad territorial: código, nombre, zona, dirección, teléfono, horario, estado. |
| `organizacion` | `Rol` | Función: código, nombre, descripción, alcance y **lista de permisos**. |
| `organizacion` | `PerfilUsuario` | Datos del SGR de una persona: código, cargo, rol, delegación base y delegaciones autorizadas. |
| `catalogos` | `Item` | Elemento medible: área, unidad de medida, meta del período y ponderador. |
| `catalogos` | `TipoAtencion` | Clasificación general de una atención, con su área. |
| `catalogos` | `SubAtencion` | Detalle de un tipo, y si **exige documento de respaldo**. |
| `atencion` | `Solicitante` | Persona que acude: RUT validado, nombre, teléfono, territorio. |
| `atencion` | `Atencion` | La atención entregada: solicitante, subatención, delegación, funcionario, detalle y respaldo. |
| `cuenta` | `CodigoRecuperacion` | Código de seis dígitos de un solo uso, con vigencia e intentos. |

### Relaciones y estrategia de eliminación

| Relación | Tipo | Al eliminar |
|---|---|---|
| `PerfilUsuario` → `User` | Uno a uno | `CASCADE`: el perfil no tiene sentido sin su usuario. |
| `PerfilUsuario` → `Rol` | Muchos a uno | `PROTECT`: impide borrar un rol asignado. |
| `PerfilUsuario` → `Delegacion` | Muchos a uno | `PROTECT`: impide borrar una delegación con personal. |
| `PerfilUsuario` ↔ `Delegacion` | Muchos a muchos | Delegaciones autorizadas; se agregó en esta entrega. |
| `SubAtencion` → `TipoAtencion` | Muchos a uno | `PROTECT`: impide borrar un tipo con subatenciones. |
| `Atencion` → `Solicitante` | Muchos a uno | `PROTECT`: la atención conserva a quién se atendió. |
| `Atencion` → `SubAtencion` | Muchos a uno | `PROTECT`: conserva qué se resolvió, aunque después se desactive. |
| `Atencion` → `Delegacion` | Muchos a uno | `PROTECT`: conserva dónde se atendió. |
| `Atencion` → `User` | Muchos a uno | `PROTECT`: conserva quién atendió. |
| `CodigoRecuperacion` → `User` | Muchos a uno | `CASCADE`: sin la cuenta, el código no sirve de nada. |

**`PROTECT` en la pantalla.** Que la base bloquee el borrado está bien, pero un
error de base de datos no es un mensaje para un funcionario. Cada modelo tiene
un método `motivo_bloqueo()` que explica en palabras por qué no se puede
desactivar, y el mantenedor lo consulta **antes** de intentarlo:

```python
def motivo_bloqueo(self):
    cuantos = self.perfiles.count()
    if cuantos:
        return (f"Tiene {cuantos} perfiles de usuario asignados. "
                "Reasigna esos usuarios a otra delegación antes de desactivarla.")
    return ""
```

Ningún registro se borra: se desactiva. Así los informes de períodos cerrados
siguen cuadrando y el historial conserva sus referencias.

### Compatibilidad con la entrega de Back End, Unidad 2

Esta entrega trabaja sobre una **copia** de la base de datos de la Unidad 2 y
sus migraciones son **aditivas**: agregan columnas y una tabla intermedia, y no
quitan ni renombran nada. En particular, `PerfilUsuario.delegacion` se conserva
tal cual y `delegaciones_autorizadas` se **suma**; reemplazar el campo habría
invalidado la entrega anterior, que sigue leyendo esa columna.

Dos migraciones merecen una mirada:

- `organizacion/0002_entrega2.py` agrega el código correlativo a `Rol` y a
  `PerfilUsuario`. No se puede agregar una columna `unique` con datos ya
  cargados, así que la migración hace tres pasos: agrega la columna con un
  valor por omisión, **numera las filas existentes** con `RunPython`, y solo
  entonces le aplica la restricción.
- `catalogos/0003_codigos_de_ejemplo.py` solo cambia textos de ayuda. No
  ejecuta ninguna sentencia sobre las tablas; existe porque Django compara el
  estado de los modelos con el de las migraciones y avisa si no coinciden.

---

## 5. Instalación y ejecución

### 5.1 Preparar el entorno

```bash
python -m venv venv
source venv/bin/activate          # en Windows: venv\Scripts\activate
pip install -r requirements.txt
```

`mysqlclient` se compila al instalarse y necesita las cabeceras de desarrollo
del conector de C. Si la instalación falla:

- **Amazon Linux 2023 y Fedora:** `sudo dnf install python3-devel mariadb-connector-c-devel gcc pkgconf-pkg-config`
- **Ubuntu y Debian:** `sudo apt install python3-dev libmariadb-dev build-essential pkg-config`
- **macOS:** `brew install mariadb-connector-c pkg-config`
- **Windows:** usar una distribución precompilada del paquete o instalar el
  conector de C de MariaDB.

### 5.2 Crear la base de datos

```sql
CREATE DATABASE sgr CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'sgr_app'@'localhost' IDENTIFIED BY 'la-clave-que-elijas';
GRANT ALL PRIVILEGES ON sgr.* TO 'sgr_app'@'localhost';
FLUSH PRIVILEGES;
```

La colación `utf8mb4_unicode_ci` es la que hace que la búsqueda de los
listados ignore mayúsculas y tildes (§3).

### 5.3 Configurar las credenciales

Las credenciales no están escritas en el código. `config/settings.py` las lee
de variables de entorno y, si existe, de un archivo `.env` en la raíz. Las
variables del sistema tienen prioridad, de modo que en el servidor basta con
definirlas allí.

```bash
cp .env.example .env
```

| Variable | Para qué sirve |
|---|---|
| `SGR_SECRET_KEY` | Clave criptográfica de Django. Distinta en cada entorno. |
| `SGR_DEBUG` | `on` en desarrollo, `off` en el servidor. |
| `SGR_ALLOWED_HOSTS` | Dominios autorizados, separados por coma. |
| `SGR_DB_NAME` · `SGR_DB_USER` · `SGR_DB_PASSWORD` | Conexión a la base. |
| `SGR_DB_HOST` · `SGR_DB_PORT` | `127.0.0.1` y `3306` en local. |
| `SGR_EMAIL_BACKEND` y el resto de `SGR_EMAIL_*` | Envío del código de recuperación. Sin definir, el código se imprime en la consola de `runserver`. |
| `SGR_MOSTRAR_CODIGO` | Muestra el código en pantalla para la demostración. Sigue a `SGR_DEBUG`; en el servidor queda apagado. |
| `SGR_HTTPS` | `on` cuando el servidor tenga certificado. Enciende juntas la redirección a HTTPS, HSTS y las cookies seguras. Sobre HTTP tiene que quedar apagada: una cookie segura por un canal inseguro no se envía y nadie puede iniciar sesión. |
| `SGR_COOKIES_SEGURAS` | Nombre anterior de `SGR_HTTPS`. Se sigue aceptando. |

El archivo `.env` está excluido en `.gitignore` y **no** se incluye en el
archivo comprimido de la entrega. El repositorio solo contiene `.env.example`,
sin valores reales.

Para generar una clave propia:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

### 5.4 Comprobar, migrar y cargar datos

```bash
python manage.py check
python manage.py makemigrations --check --dry-run   # no debe detectar cambios
python manage.py migrate
python manage.py cargar_datos_demo
python manage.py runserver
```

`makemigrations --check --dry-run` no modifica nada: solo avisa si los modelos
y las migraciones dejaron de coincidir. Si informa cambios, algo quedó sin
migrar y hay que revisarlo antes de seguir.

El sistema queda en **http://127.0.0.1:8000/** y el administrador de Django,
en `/admin/`.

### 5.5 Sobre la base de la entrega anterior

Si se parte de una copia de la base de la Unidad 2, `migrate` aplica solo las
migraciones nuevas y conserva los datos. `cargar_datos_demo` sobrescribe los
registros que comparten código (`DEL-01`, `ITM-01`…) con los de la maqueta; si
se quiere conservar los de la Unidad 2, no hay que ejecutarlo.

---

## 6. Permisos

El rol guarda su propia lista de acciones en un `JSONField`, y el mantenedor
de Roles las muestra como casillas agrupadas. Son trece:

| Grupo | Acciones |
|---|---|
| Mi gestión | registrar actividades · adjuntar evidencias · registrar atención ciudadana |
| Supervisión | validar evidencias · ver el tablero · reasignar compromisos · registrar ajustes · ver informes |
| Configuración | configurar períodos · definir metas y ponderadores · gestionar catálogos |
| Administración | gestionar usuarios y roles · consultar la auditoría |

**Por qué no se usan los permisos de Django.** `django.contrib.auth` trae
permisos por modelo (add / change / delete / view), que sirven para el
administrador y ahí se usan. El SGR necesita permisos por *acción de negocio*
—validar una evidencia, configurar un período— que no calzan uno a uno con un
modelo.

**El alcance no es lo mismo que el permiso.** El permiso dice *qué* puede
hacer; el alcance, *sobre qué delegaciones*: su delegación, varias o todas. Un
rol puede validar evidencias solo en su delegación o en todas, con el mismo
permiso marcado.

**La comprobación es del servidor.** Que el menú esconda una opción es
cortesía, no seguridad. Cada vista lleva el mixin `RequierePermiso`, que
rechaza la petición antes de entrar en la vista; escribir la dirección a mano
devuelve 403.

---

## 7. Datos de prueba

`cargar_datos_demo` carga los mismos datos de la maqueta aprobada, para que
las pantallas en Django muestren lo que se revisó. Se puede ejecutar varias
veces sin duplicar nada.

| Módulo | Registros |
|---|---|
| Delegaciones | 18 (16 activas; `DEL-17` y `DEL-18` inactivas) |
| Roles | 6 (`ROL-06` inactivo) |
| Usuarios con perfil | 15 (`USR-08` inactivo) |
| Ítems | 10 · los ponderadores activos suman 100 % |
| Tipos de atención | 8 |
| Subatenciones | 24 (22 activas; 11 exigen documento de respaldo) |
| Solicitantes | 5, con RUT ficticio de dígito verificador válido |
| Atenciones | 6 repartidas en cuatro delegaciones |
| Cargos | 6 |
| Períodos | 1 abierto, con fechas que contienen el día de hoy |
| Metas y ponderadores | 13, y los de cada cargo suman 100 % |
| Reglas de cálculo | 1 general, **sin aprobar**: el sistema la aplica y la rotula como propuesta |
| Actividades y evidencias | 111 cada una: 108 aprobadas, 2 por validar y 1 rechazada con su motivo |
| Compromisos de la agenda | 17; los 10 vigentes de `DEL-01` reproducen el lote CAL-C del plan: 8 realizados, 1 pendiente y 1 en proceso, o sea 80 % realizado |

**Todos los datos son ficticios.** No hay nombres, correos, RUT ni
antecedentes de personas reales: los correos usan el dominio reservado
`ejemplo.cl` y los RUT son números con dígito verificador correcto que no
corresponden a nadie. Los sectores de La Serena se usan como referencia
territorial.

### Cuentas para la revisión

| Cuenta | Contraseña | Rol | Para qué sirve |
|---|---|---|---|
| `felipe.araya@ejemplo.cl` | `Demo.Sgr2026` | Administrador | Los seis mantenedores. |
| `pablo.fuentes@ejemplo.cl` | `Demo.Sgr2026` | Verificador | Validar evidencias y compromisos; sin acceso a los mantenedores. |
| `marcela.rios@ejemplo.cl` | `Demo.Sgr2026` | Funcionario | Registrar actividades, atención ciudadana y compromisos. |
| `valentina.cortes@ejemplo.cl` | `Demo.Sgr2026` | Coordinador del sistema | Períodos, metas y reglas de cálculo; alcance en todas las delegaciones. |
| `soledad.guerrero@ejemplo.cl` | `Demo.Sgr2026` | Delegado o jefatura | La única que puede reasignar compromisos de la agenda. |
| `revisor` | `Sgr.Revision2026` | Superusuario | Administrador de Django. |

Son cuentas ficticias de un sistema de prueba y existen solo para la revisión
académica. Para usar otras, se definen `SGR_DEMO_PASSWORD`, `SGR_ADMIN_USER`,
`SGR_ADMIN_PASSWORD` y `SGR_ADMIN_EMAIL` antes de ejecutar el comando.

En una instalación real este comando no se ejecuta: las cuentas se crean desde
el mantenedor de Usuarios y nacen **sin contraseña utilizable**, de modo que
cada persona define la suya con el enlace de recuperación. Así nadie —tampoco
quien administra— llega a conocerla.

---

## 8. Seguridad

| Qué | Cómo se resolvió |
|---|---|
| Contraseñas | `set_password()`: en la base queda un hash con sal, nunca la contraseña. Los validadores de `AUTH_PASSWORD_VALIDATORS` se aplican en el servidor. |
| Formularios | Todos llevan `{% csrf_token %}`. Cambiar el estado de un registro es `POST`, no un enlace: un enlace quedaría en el historial y bastaría con abrirlo. |
| Permisos | Mixin `RequierePermiso` antes de la vista, no dentro. Esconder el menú es cortesía. |
| Delegación activa | Vive en la **sesión del servidor**, y cada vez se vuelve a comprobar contra las delegaciones que el perfil autoriza. Enviar otro identificador a mano no sirve. |
| Atención ciudadana | La delegación y el funcionario no viajan en el formulario: los pone la vista. Si viajaran, se podría registrar a nombre de otra persona. |
| Recuperación | El sistema responde lo mismo exista o no el correo, para que nadie pueda averiguar qué direcciones están registradas. El código vence a los 10 minutos, sirve una vez y admite 3 intentos; se compara con `secrets.compare_digest`. |
| Códigos en el administrador | Se pueden consultar, pero **no se muestran los dígitos**: quien administra no necesita verlos, y si pudiera, podría cambiar la contraseña de cualquiera. |
| Redirecciones | Todo destino de vuelta que llega en la petición —`?volver=`, campos ocultos— pasa por `comun/navegacion.py`, que solo acepta rutas internas con la misma función que protege el `?next=` del `login` de Django. Sin eso, un enlace legítimo del sistema puede terminar en una pantalla de contraseña falsa: dominio correcto, ruta correcta, sesión abierta. |
| Secretos | Ninguna credencial en el código ni en el repositorio. `.env` excluido en `.gitignore`. |
| Producción | Con `SGR_DEBUG=off` se activan `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS=DENY`, `SECURE_REFERRER_POLICY` y las cookies `HttpOnly`; con HTTPS, además las cookies seguras. |

---

## 9. Despliegue en AWS

**Dirección de la aplicación:** http://35.170.29.164/

**Administrador:** http://35.170.29.164/admin/

El despliegue usa una instancia EC2 con Amazon Linux 2023 y MariaDB para los
datos. Python 3.12 en entorno virtual, porque el intérprete del sistema es 3.9
y Django 5 exige 3.10 o superior. Gunicorn ejecuta la aplicación bajo systemd
con tres trabajadores, Nginx recibe las peticiones del exterior en el puerto 80
y las pasa a `127.0.0.1:8000`, y whitenoise sirve los archivos estáticos
recolectados con `collectstatic`. Las credenciales se definen en un `.env` con
permisos 600, fuera del repositorio. Las del correo (`SGR_EMAIL_*`) van aparte,
en `/etc/systemd/system/sgr.service.d/correo.conf`, también con permisos 600.

La instancia tiene una IP elástica para que la dirección no cambie al
reiniciarla. El sistema se sirve por HTTP: el endurecimiento de HTTPS
—redirección forzada, HSTS y cookies seguras— está implementado detrás de la
variable `SGR_HTTPS`, apagada mientras no haya certificado, porque encenderla
sobre HTTP impediría iniciar sesión.

### Cómo se publica un cambio

GitHub es la copia oficial del código. En el servidor no se edita nada a mano:
el cambio se sube a la rama `main` y se publica con `desplegar.sh`, que está en
la raíz del repositorio. El servidor tiene un clon en `~/SGR` y la aplicación
corre desde `~/proyecto_integrado`; el script copia a la aplicación solo los
archivos de `proyecto_sgr/` que cambiaron, sin tocar el entorno virtual, el
`.env` ni los archivos recolectados.

```bash
bash ~/SGR/desplegar.sh revisar   # muestra qué cambiaría, sin tocar la aplicación
bash ~/SGR/desplegar.sh           # publica la última versión de main
bash ~/SGR/desplegar.sh volver    # restaura el código del último respaldo
```

Antes de copiar, el script revisa la versión nueva con `manage.py check` y
confirma que no falten migraciones; si algo falla, se detiene sin haber copiado
nada. Después pide confirmación, respalda el código y la base de datos en
`~/respaldos` (guarda los diez últimos), copia, aplica las migraciones,
recolecta los estáticos, reinicia el servicio y comprueba que la página
responda. `requirements.txt` solo se reinstala cuando cambia.

Preparación del servidor, una sola vez:

```bash
sudo dnf install -y git
git clone https://github.com/gazzmey/SGR.git ~/SGR
```

### Archivos de las evidencias

Los archivos que se adjuntan a las evidencias se guardan en `media/` dentro de
la aplicación (o en `SGR_MEDIA_ROOT`, si se define), con un nombre que genera
el sistema. Esa carpeta no tiene dirección pública: Nginx no la sirve y Django
no define `MEDIA_URL`. Cada archivo se entrega por `/periodo/evidencias/<id>/archivo/`,
que comprueba que quien lo pide sea el autor de la actividad o un verificador
de esa delegación. Los formatos y el tamaño máximo se configuran con
`SGR_EVIDENCIA_FORMATOS` y `SGR_EVIDENCIA_MAX_MB` (por omisión PDF, JPG, JPEG y
PNG, hasta 5 MB).

Nginx rechaza por omisión cualquier envío de más de 1 MB antes de que llegue a
Django, así que el servidor necesita este ajuste, una sola vez:

```bash
echo 'client_max_body_size 20m;' | sudo tee /etc/nginx/conf.d/sgr_subidas.conf
sudo nginx -t && sudo systemctl reload nginx
```

El límite de Nginx queda holgado a propósito: el de 5 MB lo aplica Django, que
es el que puede explicarle a la persona por qué se rechazó su archivo.

---

## 10. Limitaciones conocidas

- **Un rol por usuario.** La maqueta contemplaba personas con dos roles —quien
  verifica y a la vez conduce la delegación—. `PerfilUsuario.rol` es una clave
  foránea, tal como quedó en la Unidad 2, así que `cargar_datos_demo` asigna el
  primero y anota el segundo en el cargo. Convertirlo en una relación de muchos
  a muchos cambiaría el esquema que la entrega anterior ya usa.
- **El Administrador no registra atenciones.** Según la tabla de permisos
  aprobada, `registrar_atencion` es del rol Funcionario. No es un error: si se
  quisiera que el Administrador también pudiera, se marca la casilla en el
  mantenedor de Roles, sin tocar código.
- **Los archivos de las evidencias no entran en el respaldo del despliegue.**
  `desplegar.sh` respalda el código y la base, pero no `media/`: el despliegue
  no toca esos archivos y el sistema nunca los modifica ni los borra. Para
  respaldarlos aparte basta con
  `tar -czf ~/respaldos/archivos_$(date +%F).tar.gz -C ~/proyecto_integrado media`.
  Las evidencias registradas antes de HU-09 no tienen archivo: conservan solo
  su referencia y siguen siendo válidas.
- **Sin bloqueo por intentos fallidos.** La maqueta mostraba ese estado de
  pantalla. Hacerlo bien exige registrar los intentos por cuenta y por origen,
  y no está en esta entrega.
- **Los territorios son una lista fija** en el formulario de atención, a falta
  de un mantenedor de territorios.
- **Los ajustes —bonificaciones y penalizaciones— no están implementados.**
  No es falta de tiempo: el caso TAB-04 del plan exige una «regla de ajuste
  aprobada y parametrizada», y esa regla no existe. Nadie definió qué causales
  bonifican, cuánto ni con qué tope. Implementarlo obligaría a inventar la
  norma en vez de implementarla, y el resultado sería incomprobable: no habría
  fórmula aprobada contra la cual comparar. El permiso `registrar_ajuste` y la
  acción de auditoría ya existen, de modo que el día que la regla se apruebe la
  funcionalidad se enchufa sin rehacer nada.
- **Las observaciones compartidas sobre un registro** (RF-035) tampoco. Hay
  observaciones dentro del historial del compromiso y motivos en las
  evidencias, pero no un comentario general sobre un registro que otra cuenta
  autorizada pueda consultar.
- **Sin control de versión optimista.** Si dos personas abren el mismo registro
  y ambas guardan, gana la última y la primera pierde su cambio sin aviso.
  Resolverlo exige un campo de versión en cada formulario y una comprobación al
  guardar; queda registrado como defecto abierto.
- **La alerta no llega a quien debe actuar.** Ningún rol puede a la vez ver las
  alertas y cerrar el compromiso que las origina: mover el estado exige
  `registrar_actividad`, que solo tiene el rol Funcionario, y Funcionario es el
  único sin `ver_tablero`. Desde Alertas solo se puede reasignar. Es una
  decisión de la matriz de permisos, no un error de código, y cambiarla ahora
  invalidaría los casos de seguridad ya ejecutados.
- Sin copias de seguridad automáticas de la base ni certificado HTTPS propio.

---

## 11. Uso de inteligencia artificial y verificación del equipo

Se utilizó un asistente de inteligencia artificial de forma intensiva en esta
entrega. Se declara con precisión porque la pauta lo exige y porque una
declaración que no calce con el trabajo real sería peor que no declarar nada.

**Qué hizo el asistente.** Escribió la mayor parte del código Python y de las
plantillas: el motor del mantenedor reutilizable y los seis mantenedores que
salen de él, las vistas, los formularios, el motor de cálculo, la agenda de
compromisos, las alertas, la auditoría y los informes. También escribió las
ocho suites de comprobación automatizada y la mayor parte de este documento.

**Qué hizo el equipo.** Definió el alcance y las reglas de negocio. Produjo la
maqueta de las pantallas, que es el documento contra el cual se construyó cada
vista y la fuente de las cinco reglas de alerta y de los cuatro informes.
Decidió qué se implementaba, qué quedaba fuera y con qué justificación —los
ajustes de TAB-04 se declararon fuera porque el caso exige una regla aprobada
que no existe—. Ejecutó el plan de pruebas sobre MariaDB. Desplegó el sistema
en AWS.

**La verificación manual encontró lo que las comprobaciones automatizadas no
podían encontrar.** De los catorce defectos registrados en el plan, seis los
encontró el equipo probando a mano sobre MariaDB, y dos eran estructuralmente
invisibles para las suites, que corren sobre SQLite:

- **DEF-11** — un filtro por fecha que MariaDB resuelve a NULL cuando las
  tablas de zona horaria vienen vacías, como vienen instaladas de fábrica. Una
  de las cinco alertas no aparecía nunca, sin error y sin aviso. Sobre SQLite
  funcionaba.
- **DEF-12** — una ficha que se caía cuando el historial tenía una fila sin
  autor. Las suites solo dibujaban objetos creados por ellas mismas, siempre
  completos; los datos de demostración sí tienen huecos.

Esa diferencia es el argumento de esta sección. El código lo escribió en su
mayor parte una herramienta; la verificación que lo volvió confiable la hizo
el equipo, y está documentada caso por caso en el plan de pruebas y en la hoja
de defectos.

Los cuatro integrantes pueden explicar:

- la configuración de `DATABASES` y por qué el backend `mysql` sirve para
  MariaDB;
- la definición de cada modelo y de cada campo agregado en esta entrega;
- las migraciones, incluido el paso de datos con `RunPython` que permite
  agregar una columna `unique` sobre registros existentes;
- las relaciones y la estrategia de eliminación de cada una, y por qué
  `PROTECT` se refleja en `motivo_bloqueo()`;
- la personalización del administrador;
- cómo una vista de clase se convierte en seis mantenedores, y por qué el
  estado del listado viaja en la dirección;
- dónde se comprueban los permisos y por qué esconder el menú no es seguridad.

### Cómo se verificó

| Qué se comprobó | Cómo |
|---|---|
| Configuración, modelos, plantillas, rutas y administrador | `python manage.py check` — sin observaciones. |
| Modelos y migraciones coinciden | `python manage.py makemigrations --check --dry-run` — sin cambios pendientes. |
| Las pantallas responden | Recorrido con el cliente de pruebas de Django, con los datos de demostración cargados: las trece de la entrega y las nueve que se agregaron después. |
| El cálculo da los números del plan | Los seis lotes `CAL-A` a `CAL-F` del plan de pruebas, comparados contra su resultado verificable: 80 % y 50 % de cumplimiento, aportes de 32 y 30, total 62; con tope 150 el bruto 200 % y el computable 150 %, aporte 60, total 90; el avance esperado en 0 %, 3,33 %, 50 %, 100 % y 100 %; el semáforo rojo, ámbar, ámbar y verde en 29,99 %, 30 %, 49,99 % y 50 %; el umbral colectivo alcanzado desde 80 % inclusive. |
| La cadena de la actividad | Registrar, adjuntar, rechazar con motivo, corregir, reenviar, aprobar y anular, comprobando que solo lo aprobado suma y que aprobar dos veces no suma dos veces. |
| La agenda | Los seis casos `AGE-01` a `AGE-06`: compromiso completo y vinculado, rechazo sin responsable y sin fecha, la matriz de transiciones con una prohibida, el atraso que el cierre conserva, cerrar sin validar que no otorga puntaje, y la reasignación con su historial. |
| Alertas y auditoría | `TAB-06`: las cinco condiciones se provocan y cada alerta trae motivo, responsable, fecha y enlace; marcarla revisada no toca el compromiso que la originó. `INT-03`: alta, edición, estado, validación y cambio de parámetros quedan con usuario, fecha, origen, antes y después; un perfil operativo recibe 403 y las rutas de edición y borrado no existen. |
| Búsqueda, filtros, orden, paginador y exportación | Combinaciones de parámetros en los seis listados, incluidos valores inventados en `orden` y `tam`. |
| Validaciones de los formularios | Casos válidos e inválidos: nombre repetido, nombre corto, teléfono con letras, rol sin permisos, correo duplicado, ponderadores sobre 100, RUT con dígito verificador incorrecto, subatención de otro tipo, documento faltante, detalle insuficiente. |
| Bloqueos de desactivación | Delegación con usuarios, rol con usuarios, tipo con subatenciones activas y el último administrador activo. |
| Permisos | Cada mantenedor con un rol que no lo habilita (403), sin sesión (redirección al login con `next`), y el cambio de estado por `GET` (405). |
| Recuperación de contraseña | Los cuatro pasos, más código equivocado, tres intentos agotados, reenvío, salto directo al paso 4 y correo inexistente. |
| Carga de datos | Base limpia, comando ejecutado dos veces, recuentos y fechas. |


---

## 12. Estructura del proyecto

```
proyecto_sgr/
  manage.py
  requirements.txt
  .env.example                      variables necesarias, sin valores reales
  .gitignore
  README.md
  config/
    settings.py                     configuración, base de datos, correo, seguridad
    urls.py                         monta las rutas de cada aplicación
    entorno.py                      lectura de variables de entorno y del .env
    admin_base.py                   mixin de selectores y acciones del administrador
    wsgi.py  asgi.py
  comun/                            lo transversal
    models.py                       auditoría y marcas de alerta revisada
    auditoria.py                    la única forma de escribir en la auditoría
    mantenedor.py                   el patrón de mantenedor, una sola vez
    permisos.py                     la tabla de permisos y cómo se comprueba
    contexto.py                     delegación activa en la sesión
    navegacion.py                   valida los destinos de vuelta (redirección abierta)
    excel.py                        exportación de los listados
    utilidades.py                   correlativos y suma de ponderadores
    views.py  urls.py               panel y cambio de delegación
    templatetags/sgr.py             tres etiquetas de plantilla
  organizacion/                     Delegacion, Rol, PerfilUsuario
    models.py  forms.py  views.py  urls.py  admin.py
    migrations/0001_initial.py  0002_entrega2.py
    management/commands/cargar_datos_demo.py
  catalogos/                        Item, TipoAtencion, SubAtencion
    models.py  forms.py  views.py  urls.py  admin.py
    migrations/0001_initial.py  0002_entrega2.py  0003_codigos_de_ejemplo.py
  atencion/                         Solicitante, Atencion
    models.py  forms.py  views.py  urls.py  admin.py
    migrations/0001_initial.py
  cuenta/                           CodigoRecuperacion y el acceso
    models.py  forms.py  views.py  urls.py  admin.py
    migrations/0001_initial.py
  gestion/                          el período y todo lo que se mide dentro
    models.py                       Periodo, Cargo, MetaPeriodo
    modelos_actividad.py            Actividad y Evidencia
    evidencias.py                   archivos: formatos, tamaño, nombre seguro
    modelos_agenda.py               Compromiso y su historial de cambios
    reglas.py                       ReglaCalculo: los parámetros, como dato
    calculo.py                      el motor; la única aritmética del sistema
    tablero.py                      los recuentos que acompañan al resultado
    alertas.py                      las cinco condiciones, calculadas al vuelo
    informes.py                     los cuatro informes consolidados
    forms.py  forms_actividad.py  forms_agenda.py
    views.py  views_actividad.py  views_agenda.py  views_alertas.py
    views_informes.py  views_tablero.py  urls.py  admin.py
    migrations/0001_initial.py … 0008_evidencia_archivo.py
  templates/
    base.html                       el marco institucional
    comun/                          listado, formulario, ficha, panel, 403, 404
    organizacion/  catalogos/       paneles laterales de los formularios
    atencion/                       ingreso y consulta
    cuenta/                         las cuatro pantallas de acceso
    gestion/                        período, actividad, evidencia, agenda,
                                    mi resultado y tablero
  static/sgr/
    css/sgr.css  css/sgr2.css
    js/sgr.js  js/sgr-app.js
    img/escudo.png  img/favicon.png
```

**Qué hace cada archivo de JavaScript.** `sgr.js` viene de la maqueta y aporta
los componentes de interfaz (avisos flotantes, mostrar la contraseña).
`sgr-app.js` es el de esta entrega y es deliberadamente corto: en la maqueta el
navegador filtraba, ordenaba y paginaba; aquí eso lo hace el servidor, y lo que
queda en JavaScript solo mejora el uso. Todo funciona sin él: los formularios
tienen su botón de enviar, los selectores su opción de cambiar, y la validación
que manda es la del servidor.
