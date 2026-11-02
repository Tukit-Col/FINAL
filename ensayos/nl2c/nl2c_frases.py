"""Frases de prueba del asistente NL2C con su etiqueta de oro.

Las etiquetas se escribieron ANTES de correr el modelo (el commit que agrega
este archivo es anterior al que agrega el corredor y los resultados).

De donde sale cada frase (campo `fuente`):
- `encuesta:texto`: texto libre de la encuesta a acudientes del Agustiniano
  (Resultados_encuesta.xlsx, 60 respuestas validas; columnas 18 y 24), copiado tal
  cual o con cambios minimos de persona verbal.
- `encuesta:cerrada`: una respuesta cerrada de la encuesta (P14 gasto anual,
  P21 prioridades, P22 sobreprecio) dicha como la diria un acudiente.
- `construida`: frase escrita por el equipo con la forma de lo que pide el
  formulario de /empezar (personaje, tope, estilo). La encuesta no trae nombres
  de personajes, de modo que todos los personajes son de esta clase.

Reglas de oro (las mismas para todas las frases):
- `estilo`: "gastar poco / barato / lo mas barato" es `economico`; "equilibrado /
  punto medio / sin pasarme" es `punto_medio`; "lo mejor / aunque cueste mas /
  calidad primero" es `estirarse`; sin pista, `punto_medio` (el valor por omision).
- `peso_mayor`: la dimension que el acudiente nombra primero. Sin pista, la que
  el formulario da por omision a ese estilo (precio para economico y punto medio,
  calidad para estirarse). Si dos dimensiones empatan en lo que dijo, se aceptan las dos.
- `presupuesto`: el tope por hijo en pesos si lo dice; en un rango, su extremo superior.
- `sobreprecio`: el porcentaje solo si lo dice; si no, el modelo no debe fijarlo.
- `personajes`: los del catalogo surtido que nombra; uno que no esta en el catalogo no cuenta.
- `accion`: `fijar` si hay algo que convertir en restricciones; `sin_accion` si
  pide algo que el kit no controla. Una tupla acepta varias.
"""

from __future__ import annotations

from dataclasses import dataclass

# Los personajes con las cuatro anclas en datos/catalogo (conteo de productos activos).
CATALOGO_PERSONAJES = ["disney", "stitch", "minnie", "spiderman", "bluey", "cars", "frozen", "paw patrol"]


@dataclass(frozen=True)
class Oro:
    id: str
    texto: str
    fuente: str
    accion: tuple[str, ...] = ("fijar",)
    presupuesto: int | None = None
    personajes: tuple[str, ...] = ()
    marcas: tuple[str, ...] = ()
    solo_disponibles: bool = False
    estilo: tuple[str, ...] = ("punto_medio",)
    sobreprecio: float | None = None
    peso_mayor: tuple[str, ...] = ("precio",)


E, C = "encuesta:texto", "encuesta:cerrada"
K = "construida"

