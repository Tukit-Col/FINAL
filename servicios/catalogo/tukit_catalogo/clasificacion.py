"""Clasificacion de un renglon de lista contra los conceptos del catalogo.

Normalizacion, cabeza del renglon y parecido. Funciones puras (sin red ni base de datos):
las usan la ruta de consulta, el cargador de listas y el CLI `descubrir`."""

from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any

from .embeddings import coseno


def _plano(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_tildes).strip()


VACIAS = frozenset({"de", "del", "la", "el", "los", "las", "un", "una", "y", "o", "para", "con", "en"})


# Ruido de las listas escolares que no ayuda a buscar en una tienda. La
# cantidad y el empaque describen CUANTO, no QUE, y meterlos en la consulta
# la empeora: buscar `3 bolsas de aserrin de colores` devuelve peor que
# `aserrin de colores`.
RUIDO = re.compile(
    r"\b(\d+\s*)?(unidades?|unds?|uds?|paquetes?|bolsas?|cajas?|docenas?|pares?|"
    r"rollos?|tarros?|frascos?|pliegos?|hojas?|juegos?|sets?|metros?|x\d+)\b"
)


# `metros?` entra porque "metro de cable estanado" es una medida, no lo pedido:
# sin esto la cabeza era "metro" y se la llevaba Lentejuelas ("metro
# lentejuelas..."). Una fraccion suelta ("(1/8 cartulina)") tampoco nombra la
# cosa; el tamano que dice se lee aparte, en `extraer_atributos`.
FRACCION = re.compile(r"\b\d+\s*/\s*\d+\b")


# `Lapiz 2H-6B` no pide un lapiz 2H: pide la serie de durezas, que es el kit
# de dibujo. Se reescribe como "serie durezas", que es como lo nombra ese
# concepto, para que no caiga en el lapiz suelto con la primera dureza exigida.
# Igual una lista de durezas (`Lapices HB, 2H, 2B, 6B`): dos o mas seguidas.
RANGO_DUREZA = re.compile(r"\b\d?[hb]{1,2}(?:\s*(?:-|,|y|a|al|hasta)\s*\d?[hb]{1,2}\b)+")


# `Escuadras 30° y 45°` es el par, que se vende como juego; una escuadra de 45°
# sola sigue siendo una escuadra. Los numeros no cuentan en el parecido, asi que
# sin esto el renglon empataba con `escuadras` y ganaba la escuadra suelta.
PAR_DE_ESCUADRAS = re.compile(
    r"\bescuadras?\b\D*\b(?:30|45|60)\s*(?:°|grados?)?\s*(?:y|,|-|/)?\s*(?:30|45|60)\b\s*(?:°|grados?)?"
)


# Palabras con que un colegio abre un grupo antes de los dos puntos: "Kit escolar:",
# "Materiales para generar textura como:", "Para las ninas:". Es el atajo: no hace
# falta mirar el catalogo para saber que son un encabezado. Con cualquier otra
# palabra, `clasificar` decide con el catalogo (`_sin_encabezado_de_grupo`).
_PREFIJO_DE_GRUPO = re.compile(r"^(kit|materiales?|para)\b")


# Un encabezado de grupo es corto: con mas palabras es la descripcion de la cosa.
_PALABRAS_MAXIMAS_DE_ENCABEZADO = 5


# Lo que el colegio antepone a un libro para decir que clase de libro es: «Texto:
# Cuaderno de actividades», «Novela: El gigante egoista», «Lecto Escritura:
# Cuadernillo ALFA». No agrupa utiles, clasifica un libro; quitarlo deja un nombre
# que se confunde con un util («cuaderno de actividades» -> cuaderno).
_CLASES_DE_LIBRO = frozenset({"texto", "novela", "lecto", "lectoescritura"})


