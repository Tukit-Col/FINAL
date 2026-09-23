"""Arma los dos CSV de listas oficiales que los cargadores siembran.

De donde salen. El corpus original es `Arquitectura/Corpus_ItemLista_v2.csv`,
4.719 renglones transcritos de los PDF que publicaron 17 colegios, y vive
FUERA del monorepo porque es material de la tesis: notas, PDF originales y
hojas de calculo que no son codigo desplegable.

Por que los CSV si entran al monorepo. Un cargador que leyera esa ruta seria
un cargador que solo corre en el portatil donde se escribio la tesis. La
integracion continua no tiene `Arquitectura/`, un compañero que clone el
repositorio tampoco, y el fallo no seria un error de importacion sino algo
peor: una siembra que corre, no encuentra nada y deja la base vacia sin que
nadie lo note. La regla que lo evita es que **el monorepo no depende de
ninguna ruta fuera de el**; lo que necesita para arrancar esta versionado con
el codigo que lo lee, y este script es la unica pieza que cruza esa frontera,
a mano y cuando el corpus cambia.

Que produce, y por que dos ficheros y no uno:

- `colegios.csv`: el inquilino. Lo siembra Identidad, que es donde vive la
  tenencia.
- `items_lista.csv`: lo que cada colegio pide. Lo siembra Catalogo, porque una
  lista de utiles es vocabulario de catalogo.

Un solo CSV desnormalizado obligaria a los dos servicios a leerlo entero y a
ponerse de acuerdo sobre que columnas son de quien, que es justo la clase de
acoplamiento que las fronteras del manifiesto existen para impedir. El unico
dato que ambos comparten es el `codigo` del colegio, y de el sale el mismo
UUID en los dos lados via `tukit_comun.derivar`.

Uso:

    python datos/listas/construir.py
    python datos/listas/construir.py --corpus /otra/ruta.csv --salida /tmp
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

AQUI = Path(__file__).resolve().parent
# `parents[2]` es la raiz del monorepo y `parents[3]` el directorio de la
# tesis, que lo contiene. Escrito asi para que el script siga encontrando el
# corpus si alguien clona el repositorio con otro nombre de carpeta.
CORPUS_POR_OMISION = AQUI.parents[2] / "Arquitectura" / "Corpus_ItemLista_v2.csv"

# Nombre presentable de cada colegio. Es curaduria, no derivacion: el corpus
# esta anonimizado con codigos (`2.4`) y el CONTRATO_API los usa tal cual, asi
# que el codigo NO se puede cambiar. Lo que si se puede es ponerle al lado un
# nombre que un papa reconozca, y ese solo sale de mirar el PDF del que se
# transcribio la lista.
#
# Los que no estan aqui caen en `Colegio <codigo>` a proposito. Los tres `1.x`
# salieron de hojas de un xlsx sin PDF fuente, y varios `2.x` tienen un PDF
# cuyo nombre es generico (`LISTA-DE-UTILES-2026.pdf`) y no dice de que
# colegio es. Inventarles un nombre bonito seria peor que el codigo: el codigo
# al menos no miente.
NOMBRES_POR_CODIGO: dict[str, str] = {
    "2.1": "Colegio Matilde",  # matilde.pdf
    "2.3": "Colegio San Jose de Fontibon",  # LISTAS-DE-TEXTOS-ESCOLARES-COLEGIO-SAN-JOSE-DE-FONTIBON.pdf
    "2.4": "Colegio San Pedro",  # san pedro.pdf
    "2.9": "Colegio Modelia",  # modelia.pdf
    "2.10": "Jardin Osito de Miel",  # ositodemiel.pdf
    "2.11": "Colegio Bahia Solano",  # bahiasolano.pdf
    "2.12": "Colegio Alamei",  # alamei.pdf
    "2.13": "Colegio CACS",  # TEXTOS-Y-UTILES-ESCOLARES-2026-CACS.docx-1.pdf
}

# El corpus no distingue sedes: cada colegio publico una sola lista por grado.
# Se siembra una sede igual porque `matricula` cuelga de la sede y no del
# colegio, y sin ella no habria donde matricular a nadie.
SEDE_UNICA = "Sede unica"

# Copia deliberada de `tukit_catalogo.modelos.base.MODOS_SURTIBLES`. Este
# script no pertenece a ningun servicio y no puede importar de uno sin
# convertir un generador de datos en codigo acoplado al despliegue. Lo que
# protege la copia de desincronizarse no es la disciplina: es que el cargador
# comprueba la misma condicion contra el enum de verdad y rellena lo que falte.
MODOS_SURTIBLES = frozenset({"mercado_abierto", "libro_libre"})

# `desconocido` no es un valor de `ModoAdquisicion` y son 736 renglones, casi
# todos textos escolares. La transcripcion lo uso para "el PDF no dice quien
# lo vende", que es distinto de "no se vende en la calle".
#
# Se mapea a `mercado_abierto` y no a un modo cerrado porque la alternativa es
# peor en la direccion que importa: marcarlos cerrados los sacaria del carrito
# y le diria al papa "esto no te lo conseguimos" por 736 renglones sobre los
# que nadie afirmo tal cosa. Abiertos, el peor caso es que el emparejamiento no
# encuentre la edicion y el renglon quede sin producto, que es visible y se
# arregla; cerrarlos esconde el problema detras de una instruccion inventada.
MODO_CUANDO_EL_PDF_NO_LO_DICE = "mercado_abierto"

# Que decirle al papa cuando Tukit no puede poner el renglon en el carrito.
#
# La restriccion `item_no_surtible_explica_como_conseguirlo` exige que estos
# renglones traigan texto, y la exige por una razon concreta: una linea que
# dice "esto no te lo vendemos" y no dice donde conseguirlo deja al acudiente
# peor que antes de abrir Tukit. Los textos son los que el propio corpus
# sostiene: se dice lo que el colegio declaro, sin prometer un canal que
# nadie verifico.
INSTRUCCION_POR_MODO: dict[str, str] = {
    "plataforma": (
        "El colegio indica que se adquiere por plataforma externa. "
        "Sigue el enlace o las instrucciones que el colegio publico en su lista."
    ),
    "venta_directa_editorial": (
        "El colegio indica que la editorial lo vende directamente a las familias, "
        "por lo general en una jornada de venta en el plantel."
    ),
    "edicion_exclusiva": (
        "El colegio indica que es una edicion exclusiva para la institucion: "
        "solo se consigue por el canal que el colegio senale."
    ),
    "diferido": (
        "El colegio indica que se pide mas adelante en el ano lectivo. Todavia no hay que comprarlo."
    ),
}

# Un enlace escrito dentro del renglon. Aparece 18 veces en el corpus y
# siempre en renglones de plataforma ("... Link de pago: https://..."), que
# son justamente los que el acudiente tiene que resolver por fuera. Dejarlo
# enterrado en el texto obliga a copiarlo a mano de una pantalla.
ENLACE = re.compile(r"https?://[^\s,;)\]}'\"]+")


def nombre_presentable(codigo: str) -> str:
    return NOMBRES_POR_CODIGO.get(codigo, f"Colegio {codigo}")


def normalizar_modo(crudo: str) -> str:
    limpio = (crudo or "").strip()
    if not limpio or limpio == "desconocido":
        return MODO_CUANDO_EL_PDF_NO_LO_DICE
    return limpio


def corregir_modo(tipo: str, modo: str) -> str:
    """Arregla una combinacion del corpus que no puede ser cierta.

    El corpus trae 44 renglones con `tipo_item = util` y
    `modo_adquisicion = plataforma`: "cuadernos grandes cuadriculados cosidos
    de 50 hojas", "carpeta de carton tamano oficio con gancho legajador",
    "kit de geometria". Papeleria, toda.

    Y no puede ser cierta, porque `plataforma` no significa "dificil de
    conseguir" sino algo muy concreto: se paga con un enlace o con un codigo
    de acceso, que es la forma de comprar una licencia digital y no un
    cuaderno. La explicacion probable es de transcripcion: el renglon estaba
    debajo de un encabezado del PDF que hablaba de un link de pago y la
    etiqueta se corrio hacia abajo.

    Se corrige aqui y no se deja pasar porque el efecto de no hacerlo es caro
    y silencioso: un renglon `plataforma` sale del carrito, no suma al total
    y se le muestra al papa como "esto lo resuelves por fuera". Quedarse
    callado con doce cuadernos de una lista de cincuenta y cinco es
    exactamente la lista incompleta que Tukit existe para no producir.

    La correccion es estrecha a proposito. `util` + `venta_directa_editorial`
    NO se toca, aunque suene igual de raro: hay jardines que venden utiles en
    el plantel, y el parseo ya tiene ese caso ("directamente en el jardin").
    Solo se corrige la combinacion que el propio vocabulario vuelve imposible.
    """
    if tipo == "util" and modo == "plataforma":
        return MODO_CUANDO_EL_PDF_NO_LO_DICE
    return modo


def instruccion(modo: str) -> str:
    """El texto que acompana a un renglon que Tukit no surte. Vacio si lo surte."""
    if modo in MODOS_SURTIBLES:
        return ""
    return INSTRUCCION_POR_MODO.get(
        modo, "El colegio indica que este renglon no se compra en el mercado abierto."
    )


def url_externa(texto: str) -> str:
    encontrado = ENLACE.search(texto or "")
    if not encontrado:
        return ""
    # El punto final de una frase se pega a la URL al transcribir un PDF.
    return encontrado.group(0).rstrip(".")


def cantidad_valida(crudo: str) -> int:
    """Al menos uno, porque `item_cantidad_positiva` no admite cero.

    Un renglon con cantidad cero no significa que el colegio no lo pida:
    significa que la transcripcion no encontro el numero. Pedir uno es la
    lectura conservadora y la unica que la base acepta.
    """
    try:
        cantidad = int(float((crudo or "").strip()))
    except ValueError:
        return 1
    return cantidad if cantidad > 0 else 1


def leer_corpus(ruta: Path) -> list[dict[str, str]]:
    with ruta.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def armar_colegios(filas: list[dict[str, str]]) -> list[dict[str, str]]:
    """Un colegio por codigo, en el orden en que aparecen en el corpus."""
    codigos: list[str] = []
    vistos: set[str] = set()
    for fila in filas:
        codigo = fila["colegio_id"].strip()
        if codigo and codigo not in vistos:
            vistos.add(codigo)
            codigos.append(codigo)
    return [
        {"codigo": c, "nombre": nombre_presentable(c), "sede_nombre": SEDE_UNICA}
        for c in sorted(codigos, key=_orden_codigo)
    ]


def _orden_codigo(codigo: str) -> tuple[int, ...]:
    """`2.10` va despues de `2.9`, no entre `2.1` y `2.2`.

    Ordenar los codigos como texto dejaba el fichero en un orden que parece
    correcto y no lo es, y eso ensucia el diff cada vez que se regenera.
    """
    try:
        return tuple(int(p) for p in codigo.split("."))
    except ValueError:
        return (999,)


def armar_items(filas: list[dict[str, str]]) -> list[dict[str, str]]:
    """Un renglon por fila del corpus, numerado dentro de su lista.

    El `orden` se cuenta por pareja (colegio, grado) y no global, porque es lo
    que la restriccion `uq_item_version_orden` pide: unico dentro de la version
    de UNA lista. Un contador global tambien seria unico, pero perderia lo
    unico que el numero significa, que es el lugar del renglon en la hoja que
    el colegio publico.
    """
    contador: dict[tuple[str, str], int] = defaultdict(int)
    items: list[dict[str, str]] = []
    for fila in filas:
        colegio = fila["colegio_id"].strip()
        grado = fila["grado"].strip()
        texto = fila["texto_original"].strip()
        if not colegio or not grado or not texto:
            continue
        contador[(colegio, grado)] += 1
        tipo = (fila.get("tipo_item") or "").strip()
        modo = corregir_modo(tipo, normalizar_modo(fila.get("modo_adquisicion", "")))
        items.append(
            {
                "colegio_codigo": colegio,
                "grado": grado,
                "orden": str(contador[(colegio, grado)]),
                "texto_original": texto,
                "cantidad": str(cantidad_valida(fila.get("cantidad", ""))),
                "tipo_item": tipo,
                "modo_adquisicion": modo,
                "categoria": (fila.get("categoria") or "").strip(),
                "instruccion_colegio": instruccion(modo),
                "url_externa": url_externa(texto),
            }
        )
    return items


def escribir(ruta: Path, columnas: list[str], filas: list[dict[str, str]]) -> None:
    # `newline=""` y `\n` explicito: sin los dos, en Windows el fichero sale
    # con saltos dobles y el diff de la siguiente regeneracion es el fichero
    # entero.
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        escritor = csv.DictWriter(fh, fieldnames=columnas, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--corpus", type=Path, default=CORPUS_POR_OMISION)
    analizador.add_argument("--salida", type=Path, default=AQUI)
    args = analizador.parse_args()

    if not args.corpus.exists():
        print(f"No encuentro el corpus en {args.corpus}")
        print("Es material de la tesis y vive fuera del monorepo: pasalo con --corpus.")
        return 2

    filas = leer_corpus(args.corpus)
    colegios = armar_colegios(filas)
    items = armar_items(filas)

    args.salida.mkdir(parents=True, exist_ok=True)
    escribir(args.salida / "colegios.csv", ["codigo", "nombre", "sede_nombre"], colegios)
    escribir(
        args.salida / "items_lista.csv",
        [
            "colegio_codigo",
            "grado",
            "orden",
            "texto_original",
            "cantidad",
            "tipo_item",
            "modo_adquisicion",
            "categoria",
            "instruccion_colegio",
            "url_externa",
        ],
        items,
    )

    listas = {(i["colegio_codigo"], i["grado"]) for i in items}
    no_surtibles = [i for i in items if i["modo_adquisicion"] not in MODOS_SURTIBLES]
    sin_nombre = [c for c in colegios if c["codigo"] not in NOMBRES_POR_CODIGO]

    print(f"corpus                        {len(filas):5} filas  ({args.corpus})")
    print(f"colegios.csv                  {len(colegios):5}")
    print(f"items_lista.csv               {len(items):5}")
    print(f"listas (colegio x grado)      {len(listas):5}")
    print(f"renglones que Tukit no surte  {len(no_surtibles):5}  todos con instruccion")
    print(f"colegios sin nombre curado    {len(sin_nombre):5}  {[c['codigo'] for c in sin_nombre]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
