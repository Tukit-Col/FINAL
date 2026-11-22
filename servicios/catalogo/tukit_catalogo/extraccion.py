from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

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
    ("a 4", "a4"),
    ("a 3", "a3"),
)

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
    ("tarro", "frasco"),
    ("frasco", "frasco"),
    ("pomo", "frasco"),
    ("tubo", "tubo"),
    ("libra", "bolsa"),
    ("pastilla", "pastilla"),
    ("crema", "crema"),
    ("bolsa", "bolsa"),
    ("paquete", "paquete"),
    ("sobre", "sobre"),
)

MATERIAL = (
    ("acero inoxidable", "acero"),
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

TIPOS = (
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
    ("de dibujo", "dibujo"),
    ("bitacora", "dibujo"),
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
    ("balancin", "balancin"),
    ("dos posiciones", "2 posiciones"),
    ("2 posiciones", "2 posiciones"),
    ("motorreductor", "motorreductor"),
    ("motoreductor", "motorreductor"),
    ("motor", "motor"),
    ("macho-macho", "macho-macho"),
    ("macho - macho", "macho-macho"),
    ("macho-hembra", "macho-hembra"),
    ("macho - hembra", "macho-hembra"),
    ("hembra-macho", "macho-hembra"),
    ("hembra - macho", "macho-hembra"),
    ("hembra-hembra", "hembra-hembra"),
    ("hembra - hembra", "hembra-hembra"),
    ("permanente", "permanente"),
    ("borrable", "borrable"),
    ("lavable", "lavable"),
    ("milimetrado", "milimetrado"),
    ("cuadriculado", "cuadriculado"),
    ("cuadriculada", "cuadriculado"),
    ("ferrocarril", "ferrocarril"),
    ("doble linea", "doble linea"),
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
    ("futbol de salon", "futbol de salon"),
    ("microfutbol", "futbol de salon"),
    ("baloncesto", "baloncesto"),
    ("voleibol", "voleibol"),
    ("futbol", "futbol"),
    ("cientifica", "cientifica"),
    ("de escritorio", "de escritorio"),
    ("basica", "basica"),
    ("juego de mesa", "juego de mesa"),
    ("de mesa", "juego de mesa"),
    ("juegos de mesa", "juego de mesa"),
    ("loteria", "loteria"),
    ("domino", "domino"),
    ("ajedrez", "juego de mesa"),
    ("parques", "juego de mesa"),
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
    ("palos de paleta", "paleta"),
    ("palo de paleta", "paleta"),
    ("palitos de paleta", "paleta"),
    ("para paleta", "paleta"),
    ("balso", "balso"),
    ("humeda", "humeda"),
    ("humedo", "humeda"),
    ("panitos", "humeda"),
    ("toallitas", "humeda"),
    ("toalla de papel", "papel"),
    ("toalla", "tela"),
    ("vaso", "vaso"),
    ("plato", "plato"),
    ("fotografico", "fotografico"),
    ("sketch book", "dibujo"),
    ("sketchbook", "dibujo"),
    ("bocetos", "dibujo"),
    ("escolar", "escolar"),
)

ACABADOS = (
    ("fluorescente", "fluorescente"),
    ("fluorecente", "fluorescente"),
    ("escarchado", "escarchado"),
    ("escarchada", "escarchado"),
    ("metalizado", "metalizado"),
    ("metalizada", "metalizado"),
    ("iris", "iris"),
    ("figuras", "figuras"),
)

COLORES = (
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
    ("oro", "dorado"),
    ("purpura", "morado"),
    ("cian", "cian"),
    ("cyan", "cian"),
    ("magenta", "magenta"),
)

PUNTAS = (
    ("doble punta", "doble punta"),
    ("micropunta", "micropunta"),
    ("punta roma", "punta roma"),
    ("puntaroma", "punta roma"),
    ("punta fina", "punta fina"),
    ("punta extrafina", "punta fina"),
    ("punta delgada", "punta fina"),
    ("punta gruesa", "punta gruesa"),
    ("punta pincel", "punta pincel"),
    ("punta biselada", "punta biselada"),
    ("punta bala", "punta bala"),
    ("delgado", "punta fina"),
    ("grueso", "punta gruesa"),
)

ENCUADERNACIONES = (
    ("sin espiral", "cosido"),
    ("sin argolla", "cosido"),
    ("cosido", "cosido"),
    ("cocido", "cosido"),
    ("argollado", "argollado"),
    ("anillado", "argollado"),
    ("espiral", "argollado"),
)

_BIBLIA_INFANTIL = re.compile(
    r"\b(?:ninos?|ninas?|nios|nias|infantil(?:es)?|mi primera|"
    r"(?:lecturas|historias|relatos) de la biblia)\b"
)
MULTICOLOR = ("surtido", "surtida", "surtidos", "surtidas", "multicolor", "neon", "pastel")


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
    ("disney", "disney"),
)