FRASES: list[Oro] = [
    Oro("U01", "Lo más barato posible", f"{C} P21 precio total del kit", estilo=("economico",)),
    Oro(
        "U02",
        "Quiero las marcas exactas que pide el colegio",
        f"{C} P21 marcas exactas del colegio",
        peso_mayor=("marca_exigida",),
    ),
    Oro(
        "U03",
        "Que sean de buena calidad y que duren",
        f"{C} P21 calidad y durabilidad",
        estilo=("estirarse", "punto_medio"),
        peso_mayor=("calidad",),
    ),
    Oro(
        "U04",
        "Le encantan los personajes, especialmente Bluey",
        f"{C} P21 marcas o personajes que le gustan al hijo",
        personajes=("bluey",),
        peso_mayor=("personaje",),
    ),
    Oro("U05", "Calidad y precio", f"{E} col24", peso_mayor=("precio", "calidad")),
    Oro("U06", "Buen precio y prontitud", f"{E} col24", estilo=("economico", "punto_medio")),
    Oro(
        "U07",
        "Poder encontrar los útiles a precios cómodos",
        f"{E} col24",
        estilo=("economico", "punto_medio"),
    ),
    Oro(
        "U08",
        "Sería genial tener todo en un solo lugar con buen precio",
        f"{E} col24",
        estilo=("economico", "punto_medio"),
    ),
    Oro(
        "U09",
        "Inventario en línea para evitar comprar cosas que no están disponibles",
        f"{E} col24",
        solo_disponibles=True,
    ),
    Oro("U10", "Los costos y la calidad observable", f"{E} col18", peso_mayor=("precio", "calidad")),
    Oro(
        "U11",
        "Precios y disponibilidad",
        f"{E} col18",
        solo_disponibles=True,
        estilo=("economico", "punto_medio"),
    ),
    Oro(
        "U12",
        "Que no haya agotados, quiero que todo esté disponible",
        f"{E} col18 (disponibilidad)",
        solo_disponibles=True,
    ),
    Oro("U13", "Gasto entre 700 mil y un millón por hijo al año", f"{C} P14", presupuesto=1_000_000),
    Oro(
        "U14",
        "Menos de 400 mil por hijo",
        f"{C} P14",
        presupuesto=400_000,
        estilo=("economico", "punto_medio"),
    ),
    Oro("U15", "Puedo pagar hasta un 5% más si vale la pena", f"{C} P22", sobreprecio=5.0),
    Oro(
        "U16",
        "Solo si es al mismo precio o más barato",
        f"{C} P22",
        sobreprecio=0.0,
        estilo=("economico",),
    ),
    Oro(
        "U17",
        "Hasta un 10% más por mejor calidad",
        f"{C} P22",
        sobreprecio=10.0,
        estilo=("punto_medio", "estirarse"),
        peso_mayor=("calidad",),
    ),
    Oro(
        "U18",
        "Mi hijo ama Spiderman, quiero gastar poco pero que los colores sean buenos",
        f"{K} (ejemplo del encargo)",
        personajes=("spiderman",),
        estilo=("economico",),
        peso_mayor=("precio", "calidad"),
    ),
    Oro(
        "U19",
        "Mi hija es fan de Frozen y no me importa pagar un poco más",
        K,
        personajes=("frozen",),
        estilo=("punto_medio", "estirarse"),
        peso_mayor=("personaje", "calidad"),
    ),
    Oro("U20", "Quiero Paw Patrol, tengo 300 mil", K, personajes=("paw patrol",), presupuesto=300_000),
    Oro("U21", "Algo equilibrado, sin pasarme de 300 mil", K, presupuesto=300_000),
    Oro(
        "U22",
        "Que sea lo mejor aunque cueste más, mi hijo ama Cars",
        K,
        personajes=("cars",),
        estilo=("estirarse",),
        peso_mayor=("calidad", "personaje"),
    ),
    Oro(
        "U23",
        "Prefiero marca conocida, como pide el colegio, y que cueste lo justo",
        K,
        peso_mayor=("marca_exigida",),
    ),
    Oro(
        "U24",
        "Que sea baratísimo, hasta 200 mil, y que le toque Stitch",
        K,
        personajes=("stitch",),
        presupuesto=200_000,
        estilo=("economico",),
    ),
    Oro("U25", "Calidad primero y precio después", K, estilo=("estirarse",), peso_mayor=("calidad",)),
    Oro(
        "U26",
        "No quiero la marca Faber-Castell, que sea barato",
        K,
        marcas=("faber-castell",),
        estilo=("economico",),
    ),
    Oro(
        "U27",
        "Minnie para mi hija, que no se acaben los útiles, máximo 500 mil",
        K,
        personajes=("minnie",),
        solo_disponibles=True,
        presupuesto=500_000,
    ),
    Oro(
        "U28",
        "Me gustaría gastar poco pero sin sacrificar calidad",
        K,
        estilo=("economico", "punto_medio"),
        peso_mayor=("precio", "calidad"),
    ),
    Oro("U29", "Que tenga a domicilio", f"{E} col24", accion=("sin_accion",)),
    Oro("U30", "Lista de productos con imágenes", f"{E} col24", accion=("sin_accion",)),
    Oro("U31", "Hay materiales que piden y nunca usan", f"{E} col24", accion=("sin_accion",)),
    Oro(
        "U32",
        "Importante para nosotros que incluyan el plan lector y todos los libros adicionales",
        f"{E} col24",
        accion=("sin_accion",),
    ),
    Oro("U33", "Buena iniciativa", f"{E} col24", accion=("sin_accion",)),
    Oro(
        "U34",
        "Quiero a Batman en el kit",
        f"{K} (personaje fuera del catalogo)",
        accion=("fijar", "sin_accion"),
    ),
    Oro(
        "U35",
        "Mi hijo ama a Spiderman y a Bluey",
        K,
        personajes=("spiderman", "bluey"),
        peso_mayor=("personaje",),
    ),
]
