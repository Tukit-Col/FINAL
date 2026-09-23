"""De un renglon de lista a una demanda, sin mirar el catalogo.

El catalogo responde QUE producto se parece. Esto responde QUE pidio el
colegio, que es otra pregunta y va primero: hay renglones que no se compran,
y buscarles un producto es un defecto, no cobertura.

La cantidad y el empaque quedan en campos distintos a proposito. El sistema
anterior los colapsaba en un numero y de ahi salia sumar doce cajas cuando
la lista pedia doce lapices. Aqui `cantidad` es cuantas cosas pide el
colegio y `unidades_por_empaque` es, si el renglon lo dice, de a cuantas
viene cada cosa. Multiplicar o dividir es trabajo de una fase posterior.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Lo que se empareja contra productos. El resto se resuelve sin buscar:
# un texto escolar es un lookup de edicion, y lo no comprable ni eso.
BUSCA_EN_CATALOGO = frozenset({"util", "libro_libre"})

# "Libro" no alcanza para mandar el renglon al camino editorial. Estas cinco
# redacciones salen del corpus y son papeleria: un libro para colorear no
# tiene ISBN, y tratarlo como texto escolar es el fallo que esta fase existe
# para no cometer.
_PAPELERIA_AUNQUE_DIGA_LIBRO = (
    "para colorear",
    "de colorear",
    "de recortes",
    "para recortar",
    "pasatiempo",
    "didactico para colorear",
)

_NO_COMPRAR = (
    "disponible en casa",
    "el que tenga en casa",
    "traer de casa",
    "traer el que",
    "ya lo tiene",
    "en casa",
)

_DIFERIDO = (
    "se incluiran",
    "se incluira",
    "se solicitaran",
    "se solicitara",
    "seran solicitados",
    "mas adelante",
    "durante el ano",
    "a lo largo del ano",
)

_LICENCIA = (
    "link de pago",
    "codigo de acceso",
    "se adquiere por plataforma",
    "se adquiere directamente",
    "plataforma",
)

_URL = re.compile(r"https?://[^\s)>]+")
_MEDIDA = frozenset({"cm", "mm", "ml", "cc", "gr", "grs", "gramos", "mts", "mt", "metros", "metro"})
_EMPAQUE = re.compile(
    r"(?:(?:x|por)\s+(\d{1,4})(?:\s+(unidades|unds|uds|unid|u))?)"
    r"|(?:(?:caja|paquete|set|juego|bolsa)\s+de\s+(\d{1,4}))"
)
_CANTIDAD_AL_FRENTE = re.compile(r"^(\d{1,4})\s+(?!\d)")


def _plano(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    # `x12` y `x 12` son la misma presentacion. Separarlos aqui evita que
    # el empaque dependa de como lo escribio el colegio.
    sin_tildes = re.sub(r"\bx(\d)", r"x \1", sin_tildes)
    return re.sub(r"\s+", " ", sin_tildes).strip()


@dataclass(frozen=True)
class Demanda:
    """Lo que un renglon le pide al pipeline, antes de mirar un producto.

    `cantidad` va en unidad base y puede ser cero: "el disponible en casa"
    es una instruccion de no comprar, y cero es el numero honesto. `None` no
    serviria, porque habria que distinguirlo de "no supe leerlo".
    """

    texto: str
    tipo_item: str
    modo_adquisicion: str
    cantidad: int
    unidad_base: str = "unidad"
    unidades_por_empaque: int | None = None
    url_externa: str | None = None
    nota: str | None = None

    @property
    def busca_en_catalogo(self) -> bool:
        """Si este renglon debe pasar por el emparejamiento de productos.

        Un texto escolar no: su respuesta es una edicion, no un parecido.
        Una licencia, un diferido o un "traelo de casa" tampoco.
        """
        return self.tipo_item in BUSCA_EN_CATALOGO and self.modo_adquisicion in {
            "mercado_abierto",
            "libro_libre",
        }


def mensaje_para_papa(demanda: Demanda) -> str:
    """Texto que el papa ve en el kit cuando el renglon no se busca en catalogo.

    Vacio si si se busca: ahi el estado lo pone el emparejamiento, no este
    mensaje. Nunca vacio en el resto: una linea en blanco se lee como si el
    item no existiera.
    """
    if demanda.busca_en_catalogo:
        return ""
    if demanda.tipo_item == "util" and demanda.modo_adquisicion == "venta_directa_editorial":
        return "Se adquiere directamente en el colegio. Tukit no lo incluye en la compra."
    if demanda.tipo_item == "texto" and demanda.modo_adquisicion == "venta_directa_editorial":
        return "Se compra directamente con la editorial. Tukit no lo incluye en la compra."
    if demanda.tipo_item == "no_comprar":
        return "No hay que comprarlo. Ya se tiene en casa."
    if demanda.tipo_item == "diferido":
        return "Se compra más adelante. Todavía no entra en este kit."
    if demanda.tipo_item == "licencia_digital":
        return "Es una licencia digital. No se busca en la tienda de útiles."
    if demanda.tipo_item == "uniforme":
        return "Aún no lo proveemos. El colegio indica cómo conseguirlo."
    if demanda.modo_adquisicion == "edicion_exclusiva":
        return "Es una edición exclusiva del colegio. Tukit no lo incluye en la compra."
    if demanda.tipo_item == "texto":
        return "Es un texto escolar. No se busca en la tienda de útiles."
    return "Este ítem no se busca en la tienda de útiles."


def _contiene(plano: str, frases: tuple[str, ...]) -> bool:
    return any(frase in plano for frase in frases)


def _tipo(plano: str, url: str | None) -> tuple[str, str, str | None]:
    """Tipo, modo de adquisicion y nota. El orden es el de los casos reales.

    Lo no comprable va antes que "diccionario" o "libro", porque la misma
    linea puede nombrar las dos cosas: "Diccionario: el disponible en casa"
    es una instruccion, no un pedido de diccionario.
    """
    if _contiene(plano, _NO_COMPRAR):
        return "no_comprar", "mercado_abierto", "El colegio indica usar el que ya tienes."
    if _contiene(plano, _DIFERIDO):
        return "diferido", "diferido", "El colegio lo pedira mas adelante."
    if url or _contiene(plano, _LICENCIA):
        return "licencia_digital", "plataforma", "Se paga fuera de Tukit. No entra al carrito."
    if _contiene(plano, _PAPELERIA_AUNQUE_DIGA_LIBRO):
        return "util", "mercado_abierto", None
    if "cualquier editorial" in plano:
        return "libro_libre", "libro_libre", None
    if "directamente en el jardin" in plano:
        return "util", "venta_directa_editorial", "Se compra en el jardin, no en Tukit."
    if "venta directa" in plano or "directamente con la editorial" in plano:
        return "texto", "venta_directa_editorial", "Lo vende la editorial, no Tukit."
    if "edicion exclusiva" in plano:
        return "texto", "edicion_exclusiva", "Edicion cerrada por el colegio."
    if "uniforme" in plano:
        return "uniforme", "mercado_abierto", "Fuera de alcance de esta version."
    if any(s in plano for s in ("editorial", "autor:", " autor ", "isbn", "plan lector", " ed.")):
        return "texto", "mercado_abierto", None
    return "util", "mercado_abierto", None


def _empaque(plano: str) -> int | None:
    """De a cuantas viene, si el renglon lo dice. Una medida no es un empaque.

    `x 5 metros` cuenta una longitud, no cinco rollos. `caja de 12` si
    cuenta. Cuando hay varios, gana el mayor: es el mismo criterio con el
    que se leen los nombres de producto, y conviene que las dos lecturas
    no se contradigan.
    """
    mejor: int | None = None
    for coincidencia in _EMPAQUE.finditer(plano):
        bruto = coincidencia.group(1) or coincidencia.group(3)
        if bruto is None:
            continue
        cantidad = int(bruto)
        cola = plano[coincidencia.end() : coincidencia.end() + 12]
        palabra = cola.split(" ", 1)[0] if coincidencia.group(1) and not coincidencia.group(2) else ""
        if palabra in _MEDIDA:
            continue
        if mejor is None or cantidad > mejor:
            mejor = cantidad
    return mejor


def _cantidad(plano: str, explicita: int | None, tipo: str) -> int:
    if tipo == "no_comprar":
        return 0
    if explicita is not None:
        return explicita
    al_frente = _CANTIDAD_AL_FRENTE.match(plano)
    if al_frente:
        return int(al_frente.group(1))
    return 1


def parsear_renglon(texto: str, *, cantidad: int | None = None) -> Demanda:
    """Lee un renglon. `cantidad` gana sobre el numero del texto.

    La percepcion a veces separa la columna de cantidad de la descripcion
    ("2" | "Cuaderno cuadriculado"). Cuando llega asi, el numero ya no esta
    en el texto y hay que poder pasarlo. Si el texto tambien lo trae, no se
    suman: seria contar el mismo pedido dos veces.
    """
    # El `@` de Osito marca el renglon en el margen. No es parte del pedido,
    # y pegado a la primera palabra impide reconocer el grado y el texto.
    texto = re.sub(r"^@+\s*", "", texto.strip())
    plano = _plano(texto)
    url_m = _URL.search(texto)
    url = url_m.group(0).rstrip(".,;") if url_m else None
    tipo, modo, nota = _tipo(plano, url)
    return Demanda(
        texto=texto.strip(),
        tipo_item=tipo,
        modo_adquisicion=modo,
        cantidad=_cantidad(plano, cantidad, tipo),
        unidades_por_empaque=_empaque(plano),
        url_externa=url,
        nota=nota,
    )