def extraer_personaje(nombre: str) -> str | None:
    plano = _normalizar(nombre)
    for aguja, valor in PERSONAJES:
        if re.search(rf"\b{re.escape(aguja)}\b", plano):
            return valor
    return None


def _sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _normalizar(texto: str) -> str:
    plano = _sin_tildes(texto.lower())
    plano = re.sub(r"(\d)([a-z])", r"\1 \2", plano)
    plano = re.sub(r"([a-z])(\d)", r"\1 \2", plano)
    return re.sub(r"\s+", " ", plano.replace(",", "."))


@dataclass(frozen=True)
class Empaque:
    unidades: int
    unidad_base: str


_CANTIDAD = re.compile(r"(?:^|[\s(.,\-])(?:x|por)\s*(\d{1,4})(\.\d+)?\s*([a-z]+)?")

_EMPAQUE_ESCRITO = re.compile(r"\b(?:paquete|caja|set|juego|bolsa|blister|kit)\s+de\s+(\d{1,4})\b")


def extraer_empaque(nombre: str, atributos_del_concepto: tuple[str, ...] = ()) -> Empaque:
    plano = _normalizar(nombre)
    hojas_son_atributo = "hojas" in atributos_del_concepto

    mejor: Empaque | None = None
    for coincidencia in _CANTIDAD.finditer(plano):
        cantidad = int(coincidencia.group(1))
        palabra = coincidencia.group(3) or ""

        if coincidencia.group(2):
            continue
        if 10 <= cantidad <= 999 and re.search(r"(?:^|[\s(])\d{2,3}\s*$", plano[: coincidencia.start() + 1]):
            continue
        if palabra in MEDIDA:
            continue
        if palabra and palabra not in CONTEO:
            palabra = ""
        if palabra in ("hojas", "hoja", "hj", "hjs") and hojas_son_atributo:
            continue

        unidad = CONTEO.get(palabra, "unidad")
        if cantidad < 1:
            continue
        if mejor is None or cantidad > mejor.unidades:
            mejor = Empaque(cantidad, unidad)

    escrito = _EMPAQUE_ESCRITO.search(plano)
    if escrito and (mejor is None or int(escrito.group(1)) > mejor.unidades):
        mejor = Empaque(int(escrito.group(1)), "unidad")

    if mejor is None and re.search(r"\bdocena\b", plano):
        mejor = Empaque(6 if re.search(r"\bmedia docena\b", plano) else 12, "unidad")

    if mejor is not None:
        return mejor

    if not hojas_son_atributo:
        suelto = re.search(r"(?:^|[\s(])(\d{1,4})\s+(hojas?|pliegos?|unidades|unds?|uds?)\b", plano)
        if suelto:
            return Empaque(int(suelto.group(1)), CONTEO.get(suelto.group(2), "unidad"))

    return Empaque(1, "unidad")


IDIOMAS = (
    ("espanol", "espanol"),
    ("castellano", "espanol"),
    ("ingles", "ingles"),
    ("english", "ingles"),
    ("frances", "frances"),
    ("aleman", "aleman"),
    ("latin", "latin"),
)

_IDIOMAS_DE_DICCIONARIO = (*IDIOMAS, ("spanish", "espanol"), ("french", "frances"))

