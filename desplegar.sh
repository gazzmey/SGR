#!/usr/bin/env bash
#
# desplegar.sh · publica en el servidor de AWS la versión que está en GitHub
#
# GitHub es la copia oficial del código. En el servidor no se edita nada a
# mano: el cambio se sube a la rama main y se publica con este script.
#
#   bash ~/SGR/desplegar.sh revisar    muestra qué cambiaría, sin tocar la aplicación
#   bash ~/SGR/desplegar.sh            publica la última versión de main
#   bash ~/SGR/desplegar.sh volver     restaura el código del último respaldo
#
# Al publicar, en orden:
#   1. Trae la última versión de GitHub al clon (~/SGR).
#   2. Compara los archivos de proyecto_sgr/ con los de la aplicación. Si no
#      hay diferencias, termina ahí.
#   3. Revisa la versión nueva con «manage.py check» y confirma que no falten
#      migraciones. Si algo falla, se detiene sin haber copiado nada.
#   4. Pide confirmación y respalda el código y la base de datos en
#      ~/respaldos (guarda los diez últimos de cada uno).
#   5. Copia solo los archivos del repositorio que cambiaron. Nunca toca
#      venv/, .env, staticfiles/ ni nada que no esté en GitHub.
#   6. Instala dependencias (solo si cambió requirements.txt), aplica las
#      migraciones y recolecta los archivos estáticos.
#   7. Reinicia el servicio y comprueba que la página responda.
#
# Preparación del servidor, una sola vez:
#   sudo dnf install -y git
#   git clone https://github.com/gazzmey/SGR.git ~/SGR
#
# Todo se ejecuta dentro de main(), que se llama en la última línea: así bash
# ya leyó el archivo completo cuando «git pull» lo actualiza.

REPO="${SGR_REPO:-$HOME/SGR}"
PROYECTO="${SGR_PROYECTO:-$HOME/proyecto_integrado}"
SERVICIO="${SGR_SERVICIO:-sgr}"
RESPALDOS="${SGR_RESPALDOS:-$HOME/respaldos}"
ORIGEN="$REPO/proyecto_sgr"
PY="$PROYECTO/venv/bin/python"
CONSERVAR=10
VERSION=""
COPIADO=0

paso()  { printf '\n== %s\n' "$*"; }
aviso() { printf '  ! %s\n' "$*"; }

falla() {
    printf '\nERROR: %s\n' "$*" >&2
    if [[ "$COPIADO" == 1 ]]; then
        printf '       Los archivos nuevos ya se copiaron. Para volver al código anterior:\n' >&2
        printf '       bash %s/desplegar.sh volver\n' "$REPO" >&2
    fi
    exit 1
}