def consulta_desde_renglon(renglon: str) -> str:
    """Convierte el renglon del colegio en algo que una tienda entienda.

    El colegio escribe `3 bolsas de aserrin de colores surtidos` y la tienda
    responde mejor a `aserrin de colores`. Se quitan las cantidades y los
    empaques porque dicen CUANTO y no QUE, y se dejan los adjetivos, que si
    discriminan: `de colores` separa el aserrin escolar del aserrin de
    carpinteria.
    """
    texto = _plano(renglon)
    # "Kit de aseo personal: 1 caja de panuelos" pide los panuelos: ahi lo de antes
    # de los dos puntos nombra un GRUPO, no la cosa (13-nov). Solo se salta cuando
    # el prefijo empieza por una palabra de grupo; en "Cuaderno: grande empastado",
    # "Carpeta ... con gancho: Ingles" o "... legajador. Color: Azul" lo pedido esta
    # ANTES de los dos puntos y lo de despues es un detalle (tamano, materia, color).
    grupo, dos_puntos, resto = texto.partition(":")
    if dos_puntos and resto.strip() and _PREFIJO_DE_GRUPO.match(grupo.strip()):
        texto = resto
    texto = re.sub(r"[(),;:.]", " ", texto)
    texto = FRACCION.sub(" ", texto)
    texto = RUIDO.sub(" ", texto)
    texto = re.sub(r"\b\d+\s*(gr?|grs|gramos?|ml|cc|cm|mm|mts?|metros?)\b", " ", texto)
    texto = re.sub(r"^\s*\d+\s+", "", texto)
    # La cantidad tambien se escribe en palabras ("Una caja de", "dos paquetes de").
    texto = re.sub(
        r"^\s*(un|una|unos|unas|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|doce)\s+", "", texto
    )
    palabras = [
        p for p in texto.split() if len(p) > 1 and p not in ("de", "del", "la", "el", "y", "o", "para", "con")
    ]
    return " ".join(palabras[:6])


def _parecido(a: str, b: str) -> float:
    """Cuanto se parecen dos textos, por palabras compartidas.

    Es un Jaccard sobre palabras, no un embedding. Aqui solo hace falta
    decidir si el renglon cae en un concepto que ya existe o si hay que
    proponer uno nuevo, y para eso un empate de palabras alcanza. La busqueda
    fina, con trigramas y vectores, corre contra el catalogo ya curado y es
    trabajo del resolutor, no de esto.

    Las preposiciones no cuentan como coincidencia. Parece quisquilloso y
    decidia casos: `chaquiras de colores` contra `colores de madera` comparten
    `colores` y `de`, y ese `de` subia el parecido a 0.5 justo hasta el umbral,
    con lo que unas chaquiras entraban al concepto de los lapices de colores.
    Compartir una preposicion no es parecerse.
    """
    pa = _significativas(a)
    pb = _significativas(b)
    if not pa or not pb:
        return 0.0
    return len(pa & pb) / len(pa | pb)


def _significativas(texto: str) -> set[str]:
    """Las palabras que aportan, en singular y sin numeros.

    El singular importa aqui por la misma razon que en la cabeza, y no
    haberlo puesto tenia una consecuencia que se veia: `2 lapices negros` y
    el sinonimo `lapiz negro` no compartian NINGUNA palabra, porque ambas
    diferian en la flexion. El parecido salia 0 y el renglon se decidia por
    el orden de la tabla, que lo mandaba a esfero.

    Los numeros se caen porque cuentan, no describen: `2` no acerca ni aleja
    un renglon de un concepto, pero sí infla el denominador del Jaccard y
    hunde el parecido de las frases con cantidad.
    """
    return {singular(p) for p in _plano(texto).split() if p not in VACIAS and not p.isdigit() and len(p) > 1}


def cabeza(renglon: str) -> str:
    """El sustantivo que nombra la cosa pedida.

    En espanol el nucleo del sintagma va primero: en `pompones de colores` lo
    pedido son pompones y `de colores` solo los describe. Basta con tomar la
    primera palabra util, despues de quitar cantidades y empaques.
    """
    # Un numero cuenta, no nombra: en "paquete de 20 resistencias" el empaque se
    # cae y el 20 quedaba de cabeza (13-nov).
    palabras = [p for p in consulta_desde_renglon(renglon).split() if not p.isdigit()]
    return palabras[0] if palabras else ""