FORMAS = (
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
)

GROSORES = (
    ("extra grueso", "extra grueso"),
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

_DUREZA = re.compile(r"\b(\d?[hb]{1,2})\b")
_DUREZAS_VALIDAS = frozenset(
    {"h", "b", "hb", "hh", "bb"} | {f"{n}{letra}" for n in range(2, 10) for letra in "hb"}
)

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
    numerado = re.search(rf"(\d{{1,2}})\s*(?:{'|'.join(palabras)})\b", plano)
    if numerado:
        return int(numerado.group(1))
    for aguja, cuantos in _CUANTOS_ESCRITOS:
        if re.search(rf"\b{aguja}\b", plano):
            return cuantos
    return None


def _coincidencias(plano: str, tabla: tuple[tuple[str, str], ...]) -> list[tuple[str, re.Match[str]]]:
    halladas: list[tuple[str, re.Match[str]]] = []
    for aguja, valor in tabla:
        for m in re.finditer(rf"\b{re.escape(aguja)}(?:s|es)?\b", plano):
            halladas.append((valor, m))
    halladas.sort(key=lambda par: par[1].end() - par[1].start(), reverse=True)

    tomadas: list[tuple[str, re.Match[str]]] = []
    for valor, m in halladas:
        if all(m.end() <= otra.start() or m.start() >= otra.end() for _, otra in tomadas):
            tomadas.append((valor, m))
    return tomadas


def _valor_unico(plano: str, tabla: tuple[tuple[str, str], ...]) -> tuple[str, re.Match[str]] | None:
    tomadas = _coincidencias(plano, tabla)
    if len({valor for valor, _ in tomadas}) != 1:
        return None
    return tomadas[0]


def atributos_ambiguos(texto: str, requeridos: tuple[str, ...]) -> list[str]:
    plano = _normalizar(texto)
    leidos = extraer_atributos(texto, requeridos)
    return [
        atributo
        for atributo in requeridos
        if atributo in _TABLAS_DE_UNA_DIMENSION
        and atributo not in leidos
        and len({valor for valor, _ in _coincidencias(plano, _TABLAS_DE_UNA_DIMENSION[atributo])}) > 1
    ]


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
    plano = _normalizar(nombre)
    attrs: dict[str, Any] = {}

    for pedido in requeridos:
        if pedido == "tamano":
            for aguja, valor in TAMANOS:
                if re.search(rf"\b{re.escape(aguja)}s?\b", plano):
                    attrs["tamano"] = valor
                    break
            else:
                medidas = re.search(r"(\d{1,3}(?:\.\d+)?)\s*x\s*(\d{1,3}(?:\.\d+)?)\s*cms?\b", plano)
                if medidas:
                    attrs["tamano"] = (
                        f"{_entero_si_cabe(medidas.group(1))} x {_entero_si_cabe(medidas.group(2))} cm"
                    )
                else:
                    for aguja, valor in TAMANOS_RELATIVOS:
                        if re.search(rf"\b{aguja}\b", plano):
                            attrs["tamano"] = valor
                            break

        elif pedido == "color":
            unico = _valor_unico(plano, COLORES)
            if unico:
                attrs["color"] = unico[0]
            elif re.search(
                r"\b(?:surtid[oa]s?|multicolor|de colores|diferentes colores|varios colores)\b", plano
            ):
                attrs["color"] = "surtido"

        elif pedido == "rayado":
            unico = _valor_unico(plano, RAYADOS)
            if unico:
                valor, m = unico
                medida = re.match(r"\s*(?:de\s*)?(\d{1,2}(?:\.\d)?)\s*(mm|cm)\b", plano[m.end() :])
                attrs["rayado"] = (
                    f"{valor} {_entero_si_cabe(medida.group(1))} {medida.group(2)}" if medida else valor
                )

        elif pedido == "idioma":
            hallados = [v for a, v in IDIOMAS if re.search(rf"\b{a}\b", plano)]
            if hallados:
                distintos = sorted(set(hallados))
                menciones = [v for a, v in _IDIOMAS_DE_DICCIONARIO for _ in re.finditer(rf"\b{a}\b", plano)]
                if len(distintos) == 1 and (re.search(r"\bmonolingue\b", plano) or len(menciones) >= 2):
                    attrs["idioma"] = f"{distintos[0]}-{distintos[0]}"
                else:
                    attrs["idioma"] = "-".join(distintos)

        elif pedido == "deposito":
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
                serie = re.search(r"(?:\bn\s*[o°]?\s*|#\s*)(\d{1,2})\b", plano)
                if serie:
                    attrs["grosor"] = f"n{int(serie.group(1))}"

        elif pedido == "dureza":
            durezas = {c for c in _DUREZA.findall(_sin_tildes(nombre.lower())) if c in _DUREZAS_VALIDAS}
            if len(durezas) == 1:
                attrs["dureza"] = durezas.pop()

        elif pedido == "tinta":
            encontrados = [v for a, v in COLORES if re.search(rf"\b{a}s?\b", plano)]
            if len(set(encontrados)) > 1:
                attrs["tinta"] = "surtido"
            elif encontrados:
                attrs["tinta"] = encontrados[0]

        elif pedido == "acabado":
            for aguja, valor in ACABADOS:
                if re.search(rf"\b{re.escape(aguja)}(?:s|es)?\b", plano):
                    attrs["acabado"] = valor
                    break

        elif pedido == "tipo":
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
                empaque = extraer_empaque(nombre)
                if empaque.unidades > 1:
                    attrs["colores"] = empaque.unidades

        elif pedido in ("ano", "anio"):
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
                if cuantas:
                    attrs["materias"] = int(cuantas.group(1))
                elif escrita:
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

        elif pedido == "calibre":
            calibre = re.search(r"\bcalibre\s*(\d{1,2})\b", plano) or re.search(r"\b(\d{1,2})\s*awg\b", plano)
            if calibre:
                attrs["calibre"] = f"{int(calibre.group(1))} awg"

        elif pedido == "valor":
            valores = {
                f"{_entero_si_cabe(m.group(1))} {'kohm' if m.group(2) else 'ohm'}"
                for m in re.finditer(r"(\d{1,4}(?:\.\d+)?)\s*(k)?\s*(?:ohms?|0\s?hms?|Ω)", plano)
            }
            if len(valores) == 1:
                attrs["valor"] = valores.pop()
            elif not valores and re.search(r"\b(?:surtid[oa]s|diferentes? (?:valores|amperaje))\b", plano):
                attrs["valor"] = "surtido"

        elif pedido in ("longitud", "grosor"):
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
            elif re.search(r"\bsin mangas?\b", plano):
                attrs["manga"] = "sin"
            elif re.search(r"\b(?:manga larga|mangas largas|con mangas?)\b", plano):
                attrs["manga"] = "larga"

        elif pedido == "notas":
            notas = re.search(r"(\d{1,2})\s*(?:placas|notas|tonos|teclas)\b", plano)
            if notas:
                attrs["notas"] = int(notas.group(1))

        elif pedido == "piezas":
            piezas = re.search(r"(\d{1,5})\s*(?:piezas?|fichas?)\b", plano)
            if piezas:
                attrs["piezas"] = int(piezas.group(1))

    return attrs


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
    texto = _sin_tildes(bruto.lower())
    for aguja, valor in MATERIAL:
        if aguja in texto:
            return valor
    for candidato in ("poliester", "algodon", "nylon", "sintetico", "cuero", "eva", "pvc"):
        if candidato in texto:
            return candidato
    return None


def atributos_de_ficha(especificaciones: dict[str, str], requeridos: tuple[str, ...]) -> dict[str, Any]:
    atributos: dict[str, Any] = {}
    for nombre_tienda, valor in especificaciones.items():
        destino = DE_LA_FICHA.get(nombre_tienda)
        if destino is None or destino not in requeridos or destino in atributos:
            continue

        if destino in ("hojas", "piezas"):
            cifra = re.search(r"\d{1,5}", valor)
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
            limpio = _sin_tildes(valor.strip().lower())
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