# Lee una variable del .env de la aplicación; si no está, usa la del entorno
# y, si tampoco, el valor por omisión. Mismo orden que config/entorno.py.
leer_env() {
    local v=""
    if [[ -r "$PROYECTO/.env" ]]; then
        v=$(grep -E "^[[:space:]]*$1[[:space:]]*=" "$PROYECTO/.env" | tail -n 1 | cut -d= -f2- || true)
    fi
    v="${v%$'\r'}"
    v="${v#"${v%%[![:space:]]*}"}"
    v="${v%"${v##*[![:space:]]}"}"
    printf '%s' "${v:-${!1:-$2}}"
}

preparar() {
    command -v git >/dev/null || falla "Falta git. Instálalo con: sudo dnf install -y git"
    [[ -d "$REPO/.git" ]] \
        || falla "No existe el clon en $REPO. Créalo con: git clone https://github.com/gazzmey/SGR.git $REPO"
    [[ -f "$PROYECTO/manage.py" ]] || falla "No encontré la aplicación en $PROYECTO."
    [[ -x "$PY" ]] || falla "No encontré el entorno virtual: $PY"
    # El clon se revisa con la misma configuración que la aplicación. .env
    # está en .gitignore: el enlace no se sube a GitHub ni se copia.
    if [[ -f "$PROYECTO/.env" && ! -e "$ORIGEN/.env" ]]; then
        ln -s "$PROYECTO/.env" "$ORIGEN/.env"
    fi
}

actualizar() {
    git -C "$REPO" pull --ff-only --quiet \
        || falla "git pull no pudo avanzar. Revisa si alguien editó archivos dentro de $REPO con: git -C $REPO status"
    VERSION=$(git -C "$REPO" log -1 --format='%h %s')
    printf '  GitHub (main):   %s\n' "$VERSION"
    printf '  En el servidor:  %s\n' \
        "$(cat "$PROYECTO/.desplegado" 2>/dev/null || echo 'sin registro (todavía no se publica con este script)')"
}

# Los archivos de la aplicación que están en GitHub, relativos a proyecto_sgr/.
archivos_repo() {
    git -C "$REPO" -c core.quotepath=off ls-files -- proyecto_sgr | sed 's#^proyecto_sgr/##'
}

# Una línea por archivo distinto: «nuevo<TAB>ruta» o «cambia<TAB>ruta».
comparar() {
    local ruta
    while IFS= read -r ruta; do
        if [[ ! -e "$PROYECTO/$ruta" ]]; then
            printf 'nuevo\t%s\n' "$ruta"
        elif ! cmp -s "$ORIGEN/$ruta" "$PROYECTO/$ruta"; then
            printf 'cambia\t%s\n' "$ruta"
        fi
    done < <(archivos_repo)
}

# Archivos de la aplicación que no están en GitHub. El script no los toca;
# se listan para que nada viva en el servidor sin que se sepa.
solo_en_servidor() {
    comm -13 \
        <(archivos_repo | LC_ALL=C sort) \
        <(cd "$PROYECTO" && find . \( -path ./venv -o -path ./.venv -o -path ./staticfiles \
                -o -path ./media -o -name __pycache__ \) -prune \
              -o -type f ! -name .env ! -name .desplegado ! -name '*.pyc' -print \
          | sed 's#^\./##' | LC_ALL=C sort)
}

mostrar() {
    local estado ruta
    while IFS=$'\t' read -r estado ruta; do
        printf '  %-7s %s\n' "$estado" "$ruta"
    done
}

respaldar() {
    local fecha codigo bd dump patron
    fecha=$(date +%Y%m%d_%H%M%S)
    codigo="$RESPALDOS/codigo_$fecha.tar.gz"
    bd="$RESPALDOS/bd_$fecha.sql.gz"
    mkdir -p "$RESPALDOS"
    chmod 700 "$RESPALDOS"

    tar -czf "$codigo" -C "$PROYECTO" \
        --exclude=./venv --exclude=./.venv --exclude=./staticfiles --exclude=./media \
        --exclude=./.env --exclude=__pycache__ --exclude='*.pyc' .
    printf '  código:         %s\n' "$codigo"

    dump=$(command -v mariadb-dump || command -v mysqldump || true)
    [[ -n "$dump" ]] || falla "No encontré mariadb-dump ni mysqldump para respaldar la base. No se copió nada."
    if ! MYSQL_PWD="$(leer_env SGR_DB_PASSWORD '')" "$dump" \
            --host="$(leer_env SGR_DB_HOST 127.0.0.1)" \
            --port="$(leer_env SGR_DB_PORT 3306)" \
            --user="$(leer_env SGR_DB_USER sgr_app)" \
            --single-transaction --no-tablespaces \
            "$(leer_env SGR_DB_NAME sgr)" | gzip > "$bd"; then
        rm -f "$bd"
        falla "No pude respaldar la base de datos (ver el mensaje de arriba). No se copió nada."
    fi
    printf '  base de datos:  %s\n' "$bd"

    for patron in 'codigo_*.tar.gz' 'bd_*.sql.gz'; do
        { ls -1t "$RESPALDOS"/$patron 2>/dev/null || true; } \
            | tail -n +$((CONSERVAR + 1)) \
            | while IFS= read -r viejo; do rm -f -- "$viejo"; done
    done
}

reiniciar() {
    local host codigo="000" i
    sudo systemctl restart "$SERVICIO"

    # Se prueba a través de Nginx, con el mismo nombre de host que usa el
    # navegador: Django rechaza los que no están en ALLOWED_HOSTS.
    host=$(leer_env SGR_ALLOWED_HOSTS 127.0.0.1)
    host="${host%%,*}"
    if [[ -z "$host" || "$host" == "*" ]]; then
        host=127.0.0.1
    fi
    for i in $(seq 1 20); do
        sleep 1
        codigo=$(curl -s -o /dev/null -m 5 -w '%{http_code}' -H "Host: $host" http://127.0.0.1/ || true)
        if [[ "$codigo" != "000" && "$codigo" != "502" ]]; then
            break
        fi
    done

    if ! systemctl is-active --quiet "$SERVICIO"; then
        falla "El servicio $SERVICIO no quedó activo. Revisa: sudo journalctl -u $SERVICIO -n 50"
    fi
    case "$codigo" in
        2??|3??) echo "  Servicio activo; la página responde ($codigo)." ;;
        400)     aviso "La prueba interna recibió 400 (suele ser por el nombre de host). Abre la página en el navegador para confirmar." ;;
        *)       falla "El servicio está activo pero la página respondió $codigo. Revisa: sudo journalctl -u $SERVICIO -n 50" ;;
    esac
}