def singular(palabra: str) -> str:
    """El singular de una palabra en espanol, para poder comparar raices.

    Existe por un error concreto: `lapices de colores x 12` se clasificaba
    como esfero. Comparando los primeros cinco caracteres, `lapices` da
    `lapic` y el sinonimo `lapiz colores` del concepto correcto empieza por
    `lapiz`, que no empareja porque el plural de `-z` en espanol es `-ces`.
    En cambio `lapicero`, sinonimo de esfero, si empieza por `lapic`, y se
    ganaba el renglon.

    Cortar prefijos mas cortos habria emparejado tambien `lapida`. Lo que
    falla no es la longitud del corte sino comparar formas flexionadas, asi
    que se comparan singulares.
    """
    if len(palabra) > 4 and palabra.endswith("ces"):
        return palabra[:-3] + "z"
    if len(palabra) > 4 and palabra.endswith("es"):
        return palabra[:-2]
    # `tres` y `mes` acaban en `es` sin ser plurales de nada, y quitarselo
    # las convertia en `tre` y `me`. Van antes de la regla general de la `s`
    # para que no las alcance.
    if palabra.endswith("es"):
        return palabra
    if len(palabra) > 3 and palabra.endswith("s"):
        return palabra[:-1]
    return palabra


def _sin_encabezado_de_grupo(renglon: str, conceptos: list[dict[str, Any]]) -> str:
    """El renglon sin su encabezado: «Utiles: lapiz negro» -> «lapiz negro».

    Ante «X: resto», X es un encabezado cuando no nombra nada de nuestro
    catalogo y es corto. Si X es un concepto o un sinonimo —«Cuaderno: grande
    empastado», «Colores: caja x 12»— es la cosa pedida y lo de despues es un
    detalle: el renglon se deja como esta. «Nombrar» es que la cabeza de X sea,
    en singular, la primera palabra de un nombre o sinonimo; la comparacion por
    raiz de cinco letras de `_misma_cosa` no sirve aqui, porque `papeleria` y
    `papel` quedan iguales y el encabezado se tomaria por un concepto.
    """
    grupo, dos_puntos, resto = renglon.partition(":")
    if not dos_puntos or not resto.strip():
        return renglon
    if _PREFIJO_DE_GRUPO.match(grupo.strip()):
        return resto
    # Un encabezado es una frase corta sin punto: «La casa sonambula. Autor: X» es
    # el titulo de un libro y su autor, no un grupo.
    if not grupo.split() or len(grupo.split()) > _PALABRAS_MAXIMAS_DE_ENCABEZADO or "." in grupo:
        return renglon
    nucleo = singular(cabeza(grupo))
    if not nucleo or nucleo in _CLASES_DE_LIBRO:
        return renglon
    # «Editorial: Actualidad. Serie Eficaz.» nombra una coleccion de libros; la
    # editorial suelta («Editorial: McGraw Hill») no pide nada.
    if nucleo == "editorial" and "serie" in resto.split():
        return renglon
    for concepto in conceptos:
        for candidato in [concepto["nombre"], *(concepto["sinonimos"] or [])]:
            palabras = _plano(candidato).split()
            if palabras and singular(palabras[0]) == nucleo:
                return renglon
    return resto


def _misma_cosa(a: str, b: str) -> bool:
    """Si dos palabras nombran la misma cosa, comparando singulares."""
    sa, sb = singular(a), singular(b)
    return sa[:5] == sb[:5] if min(len(sa), len(sb)) >= 5 else sa == sb


# Cuanto pesa el coseno cuando el lexico YA acerto la cabeza. Pequeno y solo
# suma: la fusion nunca hunde un match lexico (hibrido >= lexico), solo desempata
# entre los que aciertan la cabeza usando el significado del resto de la frase.
_APORTE_COSENO = 0.15


