#!/usr/bin/env bash
# Formatea el archivo que se acaba de editar — SOLO las líneas que el cambio tocó.
#
# Antes corría `ruff format` sobre el archivo entero. En un archivo con código
# preexistente sin formatear, eso reescribe líneas que el cambio nunca tocó: el
# diff se llena de reformateo ajeno, la revisión se encarece y el commit deja de
# ser una intención. Pasó de verdad — un arreglo de 18 sitios colapsó llamadas
# multilinea en media docena de archivos, y hubo que verificar a mano que no
# hubiera lógica escondida entre el ruido.
#
# `ruff check --fix` tampoco vuelve: arreglar de paso un diagnóstico preexistente
# es exactamente el "no lo arregles de paso" que el workflow pide en todas partes.
# Lo que esté mal y no sea tuyo es un hallazgo, no un fix silencioso de un hook.
#
# Funciona desde cualquier subdirectorio del proyecto.

set -uo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")

[ -z "$FILE_PATH" ] && exit 0
[ -f "$FILE_PATH" ] || exit 0

# Rangos de líneas tocadas, en el archivo NUEVO, de abajo hacia arriba: formatear
# un rango corre los números de los de más abajo, así que se procesan al revés.
rangos_tocados() {
    git diff -U0 HEAD -- "$1" 2>/dev/null | awk '
        /^@@/ {
            split($3, a, ",")
            inicio = a[1] + 0
            largo = (length(a) > 1) ? a[2] + 0 : 1
            # La columna del final es obligatoria: "4-5" cierra en la columna 1
            # de la linea 5, o sea ANTES de su contenido, y la ultima linea del
            # rango se queda sin formatear. Con "4:1-5:9999" entra entera.
            if (largo > 0) print inicio ":1-" (inicio + largo - 1) ":9999"
        }
    ' | sort -t- -k1,1nr
}

# Un archivo que git no conoce es enteramente del cambio: no hay nada ajeno que
# estropear, así que se formatea completo.
es_nuevo() {
    ! git ls-files --error-unmatch "$1" >/dev/null 2>&1
}

case "${FILE_PATH##*.}" in
    py)
        command -v ruff &>/dev/null || exit 0
        if es_nuevo "$FILE_PATH"; then
            ruff format "$FILE_PATH" &>/dev/null || true
        else
            while read -r rango; do
                [ -n "$rango" ] || continue
                ruff format --range="$rango" "$FILE_PATH" &>/dev/null || true
            done < <(rangos_tocados "$FILE_PATH")
        fi
        ;;
    ts|tsx|js|jsx)
        # biome no acepta rangos y el de prettier va por desplazamiento de bytes:
        # sin forma de acotar, un archivo ya versionado se deja como está. Lo que
        # el formateo del proyecto exija lo reporta verify.sh, que es su sitio.
        es_nuevo "$FILE_PATH" || exit 0
        if command -v biome &>/dev/null; then
            biome format --write "$FILE_PATH" &>/dev/null || true
        elif command -v prettier &>/dev/null; then
            prettier --write "$FILE_PATH" &>/dev/null || true
        fi
        ;;
esac

exit 0