revisar() {
    local cambios extra
    preparar
    paso "Versiones"
    actualizar

    paso "Archivos que cambiarían al publicar"
    cambios=$(comparar)
    if [[ -n "$cambios" ]]; then
        mostrar <<<"$cambios"
    else
        echo "  Ninguno: el servidor tiene exactamente lo que está en GitHub."
    fi

    paso "Archivos que están solo en el servidor (el script no los toca)"
    extra=$(solo_en_servidor)
    if [[ -n "$extra" ]]; then
        sed 's/^/  /' <<<"$extra"
    else
        echo "  Ninguno."
    fi

    paso "Entorno"
    printf '  %s · Django %s\n' "$("$PY" --version 2>&1)" "$("$PY" -m django --version 2>&1)"
    if ! command -v mariadb-dump >/dev/null && ! command -v mysqldump >/dev/null; then
        aviso "No encontré mariadb-dump ni mysqldump: sin eso no se puede respaldar la base."
    fi
    printf '  Espacio libre: %s\n' "$(df -h "$HOME" | awk 'NR == 2 {print $4}')"
    printf '\nLa aplicación no se modificó.\n'
}

publicar() {
    local cambios salida respuesta estado ruta
    preparar
    paso "1/6  Versiones"
    actualizar

    paso "2/6  Archivos que cambian"
    cambios=$(comparar)
    if [[ -z "$cambios" ]]; then
        echo "  Ninguno: el servidor ya tiene esta versión."
        echo "$VERSION" > "$PROYECTO/.desplegado"
        return 0
    fi
    mostrar <<<"$cambios"

    paso "3/6  Revisando la versión nueva (todavía no se copia nada)"
    if ! salida=$(cd "$ORIGEN" && "$PY" manage.py check 2>&1); then
        printf '%s\n' "$salida"
        falla "manage.py check encontró errores en la versión de GitHub. No se copió nada."
    fi
    if ! salida=$(cd "$ORIGEN" && "$PY" manage.py makemigrations --check --dry-run 2>&1); then
        printf '%s\n' "$salida"
        falla "Hay modelos que cambiaron sin su migración en GitHub. No se copió nada."
    fi
    echo "  Sin errores y sin migraciones faltantes."

    printf '\n¿Publicar estos cambios? Escribe s y Enter para seguir: '
    read -r respuesta || true
    if [[ "$respuesta" != "s" && "$respuesta" != "S" ]]; then
        printf 'Cancelado. No se copió nada.\n'
        return 0
    fi

    paso "4/6  Respaldando código y base de datos"
    respaldar

    paso "5/6  Copiando y aplicando"
    COPIADO=1
    trap 'falla "Falló un paso después de copiar (ver el mensaje de arriba)."' ERR
    while IFS=$'\t' read -r estado ruta; do
        mkdir -p "$(dirname "$PROYECTO/$ruta")"
        cp "$ORIGEN/$ruta" "$PROYECTO/$ruta"
    done <<<"$cambios"
    echo "  $(wc -l <<<"$cambios") archivo(s) copiado(s)."

    cd "$PROYECTO"
    if grep -q $'\trequirements.txt$' <<<"$cambios"; then
        echo "  requirements.txt cambió: instalando dependencias."
        "$PY" -m pip install -q -r requirements.txt
    fi
    "$PY" manage.py migrate --noinput
    "$PY" manage.py collectstatic --noinput -v 0
    echo "  Migraciones y archivos estáticos al día."

    paso "6/6  Reiniciando el servicio"
    reiniciar
    trap - ERR
    echo "$VERSION" > "$PROYECTO/.desplegado"
    printf '\nListo. Publicado: %s\n' "$VERSION"
}

volver() {
    local ultimo bd
    ultimo=$({ ls -1t "$RESPALDOS"/codigo_*.tar.gz 2>/dev/null || true; } | head -n 1)
    [[ -n "$ultimo" ]] || falla "No hay respaldos de código en $RESPALDOS."
    [[ -x "$PY" ]] || falla "No encontré el entorno virtual: $PY"

    paso "Restaurando el código de $(basename "$ultimo")"
    tar -xzf "$ultimo" -C "$PROYECTO"
    (cd "$PROYECTO" && "$PY" manage.py collectstatic --noinput -v 0)
    reiniciar

    bd="${ultimo/codigo_/bd_}"
    bd="${bd%.tar.gz}.sql.gz"
    printf '\nListo. Se restauró el código; la base de datos no se tocó.\n'
    printf 'Si la publicación que se deshizo aplicó migraciones, el respaldo de la base\n'
    printf 'de ese momento es %s\n' "$bd"
}

main() {
    set -Eeuo pipefail
    case "${1:-publicar}" in
        publicar) publicar ;;
        revisar)  revisar ;;
        volver)   volver ;;
        *)        sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 1 ;;
    esac
}

main "$@"; exit $?