def clasificar(
    renglon: str,
    conceptos: list[dict[str, Any]],
    *,
    embedding_renglon: list[float] | None = None,
) -> tuple[uuid.UUID | None, str, float]:
    """A que concepto de NUESTRO catalogo corresponde el renglon.

    Corre contra la tabla `concepto`, no contra ninguna tienda. Esa es la
    unica forma correcta: el papa pide algo y lo primero es mirar si ya
    sabemos que es y si ya lo tenemos. Salir a una tienda antes de haber
    mirado en casa es como no tener catalogo.

    La contencion literal solo cuenta si cae en la CABEZA de la frase, y esa
    condicion arreglo un error que se veia feo: `pompones de colores` y
    `chaquiras de colores` se clasificaban ambos al concepto `colores`, el de
    los lapices de colores, porque la palabra estaba contenida. Ahi `colores`
    es un adjetivo, no lo pedido. Con la cabeza anclada, `pompones` cae en el
    concepto pompones y `chaquiras`, que no tenemos, se reconoce como
    concepto nuevo, que es justo lo que es.

    El canal semantico (OE3) entra por `embedding_renglon`: el vector del
    renglon entrante, que se compara contra `concepto["embedding"]` (el centro
    de los productos del concepto, poblado por `enriquecer`). Solo cuenta cuando
    el lexico ya acerto la cabeza: el coseno SUMA un aporte pequeno para
    desempatar por significado y nunca resta, asi que el hibrido no puede dar
    menos que el lexico solo, que es lo que la tesis afirma. Sin una cabeza
    anclada por el lexico el puntaje es 0 y el renglon queda sin correspondencia.

    Sin `embedding_renglon` la funcion es identica al lexico de siempre, y por
    eso los callers que aun no calculan el vector siguen valiendo.
    """
    mejor_id, mejor_nombre, mejor = None, "", 0.0
    renglon = RANGO_DUREZA.sub(" serie durezas ", _plano(renglon))
    renglon = PAR_DE_ESCUADRAS.sub(" escuadras juego ", renglon)
    renglon = _sin_encabezado_de_grupo(renglon, conceptos)
    nucleo = cabeza(renglon)
    for concepto in conceptos:
        # Recortado en 0: un coseno negativo no es "menos parecido que nada",
        # y dejarlo restaria en las ramas lexicas. Con el modelo de produccion
        # los cosenos medidos no bajan de 0.43, pero la garantia hibrido >=
        # lexico no puede depender de que modelo haya.
        cos = (
            max(0.0, coseno(embedding_renglon, concepto["embedding"]))
            if embedding_renglon is not None and concepto.get("embedding")
            else 0.0
        )
        for candidato in [concepto["nombre"], *(concepto["sinonimos"] or [])]:
            palabras_candidato = _plano(candidato).split()
            en_la_cabeza = bool(nucleo) and any(_misma_cosa(nucleo, w) for w in palabras_candidato[:1])
            # Si el candidato no nombra la cabeza en NINGUNA de sus palabras,
            # no esta hablando de la misma cosa. Sin esta condicion, un
            # concepto de una sola palabra saca 0.5 contra cualquier frase de
            # dos que lo mencione de refilon: `chaquiras de colores` contra
            # `colores` comparte una de dos palabras y se colaba por el
            # umbral. Exigir que la cosa pedida este nombrada es mas claro
            # que subir el umbral, que solo habria movido el problema.
            nombra_la_cabeza = bool(nucleo) and any(_misma_cosa(nucleo, w) for w in palabras_candidato)
            if en_la_cabeza:
                # Acertar la cabeza da el piso, y el resto de la frase decide
                # entre los que la aciertan. Con un 1.0 plano empataban
                # `lapiz` (esfero) y `lapiz colores`, y el empate lo rompia el
                # orden de la tabla, que es como no decidir. Lo que distingue
                # a los lapices de colores de un lapiz es justamente lo que
                # sobra de la frase. El coseno suma, no resta.
                puntaje = min(1.0, 0.6 + 0.4 * _parecido(renglon, candidato) + _APORTE_COSENO * cos)
            elif nombra_la_cabeza:
                puntaje = min(1.0, _parecido(renglon, candidato) + _APORTE_COSENO * cos)
            else:
                puntaje = 0.0
            if puntaje > mejor:
                mejor_id, mejor_nombre, mejor = concepto["id"], concepto["nombre"], puntaje
    return mejor_id, mejor_nombre, mejor
