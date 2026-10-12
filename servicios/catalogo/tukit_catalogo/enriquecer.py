"""Saca empaque, atributos e imagenes de lo que ya se sabe de cada producto.

Tres carencias del catalogo y tres fuentes distintas, ninguna nueva:

- El EMPAQUE y los ATRIBUTOS ya estan escritos en el nombre del producto. No
  hacia falta salir a la red, hacia falta leerlo bien.
- La IMAGEN esta en la ficha de la tienda, y la direccion de esa ficha ya la
  guarda `oferta_tienda.url`.

El empaque es el que rompia el carrito. `producto_canonico.unidades_por_empaque`
estaba en 1 para los 260 productos, asi que pedir doce lapices sumaba doce
cajas. El modelo ya preveia el arreglo:

    unidades_a_comprar = techo(cantidad_pedida / unidades_por_empaque)

pero con el divisor en 1 la formula no hace nada.

La dificultad no es encontrar numeros en el nombre sino saber cual de ellos
cuenta. `Tempera gouache de 12 ml x 12 unidades` tiene dos doces y solo el
segundo multiplica. `Cinta 18mm X5 Metros X10 Unds` tiene tres numeros y solo
el ultimo. La regla que los separa es simple y esta abajo: un `xN` cuenta
empaques salvo que lo siga una unidad de medida.

Uso:

    python -m tukit_catalogo.enriquecer --solo-validar   # que haria
    python -m tukit_catalogo.enriquecer                  # empaque y atributos
    python -m tukit_catalogo.enriquecer --imagenes       # ademas, va a la red
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from . import tiendas
from .embeddings import Embeder, texto_de_producto

# ---------------------------------------------------------------------------
# Vocabularios
# ---------------------------------------------------------------------------

# Palabras que cuentan cosas. Un numero seguido de una de estas es un empaque.
CONTEO = {
    "unidad": "unidad",
    "unidades": "unidad",
    "und": "unidad",
    "unds": "unidad",
    "ud": "unidad",
    "uds": "unidad",
    "u": "unidad",
    "piezas": "unidad",
    "pieza": "unidad",
    "colores": "unidad",
    "color": "unidad",
    "hojas": "hoja",
    "hoja": "hoja",
    "hj": "hoja",
    "hjs": "hoja",
    "pliegos": "pliego",
    "pliego": "pliego",
}

# Palabras que MIDEN. Un numero seguido de una de estas NO es un empaque: es
# cuanto trae, cuanto mide o cuanto pesa una sola unidad. Esta lista es la que
# evita cobrar mil tarros de vinilo por un tarro de mil gramos.
MEDIDA = {
    "g",
    "gr",
    "grs",
    "gramo",
    "gramos",
    "kg",
    "kilo",
    "kilos",
    "ml",
    "cc",
    "l",
    "lt",
    "litro",
    "litros",
    "mm",
    "cm",
    "m",
    "mt",
    "mts",
    "metro",
    "metros",
    "centimetro",
    "centimetros",
    "milimetro",
    "milimetros",
    "pulgada",
    "pulgadas",
    "cms",
    "gramaje",
}

# De mas larga a mas corta: `media carta` contiene `carta`, y si se probara la
# corta primero todo lo de media carta quedaria del doble de grande.
TAMANOS = (
    ("media carta", "media carta"),
    ("medio pliego", "medio pliego"),
    ("cuarto de pliego", "cuarto de pliego"),
    ("un cuarto", "cuarto"),
    ("1/4 de pliego", "cuarto de pliego"),
    ("1/2 pliego", "medio pliego"),
    ("pliego", "pliego"),
    ("1/8", "octavo"),
    ("octavos", "octavo"),
    ("octavo", "octavo"),
    ("oficio", "oficio"),
    ("carta", "carta"),
    ("cuarto", "cuarto"),
    ("tabloide", "tabloide"),
    # `_normalizar` despega la cifra de la letra, asi que `A4` llega como
    # `a 4`. Escrito `a4`, este tamano no se leia nunca.
    ("a 4", "a4"),
    ("a 3", "a3"),
)

# Tamanos que no son de papel. Para un morral o una cartuchera, `Grande` SI
# es el tamano; para un block no significa nada. Van en una tabla aparte y se
# prueban de ultimas, despues de los tamanos escolares y de las medidas en
# centimetros, para que un `Cuaderno Grande Media Carta` quede en media carta
# y no en grande.
TAMANOS_RELATIVOS = (
    ("extragrande", "extragrande"),
    ("pequena", "pequeno"),
    ("pequeno", "pequeno"),
    ("mediana", "mediano"),
    ("mediano", "mediano"),
    ("grande", "grande"),
    ("chica", "pequeno"),
    ("mini", "pequeno"),
)

# En que forma viene la sustancia. Distingue el pegante en barra del liquido,
# que para el colegio no son intercambiables aunque peguen igual.
PRESENTACION = (
    ("dactilar", "dactilar"),
    ("en barra", "barra"),
    ("barra", "barra"),
    ("liquido", "liquido"),
    ("liquida", "liquido"),
    ("en gel", "gel"),
    ("gel", "gel"),
    ("en polvo", "polvo"),
    ("polvo", "polvo"),
    ("spray", "spray"),
    ("aerosol", "spray"),
    # Para el colegio un tarro y un frasco son lo mismo (decision del
    # 2026-10-11): se leen igual para que ninguno deje fuera al otro.
    ("tarro", "frasco"),
    ("frasco", "frasco"),
    ("pomo", "frasco"),
    ("tubo", "tubo"),
    ("pastilla", "pastilla"),
    ("crema", "crema"),
    ("bolsa", "bolsa"),
    ("paquete", "paquete"),
    ("sobre", "sobre"),
)

# De que esta hecho. Importa cuando el colegio exige plastico por seguridad o
# madera por durabilidad.
MATERIAL = (
    # `acero inoxidable` antes que nada: el colegio pide la regla de acero
    # para el dibujo tecnico, y una de plastico no le sirve (Septimo, #31).
    ("acero inoxidable", "acero"),
    # La bata y el delantal antifluido: el colegio lo pide por nombre y una
    # bata de tela no le sirve.
    ("antifluido", "antifluido"),
    ("acero", "acero"),
    ("acrilico", "acrilico"),
    ("plastico", "plastico"),
    ("plastica", "plastico"),
    ("madera", "madera"),
    ("metalico", "metal"),
    ("metalicos", "metal"),
    ("metal", "metal"),
    ("nitrilo", "nitrilo"),
    ("latex", "latex"),
    ("caucho", "caucho"),
    ("silicona", "silicona"),
    ("icopor", "icopor"),
    ("foamy", "foamy"),
    ("carton", "carton"),
    ("tela", "tela"),
    ("vidrio", "vidrio"),
    ("aluminio", "aluminio"),
    ("madeflex", "madera"),
)

# `tipo` es la clave mas pedida (30 conceptos) y la mas dispar: para una cinta
# significa transparente o de enmascarar, para un crayon jumbo o delgado, para
# un block cuadriculado o de origami.
#
# Se usa un vocabulario unico de terminos DISTINTIVOS en vez de uno por
# concepto. La apuesta es por la precision: cada termino de esta lista solo
# aparece en nombres donde de verdad significa el tipo, asi que un falso
# positivo es improbable. Lo que se pierde es cobertura, y esa es la
# direccion correcta del error: el resolutor prefiere no saber a creer mal.
TIPOS = (
    # La clase de pintura va primero: `Pintura al oleo, verde permanente` es
    # un oleo, y `permanente` ahi es el nombre del color. Un acrilico no se
    # reemplaza por un oleo (Septimo pedia acrilicos y el kit daba oleos).
    ("acrilico", "acrilico"),
    ("acrilica", "acrilico"),
    ("oleo", "oleo"),
    ("vinilo", "vinilo"),
    ("tempera", "tempera"),
    ("acuarela", "acuarela"),
    ("doble faz", "doble faz"),
    ("enmascarar", "enmascarar"),
    ("transparente", "transparente"),
    ("aislante", "aislante"),
    ("quirurgico", "quirurgico"),
    # Antes de `argollado`: un `cuaderno de dibujo argollado` es de dibujo.
    ("de dibujo", "dibujo"),
    # Lo que la auditoria del Agustiniano encontro pedido y sin leer.
    ("gigante", "gigante"),
    ("rodachines", "con ruedas"),
    ("de ruedas", "con ruedas"),
    ("panuelos faciales", "panuelo"),
    ("panuelo", "panuelo"),
    ("pincho", "pincho"),
    ("celofan", "celofan"),
    ("lija", "lija"),
    ("para colorear", "colorear"),
    ("por numeros", "por numeros"),
    ("puntas intercambiables", "intercambiable"),
    ("intercambiable", "intercambiable"),
    ("loza", "loza"),
    # Los jumpers se piden por sus dos puntas, y uno macho-macho no sirve donde
    # piden hembra. Da igual en que orden se nombren.
    ("macho-macho", "macho-macho"),
    ("macho - macho", "macho-macho"),
    ("macho-hembra", "macho-hembra"),
    ("macho - hembra", "macho-hembra"),
    ("hembra-macho", "macho-hembra"),
    ("hembra - macho", "macho-hembra"),
    ("hembra-hembra", "hembra-hembra"),
    ("hembra - hembra", "hembra-hembra"),
    # La punta (`punta fina`, `punta roma`) ya no vive aqui: tiene su tabla,
    # PUNTAS. Compartirla hacia que un marcador permanente declarara
    # `punta=permanente` y uno de punta fina `tipo=punta fina`.
    ("permanente", "permanente"),
    ("borrable", "borrable"),
    ("lavable", "lavable"),
    ("milimetrado", "milimetrado"),
    ("cuadriculado", "cuadriculado"),
    ("cuadriculada", "cuadriculado"),
    ("ferrocarril", "ferrocarril"),
    ("doble linea", "doble linea"),
    # Como el colegio pide un block: `a rayas`, `de hojas blancas`.
    ("a rayas", "rayado"),
    ("rayado", "rayado"),
    ("rayada", "rayado"),
    ("hojas blancas", "blanco"),
    ("sin rayas", "blanco"),
    ("block blanco", "blanco"),
    ("origami", "origami"),
    ("iris", "iris"),
    ("kraft", "kraft"),
    ("bond", "bond"),
    ("propalcote", "propalcote"),
    ("cartulina", "cartulina"),
    ("jumbo", "jumbo"),
    ("triangular", "triangular"),
    ("hexagonal", "hexagonal"),
    ("vertical", "vertical"),
    ("horizontal", "horizontal"),
    ("de nata", "nata"),
    ("miga de pan", "miga de pan"),
    ("retractil", "retractil"),
    ("argollado", "argollado"),
    ("cosido", "cosido"),
    ("legajador", "legajador"),
    ("mariposa", "mariposa"),
    ("examen", "examen"),
    # Terminos que resultaron de mirar los conceptos donde NINGUN producto
    # lograba cumplir el atributo exigido. No se inventaron: cada uno aparece
    # literal en los nombres de esos productos.
    ("futbol de salon", "futbol de salon"),
    ("microfutbol", "futbol de salon"),
    ("baloncesto", "baloncesto"),
    ("voleibol", "voleibol"),
    ("futbol", "futbol"),
    ("cientifica", "cientifica"),
    ("de escritorio", "de escritorio"),
    ("basica", "basica"),
    # `dulce` antes que `soprano`: dulce es el instrumento y soprano la voz. Una
    # "Flauta Dulce Soprano" quedaba `soprano` y la lista que pide "flauta dulce"
    # (la escolar de siempre) no encontraba ninguna.
    ("dulce", "dulce"),
    ("soprano", "soprano"),
    ("traversa", "traversa"),
    ("precision", "precision"),
    ("fuelle", "fuelle"),
    ("con ruedas", "con ruedas"),
    ("universitario", "universitario"),
    ("morral", "morral"),
    ("montessori", "montessori"),
    ("rompecabezas", "rompecabezas"),
    ("celuguia", "celuguia"),
    # Palitos: el de paleta (helado) no es la varilla de balso de maquetas.
    # Se escribe con la frase entera porque `paleta` sola es tambien la de
    # mezclar pintura.
    ("palos de paleta", "paleta"),
    ("palo de paleta", "paleta"),
    ("palitos de paleta", "paleta"),
    ("para paleta", "paleta"),
    ("balso", "balso"),
    # Una toalla es de tela; los panitos y toallitas son humedos. El humedo
    # va antes para que `toalla humeda` no quede en tela.
    ("humeda", "humeda"),
    ("humedo", "humeda"),
    ("panitos", "humeda"),
    ("toallitas", "humeda"),
    ("toalla de papel", "papel"),
    ("toalla", "tela"),
    ("vaso", "vaso"),
    ("plato", "plato"),
    ("fotografico", "fotografico"),
    # El block de dibujo: `Sketch Book`, `para bocetos`. Va despues de
    # `argollado` y `cuadriculado`, que si lo dicen son mas especificos.
    ("sketch book", "dibujo"),
    ("sketchbook", "dibujo"),
    ("bocetos", "dibujo"),
    # `escolar` va de ultimo a proposito: aparece en medio catalogo y como
    # tipo dice poquisimo, asi que solo gana cuando no hay nada mejor.
    ("escolar", "escolar"),
)

# El acabado de un papel, un foamy o una pintura. Tenia que tener tabla propia:
# leido con TIPOS, el de una tempera fluorescente era `tempera` (la clase de
# pintura va primero alli) y el de una cartulina fluorescente, `cartulina`.
ACABADOS = (
    ("fluorescente", "fluorescente"),
    ("fluorecente", "fluorescente"),  # asi lo escriben varias tiendas
    ("escarchado", "escarchado"),
    ("escarchada", "escarchado"),
    ("metalizado", "metalizado"),
    ("metalizada", "metalizado"),
    ("iris", "iris"),
    # No es un acabado, pero es lo que distingue un paquete de figuras de foamy
    # (J#49) de las laminas lisas, y el foamy solo tiene esta dimension libre.
    ("figuras", "figuras"),
)

# Las tiendas concuerdan el color con el genero del producto: la cartulina es
# `Negra` y el marcador es `Negro`. Buscar solo el masculino dejaba sin color
# a todo lo femenino, que es medio catalogo (cartulina, cinta, tempera).
COLORES = (
    # `de colores` es como el colegio pide el surtido: `octavos de carton
    # paja de colores` no es el carton crema (Septimo, #68).
    ("de colores", "surtido"),
    ("colores", "surtido"),
    ("surtido", "surtido"),
    ("surtida", "surtido"),
    ("surtidos", "surtido"),
    ("surtidas", "surtido"),
    ("multicolor", "surtido"),
    ("blanco", "blanco"),
    ("blanca", "blanco"),
    ("negro", "negro"),
    ("negra", "negro"),
    ("rojo", "rojo"),
    ("roja", "rojo"),
    ("azul", "azul"),
    ("verde", "verde"),
    ("amarillo", "amarillo"),
    ("amarilla", "amarillo"),
    ("naranja", "naranja"),
    ("morado", "morado"),
    ("morada", "morado"),
    ("violeta", "violeta"),
    ("rosado", "rosado"),
    ("rosada", "rosado"),
    ("rosa", "rosado"),
    ("cafe", "cafe"),
    ("gris", "gris"),
    ("dorado", "dorado"),
    ("dorada", "dorado"),
    ("plateado", "plateado"),
    ("plateada", "plateado"),
    ("fucsia", "fucsia"),
    ("turquesa", "turquesa"),
    ("beige", "beige"),
    ("vinotinto", "vinotinto"),
    ("celeste", "celeste"),
    ("neon", "neon"),
    ("crema", "crema"),
    ("kraft", "kraft"),
    # Los primarios de la pintura (cian, magenta, amarillo): sin ellos un
    # acrilico magenta no declaraba color y no se podia exigir.
    ("oro", "dorado"),
    ("purpura", "morado"),
    ("cian", "cian"),
    ("cyan", "cian"),
    ("magenta", "magenta"),
)

# La punta de un marcador o de unas tijeras. Es la forma del extremo, no la
# clase de tinta, y por eso no comparte tabla con TIPOS.
PUNTAS = (
    ("micropunta", "micropunta"),
    ("punta roma", "punta roma"),
    # Asi, junto, lo escribe la lista de Jardin (J#62).
    ("puntaroma", "punta roma"),
    ("punta fina", "punta fina"),
    ("punta extrafina", "punta fina"),
    ("punta delgada", "punta fina"),
    ("punta gruesa", "punta gruesa"),
    ("punta pincel", "punta pincel"),
    ("punta biselada", "punta biselada"),
    ("punta bala", "punta bala"),
    # `marcadores delgados` es como las listas piden la punta fina, y asi se
    # llaman los productos (`Plumones delgados Keyroad`).
    ("delgado", "punta fina"),
    ("grueso", "punta gruesa"),
)

# Como esta armado el cuaderno. Cosido y argollado no se sustituyen: el
# colegio pide cosido para que no se arranquen hojas. `sin espiral` es como
# muchas listas dicen cosido; `cocido` es la errata mas frecuente del corpus.
ENCUADERNACIONES = (
    ("sin espiral", "cosido"),
    ("sin argolla", "cosido"),
    ("cosido", "cosido"),
    ("cocido", "cosido"),
    ("argollado", "argollado"),
    ("anillado", "argollado"),
    ("espiral", "argollado"),
)

# Lo que convierte una Biblia en una seleccion para ninos. Sin una de estas,
# una Biblia es la completa: el colegio que pide `Biblia catolica` no quiere
# `Lecturas de la Biblia para ninos` (Septimo, #1). `nios` y `nias` son como
# una tienda escribio `ninos` y `ninas` al perder la enie.
_BIBLIA_INFANTIL = re.compile(
    r"\b(?:ninos?|ninas?|nios|nias|infantil(?:es)?|mi primera|"
    r"(?:lecturas|historias|relatos) de la biblia)\b"
)
# Senales de que el paquete trae varios colores y no varias veces el mismo.
# Sin una de estas, `x12 unidades` puede ser una docena de marcadores negros.
# `fluorescente` no entra. En Osito de Miel, "vinilo escolar fluorescente
# x 6" es un solo color con acabado fluorescente, y contarlo como surtido
# hacia que el 6 del empaque se volviera `colores=6`. Ningun vinilo del
# catalogo declara seis colores, asi que el renglon se abstenia teniendo
# el producto a la vista.
MULTICOLOR = ("surtido", "surtida", "surtidos", "surtidas", "multicolor", "neon", "pastel")


# Personajes y marcas de licencia que aparecen en la papeleria colombiana.
#
# El personaje es ORTOGONAL al nivel, y esa es la razon de que viva en su
# propia columna en vez de ser un atributo mas. Un cuaderno de Spiderman no es
# un cuaderno mejor: es el mismo cuaderno con una portada por la que el nino
# insiste y el papa paga un sobreprecio. Separarlos permite las dos cosas que
# el kit necesita hacer: ofrecer la version con personaje a quien la quiere, y
# calcular cuanto cuesta exactamente ese gusto frente a la version lisa.
#
# La lista se escribe a mano porque no hay forma de deducirla. `Halo` y
# `Cars` son palabras comunes en espanol y en ingles, y solo el contexto de
# una lista escolar colombiana dice que aqui son franquicias.
PERSONAJES = (
    ("paw patrol", "Paw Patrol"),
    ("hello kitty", "Hello Kitty"),
    ("my melody", "My Melody"),
    ("minnie mouse", "Minnie Mouse"),
    ("mickey mouse", "Mickey Mouse"),
    ("spiderman", "Spiderman"),
    ("spider man", "Spiderman"),
    ("avengers", "Avengers"),
    ("minecraft", "Minecraft"),
    ("frozen", "Frozen"),
    ("barbie", "Barbie"),
    ("bluey", "Bluey"),
    ("stitch", "Stitch"),
    ("snoopy", "Snoopy"),
    ("bambi", "Bambi"),
    ("batman", "Batman"),
    ("superman", "Superman"),
    ("harry potter", "Harry Potter"),
    ("star wars", "Star Wars"),
    ("mandaloriano", "Star Wars"),
    ("hot wheels", "Hot Wheels"),
    ("peppa pig", "Peppa Pig"),
    ("pikachu", "Pokemon"),
    ("pokemon", "Pokemon"),
    ("naruto", "Naruto"),
    ("sonic", "Sonic"),
    ("mario bros", "Mario Bros"),
    ("unicornio", "Unicornio"),
    ("dinosaurio", "Dinosaurios"),
    ("halo", "Halo"),
    ("lego", "Lego"),
    ("kiut", "Kiut"),
    ("totto", "Totto"),
    ("cars", "Cars"),
    # `disney` es un paraguas, no una franquicia: va de ULTIMO a proposito, para
    # que un "Morral Disney Frozen" lo reclame Frozen (mas arriba) y solo caiga
    # en Disney lo que no dice otra cosa mas especifica.
    ("disney", "disney"),
)


def extraer_personaje(nombre: str) -> str | None:
    """El personaje de la portada, o None si el producto es liso.

    Se recorre la lista en orden y gana el primero, que por eso esta ordenada
    de nombre largo a corto: `Minnie Mouse` antes que `Mickey Mouse` no
    importa, pero `mandaloriano` tiene que llegar antes de que nada mas
    reclame ese producto para otra franquicia.
    """
    plano = _normalizar(nombre)
    for aguja, valor in PERSONAJES:
        if re.search(rf"\b{re.escape(aguja)}\b", plano):
            return valor
    return None


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _normalizar(texto: str) -> str:
    """Minusculas, sin tildes y con las cifras despegadas de las letras.

    Las tiendas escriben `X10Unds`, `x12ml` y `27x37cm` sin espacios, asi que
    sin este paso las expresiones regulares tendrian que contemplar cada
    variante de separacion.
    """
    plano = _sin_tildes(texto.lower())
    plano = re.sub(r"(\d)([a-z])", r"\1 \2", plano)
    plano = re.sub(r"([a-z])(\d)", r"\1 \2", plano)
    return re.sub(r"\s+", " ", plano.replace(",", "."))


# ---------------------------------------------------------------------------
# Empaque
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Empaque:
    unidades: int
    unidad_base: str


# `x 12 unidades`, `X10 Unds`, `por 5 hojas`, `x25`.
#
# La parte decimal se captura aunque no se use como cifra, porque su sola
# presencia ya descarta el empaque: `30,5 x 30,5 cm` son centimetros y no
# treinta acetatos. Nadie empaca media unidad.
#
# El punto y la coma cuentan como separador validos delante de la `x` porque
# las tiendas escriben `Resaltadores..neon.x5`, y exigir un espacio dejaba ese
# paquete de cinco contado como uno.
_CANTIDAD = re.compile(r"(?:^|[\s(.,\-])(?:x|por)\s*(\d{1,4})(\.\d+)?\s*([a-z]+)?")

# `Paquete De 12`, `Caja de 24`, `Set de 15`: el mismo empaque sin la `x`.
_EMPAQUE_ESCRITO = re.compile(r"\b(?:paquete|caja|set|juego|bolsa|blister|kit)\s+de\s+(\d{1,4})\b")


def extraer_empaque(nombre: str, atributos_del_concepto: tuple[str, ...] = ()) -> Empaque:
    """Cuantas unidades trae el producto, y en que se cuentan.

    La regla, en una linea: `xN` cuenta empaques salvo que lo siga una unidad
    de medida.

    Eso resuelve los tres nombres que mas cuestan:

    - `x1000 Gramos`  -> medida, no son mil tarros
    - `X5 Metros`     -> medida, no son cinco rollos
    - `X10 Unds`      -> conteo, si son diez

    Queda un caso que la regla sola no puede decidir, y es `N hojas`. Cien
    hojas de un cuaderno son una propiedad del cuaderno; cinco hojas de
    acetato son cinco cosas. La misma palabra significa lo contrario segun que
    producto sea, asi que lo decide el concepto: si declara `hojas` entre sus
    `atributos_discriminantes`, las hojas describen y no cuentan.
    """
    plano = _normalizar(nombre)
    hojas_son_atributo = "hojas" in atributos_del_concepto

    mejor: Empaque | None = None
    for coincidencia in _CANTIDAD.finditer(plano):
        cantidad = int(coincidencia.group(1))
        palabra = coincidencia.group(3) or ""

        if coincidencia.group(2):
            continue  # tiene decimales: es una medida
        if palabra in MEDIDA:
            continue  # es cuanto trae o cuanto mide, no cuantos son
        if palabra and palabra not in CONTEO:
            # Una palabra que no cuenta ni mide: `x100 Gigante`. El numero
            # sigue siendo el empaque, porque `x` delante de una cifra sin
            # unidad es como las tiendas escriben la cantidad.
            palabra = ""
        if palabra in ("hojas", "hoja", "hj", "hjs") and hojas_son_atributo:
            continue

        unidad = CONTEO.get(palabra, "unidad")
        if cantidad < 1:
            continue
        # Con varios candidatos gana el mayor: en `x 12 ml x 12 unidades` da
        # igual, pero en nombres con un `x2` de presentacion y un `x24` de caja
        # el empaque real es el grande.
        if mejor is None or cantidad > mejor.unidades:
            mejor = Empaque(cantidad, unidad)

    escrito = _EMPAQUE_ESCRITO.search(plano)
    if escrito and (mejor is None or int(escrito.group(1)) > mejor.unidades):
        mejor = Empaque(int(escrito.group(1)), "unidad")

    if mejor is None and re.search(r"\bdocena\b", plano):
        # `Docena Barra Silicona Gruesa` (J#93) se compraba de a una barra.
        mejor = Empaque(6 if re.search(r"\bmedia docena\b", plano) else 12, "unidad")

    if mejor is not None:
        return mejor

    # Sin `x` ni `por`: puede seguir habiendo un conteo suelto, como
    # `Block cuadriculado de 50 hojas`.
    if not hojas_son_atributo:
        suelto = re.search(r"(?:^|\s)(\d{1,4})\s+(hojas?|pliegos?|unidades)\b", plano)
        if suelto:
            return Empaque(int(suelto.group(1)), CONTEO.get(suelto.group(2), "unidad"))

    return Empaque(1, "unidad")


# ---------------------------------------------------------------------------
# Atributos
# ---------------------------------------------------------------------------


# Los idiomas de un diccionario. Un bilingue no es un monolingue: es otro
# libro, a otro precio, y el colegio lo pide escrito ("de ingles y frances").
IDIOMAS = (
    ("espanol", "espanol"),
    ("castellano", "espanol"),
    ("ingles", "ingles"),
    ("english", "ingles"),
    ("frances", "frances"),
    ("aleman", "aleman"),
    ("latin", "latin"),
)

# Para saber si un diccionario es monolingue se cuentan las menciones de
# idioma, y las tiendas los escriben tambien en ingles: `english-spanish`.
_IDIOMAS_DE_DICCIONARIO = (*IDIOMAS, ("spanish", "espanol"), ("french", "frances"))

# La forma de la cerda de un pincel o de la punta de un instrumento. Vive
# aparte de TIPOS porque `plano` y `redondo` no describen la clase de objeto
# sino su silueta, y mezclarlos hacia que `Pincel redondo` no leyera nada.
FORMAS = (
    # `triangular` y `hexagonal` estaban en TIPOS y al mudar `forma` a su
    # propia tabla se quedaron fuera: `Lapiz triangular` dejo de leerse, y el
    # corpus lo pide 17 veces. Un vocabulario nuevo tiene que cubrir lo que
    # cubria el que reemplaza.
    ("triangular", "triangular"),
    ("hexagonal", "hexagonal"),
    ("ergonomico", "ergonomico"),
    ("redondo", "redondo"),
    ("redonda", "redondo"),
    ("plano", "plano"),
    ("plana", "plano"),
    ("biselado", "biselado"),
    ("lengua de gato", "lengua de gato"),
    ("abanico", "abanico"),
    ("espatulado", "espatulado"),
    ("cuadrado", "cuadrado"),
    ("rectangular", "rectangular"),
)

# Como esta rayada la hoja. Es lo que un colegio escribe de un cuaderno casi
# siempre, y el orden importa: las variantes con medida van primero para que
# `cuadriculado 1 cm` no se resuelva como `cuadriculado` a secas, que es otro
# cuaderno y para un nino de primero no da igual.
RAYADOS = (
    ("cuadricula grande", "cuadricula grande"),
    ("cuadricula pequena", "cuadricula pequena"),
    ("doble linea", "doble linea"),
    ("triple linea", "triple linea"),
    ("ferrocarril", "ferrocarril"),
    ("milimetrado", "milimetrado"),
    ("cuadriculado", "cuadriculado"),
    ("cuadriculada", "cuadriculado"),
    ("cuadros", "cuadriculado"),
    ("cuadriculas", "cuadriculado"),
    ("rayado", "rayado"),
    ("rayada", "rayado"),
    ("renglon", "rayado"),
    ("lineas", "rayado"),
    ("rayas", "rayado"),
    ("cuadrovia", "cuadrovia"),
    ("pentagramado", "pentagramado"),
    ("blanco", "blanco"),
    ("blanca", "blanco"),
    ("sin rayas", "blanco"),
    # Aqui estaba `cuadriculado grande -> cuadricula grande`, y no ganaba
    # nunca porque `cuadriculado` iba antes. Se quito al leer el rayado por
    # la coincidencia mas larga, que lo habria activado: en las listas
    # `cuaderno cuadriculado grande` es un cuaderno GRANDE, no de cuadro
    # grande, y exigirlo dejaba sin cuaderno a Septimo.
)

# Lo que gradua un pincel o una mina. Va aparte de TAMANOS_RELATIVOS porque
# un pincel `grueso` no es un pincel `grande`: lo grueso es la cerda.
GROSORES = (
    ("extra grueso", "extra grueso"),
    # Un lapiz o un color jumbo es el grueso de las listas de preescolar.
    ("jumbo", "grueso"),
    ("muy grueso", "extra grueso"),
    ("grueso", "grueso"),
    ("gruesa", "grueso"),
    ("mediano", "mediano"),
    ("mediana", "mediano"),
    ("delgado", "delgado"),
    ("delgada", "delgado"),
    ("fino", "delgado"),
    ("fina", "delgado"),
    ("pequeno", "pequeno"),
    ("pequena", "pequeno"),
)

# La escala de grafito. Se escribe pegada al numero (`2B`, `HB`, `4H`) y hay
# que distinguirla de la escala comercial del lapiz (`lapiz n 2`), que usa el
# mismo digito para decir otra cosa.
_DUREZA = re.compile(r"\b(\d?[hb]{1,2})\b")
_DUREZAS_VALIDAS = frozenset(
    {"h", "b", "hb", "hh", "bb"} | {f"{n}{letra}" for n in range(2, 10) for letra in "hb"}
)

# Los numeros como los escribe una lista: `cuaderno tres materias`.
_NUMEROS_ESCRITOS = {
    "una": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "diez": 10,
}

# Cuantos huecos o bolsillos trae algo que los cuenta. El colegio no escribe
# `2`: escribe `doble servicio`, `doble`, `sencillo`.
_CUANTOS_ESCRITOS = (
    ("cuadruple", 4),
    ("triple", 3),
    ("doble", 2),
    ("dos", 2),
    ("sencillo", 1),
    ("sencilla", 1),
    ("simple", 1),
    ("individual", 1),
)


def _cuantos_huecos(plano: str, palabras: tuple[str, ...]) -> int | None:
    """Cuantos compartimentos, orificios o bolsillos declara el texto."""
    numerado = re.search(rf"(\d{{1,2}})\s*(?:{'|'.join(palabras)})\b", plano)
    if numerado:
        return int(numerado.group(1))
    for aguja, cuantos in _CUANTOS_ESCRITOS:
        if re.search(rf"\b{aguja}\b", plano):
            return cuantos
    return None


def _coincidencias(plano: str, tabla: tuple[tuple[str, str], ...]) -> list[tuple[str, re.Match[str]]]:
    """Los valores de `tabla` que nombra el texto, cada uno con donde aparece.

    Las coincidencias se toman de la mas larga a la mas corta y una que se
    monta sobre otra ya tomada no cuenta: `doble linea` es un rayado, no
    `doble linea` mas `linea`. El plural se admite porque las listas
    escriben `cuadernos cosidos` y `marcadores acrilicos`.
    """
    halladas: list[tuple[str, re.Match[str]]] = []
    for aguja, valor in tabla:
        # El plural en `s` y en `es`: `marcadores acrilicos`, `colores triangulares`.
        for m in re.finditer(rf"\b{re.escape(aguja)}(?:s|es)?\b", plano):
            halladas.append((valor, m))
    halladas.sort(key=lambda par: par[1].end() - par[1].start(), reverse=True)

    tomadas: list[tuple[str, re.Match[str]]] = []
    for valor, m in halladas:
        if all(m.end() <= otra.start() or m.start() >= otra.end() for _, otra in tomadas):
            tomadas.append((valor, m))
    return tomadas


def _valor_unico(plano: str, tabla: tuple[tuple[str, str], ...]) -> tuple[str, re.Match[str]] | None:
    """El unico valor de `tabla` que nombra el texto, o None si nombra cero o varios.

    Es para los atributos de UNA dimension (color, forma, rayado...). Un
    renglon que enumera varios valores pide un surtido, y exigir el primero
    de la tabla era exigir lo contrario: `pinceles planos, redondos y
    abanico` pedia solo planos.
    """
    tomadas = _coincidencias(plano, tabla)
    if len({valor for valor, _ in tomadas}) != 1:
        return None
    return tomadas[0]


def atributos_ambiguos(texto: str, requeridos: tuple[str, ...]) -> list[str]:
    """Los atributos que el renglon nombra con varios valores y por eso no exige.

    Son los que una persona tiene que mirar: `cuaderno rayado o cuadriculado`
    no se le puede pedir a ningun producto, pero tampoco es un renglon sin
    rayado. Que el filtro no lo exija evita un hueco falso; que quede marcado
    evita que el silencio pase por respuesta.
    """
    plano = _normalizar(texto)
    leidos = extraer_atributos(texto, requeridos)
    return [
        atributo
        for atributo in requeridos
        if atributo in _TABLAS_DE_UNA_DIMENSION
        and atributo not in leidos
        and len({valor for valor, _ in _coincidencias(plano, _TABLAS_DE_UNA_DIMENSION[atributo])}) > 1
    ]


# Los atributos de una sola dimension: los que la regla del valor unico cubre.
_TABLAS_DE_UNA_DIMENSION: dict[str, tuple[tuple[str, str], ...]] = {
    "color": COLORES,
    "forma": FORMAS,
    "rayado": RAYADOS,
    "material": MATERIAL,
    "punta": PUNTAS,
    "presentacion": PRESENTACION,
    "encuadernacion": ENCUADERNACIONES,
    "grosor": GROSORES,
}


def extraer_atributos(nombre: str, requeridos: tuple[str, ...]) -> dict[str, Any]:
    """Lee del nombre solo los atributos que el concepto declara necesitar.

    Dos decisiones que parecen timidas y no lo son.

    La primera: se devuelve unicamente lo pedido. Los atributos son el
    contrato con el resolutor, y meterle todo lo legible convierte cada
    comparacion en ruido.

    La segunda: si no se puede leer, la clave no aparece. Nunca `desconocido`,
    nunca el valor mas frecuente. Un atributo inventado es peor que uno
    ausente: si el catalogo afirma `tamano: oficio` sobre algo que es carta, el
    resolutor lo elige con confianza y el papa recibe el tamano equivocado.
    Ausente, el renglon se va a revision, que es lo correcto.
    """
    plano = _normalizar(nombre)
    attrs: dict[str, Any] = {}

    for pedido in requeridos:
        if pedido == "tamano":
            for aguja, valor in TAMANOS:
                # Con el plural: las listas piden `cuartos de cartulina` y
                # `pliegos de papel`, y sin la `s` no se leia ninguno.
                if re.search(rf"\b{re.escape(aguja)}s?\b", plano):
                    attrs["tamano"] = valor
                    break
            else:
                # Sin tamano escolar, unas medidas en centimetros tambien
                # dicen de que tamano es: `Bloc origami (15 x 15 cm)`.
                medidas = re.search(r"(\d{1,3}(?:\.\d+)?)\s*x\s*(\d{1,3}(?:\.\d+)?)\s*cms?\b", plano)
                if medidas:
                    attrs["tamano"] = (
                        f"{_entero_si_cabe(medidas.group(1))} x {_entero_si_cabe(medidas.group(2))} cm"
                    )
                else:
                    # Ultimo recurso: para un morral o una cartuchera,
                    # `Grande` SI es el tamano. Va despues de todo lo demas
                    # para que `Cuaderno Grande Media Carta` quede en media
                    # carta, que es lo que el colegio escribio.
                    for aguja, valor in TAMANOS_RELATIVOS:
                        if re.search(rf"\b{aguja}\b", plano):
                            attrs["tamano"] = valor
                            break

        elif pedido == "color":
            # El plural admitido por lo mismo que en la tinta: las listas
            # escriben `carpetas rojas`, no `carpeta roja`.
            unico = _valor_unico(plano, COLORES)
            if unico:
                attrs["color"] = unico[0]
            elif re.search(r"\b(?:surtid[oa]s?|multicolor|de colores)\b", plano):
                # Varios colores y ademas `surtido`: el nombre ya dijo que
                # es un surtido, y eso si se puede afirmar.
                attrs["color"] = "surtido"

        elif pedido == "rayado":
            unico = _valor_unico(plano, RAYADOS)
            if unico:
                valor, m = unico
                # Si el rayado viene con medida, la medida es parte del
                # rayado: un cuadriculado de 1 cm y uno de 5 mm no se
                # sustituyen entre si en un cuaderno de primaria.
                medida = re.match(r"\s*(?:de\s*)?(\d{1,2}(?:\.\d)?)\s*(mm|cm)\b", plano[m.end() :])
                attrs["rayado"] = (
                    f"{valor} {_entero_si_cabe(medida.group(1))} {medida.group(2)}" if medida else valor
                )

        elif pedido == "idioma":
            hallados = [v for a, v in IDIOMAS if re.search(rf"\b{a}\b", plano)]
            if hallados:
                # Se unen en vez de quedarse con el primero: `diccionario de
                # ingles y frances` es un bilingue, y darlo por ingles a
                # secas lo confunde con otro libro y otro precio.
                # En orden alfabetico: `ingles - espanol` y `espanol - ingles`
                # son el mismo diccionario, y en el orden en que se escribieron
                # no se reconocian entre si.
                distintos = sorted(set(hallados))
                menciones = [v for a, v in _IDIOMAS_DE_DICCIONARIO for _ in re.finditer(rf"\b{a}\b", plano)]
                if len(distintos) == 1 and (re.search(r"\bmonolingue\b", plano) or len(menciones) >= 2):
                    # `Ingles - Ingles`: el monolingue, dicho a proposito. Se
                    # escribe doble para no confundirlo con `de ingles` a secas,
                    # que en una lista suele ser el bilingue con espanol.
                    attrs["idioma"] = f"{distintos[0]}-{distintos[0]}"
                else:
                    attrs["idioma"] = "-".join(distintos)

        elif pedido == "deposito":
            # Solo se afirma cuando el texto lo dice. Un tajalapiz que no
            # menciona deposito puede tenerlo: callar es correcto, decir que
            # no lo tiene es inventarse una ausencia.
            if re.search(r"\bsin deposito\b", plano):
                attrs["deposito"] = False
            elif re.search(r"\b(?:con )?(?:deposito|portabasura)\b", plano):
                attrs["deposito"] = True

        elif pedido in ("orificios", "compartimentos"):
            palabras = {
                "orificios": ("orificios?", "huecos?", "entradas?"),
                "compartimentos": ("compartimentos?", "bolsillos?", "servicios?", "cierres?"),
            }[pedido]
            cuantos = _cuantos_huecos(plano, palabras)
            if cuantos is not None:
                attrs[pedido] = cuantos

        elif pedido == "grosor":
            unico = _valor_unico(plano, GROSORES)
            if unico:
                attrs["grosor"] = unico[0]
            else:
                # La serie numerica del pincel, cuando no hay palabra. Se
                # guarda con prefijo para que no se confunda con una medida
                # y para que quede claro que es una escala de marca.
                serie = re.search(r"(?:\bn\s*[o°]?\s*|#\s*)(\d{1,2})\b", plano)
                if serie:
                    attrs["grosor"] = f"n{int(serie.group(1))}"

        elif pedido == "dureza":
            # Sobre el texto pegado y no sobre `plano`: `_normalizar` separa
            # las cifras de las letras para poder leer `x12ml`, y de paso
            # convierte `2B` en `2 b`, con lo que la escala de grafito se
            # partia en dos y quedaba en `b`. Una mina 2B no es una B.
            # Con dos durezas distintas (`2H-6B`) es una serie, no una mina:
            # exigir la primera dejaba sin opcion al renglon.
            durezas = {c for c in _DUREZA.findall(_sin_tildes(nombre.lower())) if c in _DUREZAS_VALIDAS}
            if len(durezas) == 1:
                attrs["dureza"] = durezas.pop()

        elif pedido == "tinta":
            # La tinta de un esfero es el color que el colegio escribe:
            # `Lapicero Negro` no habla del plastico del tubo. Se reusa la
            # tabla de colores porque es el mismo vocabulario.
            # Con el plural admitido: el renglon del corpus es `esferos rojos
            # y negros`, y exigir el singular no leia ninguno de los dos.
            encontrados = [v for a, v in COLORES if re.search(rf"\b{a}s?\b", plano)]
            if len(set(encontrados)) > 1:
                # `esferos rojos y negros` es un renglon que pide los dos.
                attrs["tinta"] = "surtido"
            elif encontrados:
                attrs["tinta"] = encontrados[0]

        elif pedido == "acabado":
            for aguja, valor in ACABADOS:
                if re.search(rf"\b{re.escape(aguja)}(?:s|es)?\b", plano):
                    attrs["acabado"] = valor
                    break

        elif pedido == "tipo":
            # `tipo` mezcla dimensiones (`Block cuadriculado argollado` dice
            # dos tipos y los dos son ciertos), asi que aqui no aplica la
            # regla del valor unico: gana el primero de la tabla, que esta
            # ordenada del termino mas especifico al menos.
            for aguja, valor in TIPOS:
                if re.search(rf"\b{re.escape(aguja)}(?:s|es)?\b", plano):
                    attrs["tipo"] = valor
                    break

        elif pedido in ("presentacion", "material", "forma", "punta", "encuadernacion"):
            tabla = {
                "presentacion": PRESENTACION,
                "material": MATERIAL,
                "forma": FORMAS,
                "punta": PUNTAS,
                "encuadernacion": ENCUADERNACIONES,
            }[pedido]
            unico = _valor_unico(plano, tabla)
            if unico:
                attrs[pedido] = unico[0]

        elif pedido == "edicion":
            if _BIBLIA_INFANTIL.search(plano):
                attrs["edicion"] = "infantil"
            elif re.search(r"\bbiblia\b", plano):
                attrs["edicion"] = "completa"

        elif pedido == "monolingue":
            # Se cuentan las menciones, no los idiomas distintos: `ingles -
            # ingles` nombra uno solo dos veces, y eso es lo que dice
            # monolingue. `Diccionario de ingles` a secas no dice nada.
            menciones = [v for a, v in _IDIOMAS_DE_DICCIONARIO for _ in re.finditer(rf"\b{a}\b", plano)]
            if re.search(r"\bmonolingue\b", plano) or (len(menciones) >= 2 and len(set(menciones)) == 1):
                attrs["monolingue"] = True
            elif len(set(menciones)) >= 2 or re.search(r"\bbilingue\b", plano):
                attrs["monolingue"] = False

        elif pedido == "grados":
            grados = re.search(r"\b(\d{2,3})\s*(?:grados?\b|°|º)", plano)
            if grados:
                attrs["grados"] = int(grados.group(1))

        elif pedido == "colores":
            cuantos = re.search(r"(\d{1,3})\s*colores\b", plano)
            if cuantos:
                attrs["colores"] = int(cuantos.group(1))
            elif any(re.search(rf"\b{s}\b", plano) for s in MULTICOLOR):
                # El nombre dice que es surtido pero no cuantos: entonces hay
                # tantos colores como unidades trae el empaque. Se exige la
                # senal de surtido porque sin ella `x12 unidades` puede ser
                # una docena de marcadores del mismo color.
                empaque = extraer_empaque(nombre)
                if empaque.unidades > 1:
                    attrs["colores"] = empaque.unidades

        elif pedido in ("ano", "anio"):
            # `Agenda Chica Kawai 2026 2027` cubre dos anos lectivos, que es
            # como se venden las agendas escolares en Colombia: empiezan a
            # mitad de un ano y terminan en el siguiente.
            anos = re.findall(r"\b(20[2-4]\d)\b", plano)
            if anos:
                attrs[pedido] = "-".join(dict.fromkeys(anos[:2]))
            elif re.search(r"\bpermanente\b", plano):
                attrs[pedido] = "permanente"

        elif pedido == "materias":
            if re.search(r"\bmulti\s?materias?\b", plano):
                attrs["materias"] = "multiple"
            else:
                cuantas = re.search(r"(\d{1,2})\s*materias\b", plano)
                escrita = re.search(rf"\b({'|'.join(_NUMEROS_ESCRITOS)})\s+materias\b", plano)
                # Uno por omision, y es el UNICO atributo que lo tiene. En la
                # papeleria colombiana lo multiple siempre viene marcado, asi
                # que un cuaderno callado es de una materia: no es un dato que
                # falte, es el dato. Sin esto, 16 de los 17 cuadernos del
                # catalogo quedaban incompletos por algo que ya sabiamos, y
                # C001 es el concepto mas pedido del corpus.
                if cuantas:
                    attrs["materias"] = int(cuantas.group(1))
                elif escrita:
                    # `cuaderno tres materias` (11#21) se leia de una materia.
                    attrs["materias"] = _NUMEROS_ESCRITOS[escrita.group(1)]
                else:
                    attrs["materias"] = 1

        elif pedido == "hojas":
            cuantas = re.search(r"(\d{1,4})\s*(?:hojas?|hjs?)\b", plano)
            if cuantas:
                attrs["hojas"] = int(cuantas.group(1))

        elif pedido == "unidades":
            empaque = extraer_empaque(nombre)
            if empaque.unidades > 1:
                attrs["unidades"] = empaque.unidades

        elif pedido in ("gramaje", "peso"):
            peso = re.search(r"(\d{1,4}(?:\.\d+)?)\s*(g|gr|grs|gramos?|kg)\b", plano)
            if peso:
                attrs[pedido] = f"{_entero_si_cabe(peso.group(1))} {'kg' if peso.group(2) == 'kg' else 'g'}"

        elif pedido in ("capacidad", "volumen"):
            vol = re.search(r"(\d{1,4}(?:\.\d+)?)\s*(ml|cc|lt?|litros?)\b", plano)
            if vol:
                unidad = "ml" if vol.group(2) in ("ml", "cc") else "l"
                attrs[pedido] = f"{_entero_si_cabe(vol.group(1))} {unidad}"

        elif pedido in ("longitud", "grosor", "calibre"):
            largo = re.search(
                r"(\d{1,4}(?:\.\d+)?)\s*(mm|cm|m|metros?|centimetros?|milimetros?|pulgadas?)\b", plano
            )
            if largo:
                attrs[pedido] = f"{_entero_si_cabe(largo.group(1))} {_unidad_corta(largo.group(2))}"

        elif pedido == "puntos":
            puntos = re.search(r"(\d{3,4})\s*(?:puntos|contactos|pines)\b", plano)
            if puntos:
                attrs["puntos"] = int(puntos.group(1))

        elif pedido == "manga":
            if re.search(r"\bmanga corta\b", plano):
                attrs["manga"] = "corta"
            elif re.search(r"\b(?:manga larga|mangas largas|con mangas?)\b", plano):
                attrs["manga"] = "larga"

        elif pedido == "notas":
            # Un xilofono se pide por placas y se vende por notas o tonos.
            notas = re.search(r"(\d{1,2})\s*(?:placas|notas|tonos|teclas)\b", plano)
            if notas:
                attrs["notas"] = int(notas.group(1))

        elif pedido == "piezas":
            piezas = re.search(r"(\d{1,5})\s*(?:piezas?|fichas?)\b", plano)
            if piezas:
                attrs["piezas"] = int(piezas.group(1))

    return attrs


# ---------------------------------------------------------------------------
# Atributos que vienen de la ficha de la tienda
# ---------------------------------------------------------------------------

# Como se llama en la ficha de la tienda cada cosa que el catalogo necesita.
#
# La ficha trae muchisimo mas, y casi todo es contabilidad interna de la
# tienda: `Factor Neto PUM`, `Dividendo PUM`, `IVA`, `Prime`, `Ump del Empaque
# 1 (Out)`. Nada de eso describe el producto para un papa ni sirve para
# comparar contra lo que pidio el colegio, asi que no se importa "todo lo que
# haya" sino esta lista corta y escrita a proposito.
# Solo los campos que las tiendas publican de verdad, contados sobre las 147
# fichas en cache. `Talla` no aparece en ninguna, asi que no esta aqui:
# mapear un campo inexistente es codigo muerto con apariencia de cobertura, y
# hace creer que el atributo se puede llenar cuando no hay de donde.
DE_LA_FICHA = {
    "Tamaño": "tamano",
    "Idioma": "idioma",
    "Dimensiones": "dimensiones",
    "Medidas del producto": "dimensiones",
    "Tipo de punta": "punta",
    "Presentación": "presentacion",
    "Tipo de agenda": "tipo",
    "Tipo de producto": "tipo",
    "Material Principal": "material",
    "Número de páginas": "hojas",
    "N.° páginas": "hojas",
    "Número de hojas": "hojas",
    "Número de Piezas": "piezas",
    "Tipo de linea": "rayado",
    "Tipo de línea": "rayado",
    "Capacidad": "capacidad",
    "Peso": "gramaje",
    "Tipo": "tipo",
    "Material": "material",
    "Color": "color",
    "Formato": "tipo",
    "Encuadernación": "acabado",
}


def _limpiar_material(bruto: str) -> str | None:
    """`Exterior: Poliester=100%` -> `poliester`.

    Las tiendas escriben el material como una ficha de composicion textil
    entera. Guardarla tal cual hace que el resolutor compare `algodon` de la
    lista del colegio contra `Exterior: Poliester=100%, Forro: Nylon=100%` y
    no encuentre nada.
    """
    texto = _sin_tildes(bruto.lower())
    for aguja, valor in MATERIAL:
        if aguja in texto:
            return valor
    for candidato in ("poliester", "algodon", "nylon", "sintetico", "cuero", "eva", "pvc"):
        if candidato in texto:
            return candidato
    return None


def atributos_de_ficha(especificaciones: dict[str, str], requeridos: tuple[str, ...]) -> dict[str, Any]:
    """Traduce la ficha de la tienda a los atributos que el concepto exige.

    Se sigue devolviendo solo lo pedido y se sigue callando lo que no se pueda
    leer, por la misma razon que al leer el nombre: un atributo inventado es
    peor que uno ausente, porque el resolutor lo cree y elige con confianza.
    """
    atributos: dict[str, Any] = {}
    for nombre_tienda, valor in especificaciones.items():
        destino = DE_LA_FICHA.get(nombre_tienda)
        if destino is None or destino not in requeridos or destino in atributos:
            continue

        if destino in ("hojas", "piezas"):
            cifra = re.search(r"\d{1,5}", valor)
            # `Número de Piezas: 0` aparece cuando la tienda no lo lleno. Un
            # cero declarado es tan inutil como un vacio y ademas parece dato.
            if cifra and int(cifra.group()) > 0:
                atributos[destino] = int(cifra.group())
        elif destino == "material":
            limpio = _limpiar_material(valor)
            if limpio:
                atributos["material"] = limpio
        elif destino == "color":
            plano = _normalizar(valor)
            for aguja, canonico in COLORES:
                if re.search(rf"\b{aguja}\b", plano):
                    atributos["color"] = canonico
                    break
        else:
            # Sin tildes, igual que lo que sale de un nombre. Sin esto, la
            # ficha guardaba `español` y el nombre `espanol` para el mismo
            # atributo, asi que el resolutor comparaba dos cadenas distintas
            # y no emparejaba nada. El sintoma es el peor posible: no falla,
            # solo deja de encontrar.
            limpio = _sin_tildes(valor.strip().lower())
            # `N/A`, `Normal`, `-`: la tienda lleno la casilla para no dejarla
            # vacia. Eso no es informacion sobre el producto.
            if limpio and limpio not in ("n/a", "na", "-", "normal", "otro", "otros", "ninguno"):
                atributos[destino] = limpio[:64]
    return atributos


def _entero_si_cabe(texto: str) -> str:
    valor = float(texto)
    return str(int(valor)) if valor.is_integer() else texto


def _unidad_corta(palabra: str) -> str:
    if palabra.startswith("pulgada"):
        return "in"
    if palabra.startswith("mili") or palabra == "mm":
        return "mm"
    if palabra.startswith("centi") or palabra == "cm":
        return "cm"
    return "m"


# ---------------------------------------------------------------------------
# Imagenes
# ---------------------------------------------------------------------------


def imagen_desde_ficha(url_oferta: str) -> str | None:
    """Portada de la ficha que ya se conocia, sin buscar nada.

    Se conserva como funcion propia porque es lo que usa la pasada de
    imagenes, pero el trabajo lo hace `tiendas.ficha`, que exige que la
    direccion devuelva UN producto. Una busqueda por nombre devolveria algo
    parecido, y ponerle a un producto la foto de otro es peor que dejarlo sin
    foto: el papa reconoce la imagen, pide confiado y recibe otra cosa.
    """
    encontrada = tiendas.ficha(url_oferta)
    return encontrada.imagen_url if encontrada else None


# ---------------------------------------------------------------------------
# Embeddings (canal semantico de la busqueda hibrida, OE3)
# ---------------------------------------------------------------------------


def embeddings_a_actualizar(productos: list[dict[str, Any]], embeder: Embeder) -> list[dict[str, Any]]:
    """Que embeddings hay que (re)calcular, y con que texto.

    Es idempotente por diseno, que es lo que permite correr el backfill sobre
    todo el corpus sin gastar una llamada por producto cada vez: se recalcula
    solo cuando el TEXTO del que sale el vector cambio, o cuando no habia
    vector. `texto_embedding` guardado es la huella; si coincide con el texto
    de ahora, el vector sigue valiendo. Esto separa el QUE de la escritura a
    base y del transporte, para poder probarlo sin red ni motor: se inyecta
    `embeder` (el falso en pruebas, Gemini en produccion).

    El embeder se llama UNA vez con todos los textos pendientes: los
    proveedores cobran y tardan por peticion, no por vector, y un lote es una
    peticion. La lista devuelta tiene la forma que `_guardar_embeddings`
    espera (`pid`, `embedding`, `embedding_model`, `texto_embedding`).
    """
    modelo = getattr(embeder, "modelo", None) or getattr(embeder, "__name__", "embeder")
    pendientes: list[tuple[dict[str, Any], str]] = []
    for p in productos:
        texto = texto_de_producto(p.get("nombre", ""), p.get("concepto"), p.get("atributos"))
        vigente = p.get("texto_embedding") == texto and p.get("embedding_model") == modelo
        if not vigente:
            pendientes.append((p, texto))

    if not pendientes:
        return []

    vectores = embeder([texto for _, texto in pendientes])
    return [
        {
            "pid": p["id"],
            "embedding": vector,
            "embedding_model": modelo,
            "texto_embedding": texto,
        }
        for (p, texto), vector in zip(pendientes, vectores, strict=True)
    ]


# ---------------------------------------------------------------------------
# Aplicacion
# ---------------------------------------------------------------------------


async def _cargar_contexto() -> tuple[
    list[dict[str, Any]], dict[str, tuple[str, ...]], dict[str, list[str]], dict[str, str], dict[str, str]
]:
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    producto = Base.metadata.tables["producto_canonico"]
    concepto = Base.metadata.tables["concepto"]
    oferta = Base.metadata.tables["oferta_tienda"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            productos = [
                dict(f._mapping)
                for f in await conexion.execute(
                    select(
                        producto.c.id,
                        producto.c.nombre,
                        producto.c.concepto_id,
                        producto.c.imagen_url,
                        producto.c.unidades_por_empaque,
                        producto.c.unidad_base,
                        producto.c.atributos,
                        producto.c.personaje,
                        # La huella del embedding: con que texto y que modelo se
                        # calculo el vector que ya esta en la fila. Es lo que
                        # hace idempotente el backfill (ver embeddings_a_actualizar).
                        producto.c.texto_embedding,
                        producto.c.embedding_model,
                    )
                )
            ]
            requeridos: dict[str, tuple[str, ...]] = {}
            nombres_concepto: dict[str, str] = {}
            codigos_concepto: dict[str, str] = {}
            for f in await conexion.execute(
                select(
                    concepto.c.id,
                    concepto.c.codigo,
                    concepto.c.nombre_canonico,
                    concepto.c.atributos_discriminantes,
                    concepto.c.atributos_descriptivos,
                )
            ):
                # Los DOS, discriminantes y descriptivos. El enriquecedor llena
                # todo lo que se pueda leer: un descriptivo no filtra
                # candidatos, pero si se le muestra al acudiente, y dejarlo
                # vacio lo deja mirando una ficha en blanco.
                requeridos[str(f.id)] = tuple(f.atributos_discriminantes or ()) + tuple(
                    f.atributos_descriptivos or ()
                )
                nombres_concepto[str(f.id)] = f.nombre_canonico
                codigos_concepto[str(f.id)] = f.codigo
            urls: dict[str, list[str]] = {}
            for f in await conexion.execute(
                select(oferta.c.producto_canonico_id, oferta.c.url).where(oferta.c.url.is_not(None))
            ):
                urls.setdefault(str(f.producto_canonico_id), []).append(f.url)
    finally:
        await motor.cerrar()
    return productos, requeridos, urls, nombres_concepto, codigos_concepto


async def _guardar_embeddings(cambios: list[dict[str, Any]]) -> None:
    """Escribe los vectores calculados en `producto_canonico`.

    Va en su propia transaccion, aparte de `_guardar` (empaque, atributos,
    imagen), porque el embedding sale de un puerto externo que puede fallar o
    no estar configurado: separarlo deja que el enriquecimiento del nombre —que
    nunca sale a la red— se escriba aunque el canal semantico no corra.
    """
    if not cambios:
        return
    from sqlalchemy import bindparam, update
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    producto = Base.metadata.tables["producto_canonico"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            sentencia = (
                update(producto)
                .where(producto.c.id == bindparam("pid"))
                .values(
                    embedding=bindparam("embedding"),
                    embedding_model=bindparam("embedding_model"),
                    texto_embedding=bindparam("texto_embedding"),
                )
            )
            await conexion.execute(sentencia, cambios)
    finally:
        await motor.cerrar()


async def _guardar(cambios: list[dict[str, Any]]) -> None:
    from sqlalchemy import bindparam, select, update
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    producto = Base.metadata.tables["producto_canonico"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            sentencia = (
                update(producto)
                .where(producto.c.id == bindparam("pid"))
                .values(
                    unidades_por_empaque=bindparam("unidades_por_empaque"),
                    unidad_base=bindparam("unidad_base"),
                    atributos=bindparam("atributos"),
                    imagen_url=bindparam("imagen_url"),
                    personaje=bindparam("personaje"),
                )
            )
            await conexion.execute(sentencia, cambios)

            # Un concepto admite personaje si de hecho existe uno con
            # personaje. Se deduce del catalogo en vez de mantenerlo a mano:
            # la marca decia que siete conceptos lo admitian y el catalogo ya
            # traia reglas de Barbie, vasos de Spiderman y balones de
            # Avengers. Una bandera que contradice a los datos que describe no
            # sirve para decidir nada.
            concepto = Base.metadata.tables["concepto"]
            await conexion.execute(
                update(concepto)
                .where(
                    concepto.c.id.in_(select(producto.c.concepto_id).where(producto.c.personaje.is_not(None)))
                )
                .values(admite_personaje=True)
            )
    finally:
        await motor.cerrar()


def empaque_combinado(unidades_guardadas: int | None, unidad_guardada: str | None, leido: Empaque) -> Empaque:
    """El empaque guardado gana sobre el leido del nombre, salvo que sea el 1 por omision.

    Desde que el empaque es columna de `productos_canonicos.csv`, lo guardado
    puede ser una correccion a mano (la UI de admin la permite), y una pasada
    de `enriquecer` no puede deshacerla. Un 1 no se distingue del default, asi
    que ahi si manda lo que dice el nombre.
    """
    if unidades_guardadas and unidades_guardadas > 1:
        return Empaque(unidades_guardadas, unidad_guardada or leido.unidad_base)
    return leido


def atributos_combinados(
    guardados: dict[str, Any], leidos: dict[str, Any], reextraer: frozenset[str] = frozenset()
) -> dict[str, Any]:
    """Lo guardado gana sobre lo leido, salvo en las claves que se piden releer.

    Lo guardado gana porque puede ser curado a mano, y el juicio de una
    persona vale mas que una expresion regular. Pero lo guardado tambien es lo
    que una version vieja del vocabulario leyo mal (`punta=permanente` en un
    marcador, `tipo=permanente` en un oleo verde permanente), y sin una forma
    de releerlo ese error no se iba nunca. Releer es explicito y por clave:
    en esas claves manda lo que el nombre dice HOY, y si hoy no dice nada, la
    clave se va.
    """
    conservados = {k: v for k, v in guardados.items() if k not in reextraer}
    return {**leidos, **conservados}


def _leer_reextraer(pedidos: list[str]) -> dict[str, frozenset[str]]:
    """`C006:tipo,punta` -> {"C006": {"tipo", "punta"}}."""
    salida: dict[str, set[str]] = {}
    for pedido in pedidos:
        codigo, _, claves = pedido.partition(":")
        if not codigo or not claves:
            raise SystemExit(f"--reextraer espera CONCEPTO:clave[,clave], no {pedido!r}")
        salida.setdefault(codigo.strip(), set()).update(c.strip() for c in claves.split(",") if c.strip())
    return {c: frozenset(v) for c, v in salida.items()}


async def _principal(
    con_imagenes: bool,
    solo_validar: bool,
    con_embeddings: bool = True,
    reextraer: dict[str, frozenset[str]] | None = None,
    informe: str | None = None,
    con_fichas: bool = False,
) -> int:
    productos, requeridos, urls, nombres_concepto, codigos = await _cargar_contexto()
    reextraer = reextraer or {}

    imagenes: dict[str, str] = {}
    de_ficha: dict[str, dict[str, Any]] = {}
    if con_imagenes or con_fichas:
        # Una sola lectura por producto y de ahi sale todo lo que la tienda
        # sabe: la portada, los atributos de la ficha tecnica y el personaje
        # que la tienda declara. Leer la misma ficha tres veces, una por cada
        # dato, multiplicaba por tres el tiempo y el riesgo de que la tienda
        # cortara por exceso de peticiones.
        def le_falta_algo(p: dict[str, Any]) -> bool:
            if con_imagenes and (not p["imagen_url"] or not p["atributos"]):
                return True
            # `--fichas`: lo que el nombre no dijo puede estar en la ficha.
            # Se pide solo para quien le falta un atributo de su concepto,
            # para no leer 685 fichas cuando el nombre ya lo dijo todo.
            guardados = p["atributos"] or {}
            return con_fichas and any(a not in guardados for a in requeridos.get(str(p["concepto_id"]), ()))

        pendientes = [(p, urls.get(str(p["id"]), [])) for p in productos if le_falta_algo(p)]
        pendientes = [(p, u) for p, u in pendientes if u]
        print(f"Leyendo la ficha de {len(pendientes)} productos en las tiendas que ya se conocian...")

        def resolver(par):
            producto, direcciones = par
            for direccion in direcciones:
                encontrada = tiendas.ficha(direccion)
                if encontrada:
                    return str(producto["id"]), encontrada
            return str(producto["id"]), None

        leidas = 0
        with ThreadPoolExecutor(max_workers=6) as grupo:
            for pid, oferta in grupo.map(resolver, pendientes):
                if oferta is None:
                    continue
                leidas += 1
                if oferta.imagen_url:
                    imagenes[pid] = oferta.imagen_url
                de_ficha[pid] = {
                    "especificaciones": oferta.especificaciones,
                    "personaje": oferta.especificaciones.get("Personaje"),
                }
        print(f"  fichas leidas: {leidas}/{len(pendientes)}   con portada: {len(imagenes)}")

    cambios = []
    empaques_nuevos = atributos_nuevos = 0
    for p in productos:
        attrs_concepto = requeridos.get(str(p["concepto_id"]), ())
        empaque = extraer_empaque(p["nombre"], attrs_concepto)
        attrs = extraer_atributos(p["nombre"], attrs_concepto)

        # La ficha de la tienda rellena lo que el nombre no dijo, y no al
        # reves. El nombre es lo que el papa va a leer en el kit, asi que si
        # los dos hablan del mismo atributo manda el nombre: un cuaderno que
        # se llama "Media Carta" es de media carta aunque la ficha diga
        # "Tamaño: Normal".
        ficha_p = de_ficha.get(str(p["id"]))
        if ficha_p:
            attrs = {**atributos_de_ficha(ficha_p["especificaciones"], attrs_concepto), **attrs}

        empaque = empaque_combinado(p["unidades_por_empaque"], p.get("unidad_base"), empaque)
        if empaque.unidades != p["unidades_por_empaque"]:
            empaques_nuevos += 1
        if attrs and not p["atributos"]:
            atributos_nuevos += 1

        cambios.append(
            {
                "pid": p["id"],
                "unidades_por_empaque": empaque.unidades,
                "unidad_base": empaque.unidad_base,
                # Lo leido no pisa lo curado a mano: si alguien ya reviso este
                # producto, su juicio vale mas que una expresion regular.
                "atributos": atributos_combinados(
                    p["atributos"] or {},
                    attrs,
                    reextraer.get(codigos.get(str(p["concepto_id"]), ""), frozenset()),
                ),
                "imagen_url": p["imagen_url"] or imagenes.get(str(p["id"])),
                "personaje": (
                    p["personaje"] or extraer_personaje(p["nombre"]) or (ficha_p or {}).get("personaje")
                ),
            }
        )

    if informe:
        _escribir_informe(informe, productos, cambios, codigos)

    con_personaje = sum(1 for c in cambios if c["personaje"])
    con_attrs = sum(1 for c in cambios if c["atributos"])
    con_img = sum(1 for c in cambios if c["imagen_url"])
    total = len(cambios)
    print("\n=== lo que se puede leer del nombre ===")
    print(f"  empaque corregido (ya no es 1)     {empaques_nuevos:5}/{total}")
    print(f"  productos con atributos            {con_attrs:5}/{total}")
    print(f"     nuevos en esta pasada           {atributos_nuevos:5}")
    print(f"  productos con imagen               {con_img:5}/{total}")
    print(f"  productos con personaje            {con_personaje:5}/{total}")

    # El canal semantico (OE3). El texto que se embebe se arma de lo YA
    # enriquecido —nombre + concepto + atributos finales—, no del crudo, para
    # que el vector situe al producto por lo que de verdad es. Se decide el
    # embeder por el entorno: con GEMINI_API_KEY, el real; sin ella, ninguno,
    # y se dice —no se inventa un vector falso en produccion—.
    plan_embeddings: list[dict[str, Any]] = []
    if con_embeddings:
        embeder = _embeder_por_entorno()
        if embeder is None:
            print("\n(sin GEMINI_API_KEY: no se calculan embeddings)")
        else:
            por_pid = {str(c["pid"]): c for c in cambios}
            para_embeber = [
                {
                    "id": p["id"],
                    "nombre": p["nombre"],
                    "concepto": nombres_concepto.get(str(p["concepto_id"])),
                    "atributos": por_pid[str(p["id"])]["atributos"],
                    "texto_embedding": p.get("texto_embedding"),
                    "embedding_model": p.get("embedding_model"),
                }
                for p in productos
            ]
            plan_embeddings = embeddings_a_actualizar(para_embeber, embeder)
            print(f"  embeddings a (re)calcular          {len(plan_embeddings):5}/{total}")

    if solo_validar:
        print("\n(--solo-validar: no se escribio nada)")
        return 0

    await _guardar(cambios)
    await _guardar_embeddings(plan_embeddings)
    print("\nEscrito.")
    return 0


def _escribir_informe(
    ruta: str, productos: list[dict[str, Any]], cambios: list[dict[str, Any]], codigos: dict[str, str]
) -> None:
    """Un CSV con cada atributo que esta pasada agrega, cambia o quita.

    Es lo que se revisa antes de escribir: el resumen dice cuantos productos
    tienen atributos, pero no si los que se leyeron son ciertos.
    """
    import csv

    por_pid = {str(c["pid"]): c for c in cambios}
    filas = 0
    with open(ruta, "w", encoding="utf-8", newline="") as salida:
        escritor = csv.writer(salida)
        escritor.writerow(["concepto", "producto_id", "nombre", "atributo", "antes", "despues"])
        for p in productos:
            antes = p["atributos"] or {}
            despues = por_pid[str(p["id"])]["atributos"]
            for clave in sorted(set(antes) | set(despues)):
                if antes.get(clave) != despues.get(clave):
                    escritor.writerow(
                        [
                            codigos.get(str(p["concepto_id"]), ""),
                            p["id"],
                            p["nombre"],
                            clave,
                            antes.get(clave, ""),
                            despues.get(clave, ""),
                        ]
                    )
                    filas += 1
    print(f"  informe: {filas} cambios de atributo en {ruta}")


def _embeder_por_entorno() -> Embeder | None:
    """El embeder real si hay clave, ninguno si no.

    Se elige por entorno y no por bandera para que el mismo comando haga lo
    correcto en cada sitio: con clave (produccion, E2E) puebla el canal
    semantico; sin ella (un dev sin credenciales) enriquece nombre e imagenes
    y calla el vector, en vez de fallar o fingirlo. Las pruebas no pasan por
    aqui: inyectan el embeder falso directo a `embeddings_a_actualizar`.
    """
    import os

    from .embeddings import embeder_gemini

    return embeder_gemini if os.environ.get("GEMINI_API_KEY", "").strip() else None


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--imagenes", action="store_true", help="ir a la red por las portadas")
    analizador.add_argument("--sin-embeddings", action="store_true", help="no calcular el canal semantico")
    analizador.add_argument("--solo-validar", action="store_true")
    analizador.add_argument(
        "--reextraer",
        action="append",
        default=[],
        metavar="CONCEPTO:clave[,clave]",
        help="releer del nombre estas claves aunque ya esten guardadas (p. ej. C006:tipo,punta)",
    )
    analizador.add_argument("--informe", metavar="RUTA.csv", help="escribir cada cambio de atributo a un CSV")
    analizador.add_argument(
        "--fichas",
        action="store_true",
        help="leer la ficha de la tienda de los productos a los que les falta un atributo (va a la red)",
    )
    args = analizador.parse_args()
    return asyncio.run(
        _principal(
            args.imagenes,
            args.solo_validar,
            not args.sin_embeddings,
            reextraer=_leer_reextraer(args.reextraer),
            informe=args.informe,
            con_fichas=args.fichas,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
