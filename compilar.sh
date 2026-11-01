#!/usr/bin/env bash
# Compila la memoria. No usamos latexmk porque no esta instalado en esta maquina,
# ni biber porque tampoco: la bibliografia va con bibtex y natbib.
#
# Uso:  ./compilar.sh          compila y reporta
#       ./compilar.sh limpiar  borra los auxiliares
set -uo pipefail
cd "$(dirname "$0")"

if [ "${1:-}" = "limpiar" ]; then
    rm -f main.{aux,bbl,blg,log,lof,lot,out,toc} sections/*.aux sections/covers/*.aux
    echo "Auxiliares borrados."
    exit 0
fi

ejecutar() {
    echo "--- $* ---"
    "$@" > /tmp/memoria_paso.log 2>&1
    local codigo=$?
    if [ $codigo -ne 0 ]; then
        echo "FALLO ($codigo). Errores:"
        grep -n -A4 '^!' /tmp/memoria_paso.log | head -40
        return $codigo
    fi
    return 0
}

ejecutar pdflatex -interaction=nonstopmode main.tex || exit 1
# bibtex falla si todavia no hay ninguna cita; en esa etapa no es un error real.
bibtex main > /tmp/memoria_bibtex.log 2>&1 || echo "Aviso: bibtex sin citas todavia."
ejecutar pdflatex -interaction=nonstopmode main.tex || exit 1
ejecutar pdflatex -interaction=nonstopmode main.tex || exit 1

echo
echo "=== Resultado ==="
paginas=$(grep -oE 'Output written on main\.pdf \(([0-9]+) pages' main.log | grep -oE '[0-9]+' | head -1)
echo "Paginas: ${paginas:-desconocido}"

faltantes=$(grep -c 'Citation.*undefined' main.log || true)
[ "$faltantes" -gt 0 ] && echo "Citas sin resolver: $faltantes"

refs=$(grep -c 'Reference.*undefined' main.log || true)
[ "$refs" -gt 0 ] && echo "Referencias cruzadas sin resolver: $refs"

sobreflujo=$(grep -c 'Overfull \\hbox' main.log || true)
echo "Cajas desbordadas: $sobreflujo"
