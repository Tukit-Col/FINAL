"""
Dataset sintético pero realista del dominio de Tukit: catálogo escolar en
español + consultas de "lista de útiles" con ground truth.

Cada producto tiene un nombre canónico (producto + marca + atributos) y de
él se derivan 3 consultas con paráfrasis tal como las escribiría un padre
o el OCR de un PDF de lista escolar. El ground truth es el producto que
originó cada consulta (1 relevante por consulta).
"""
import random
import unicodedata
import uuid

CATEGORIAS = {
    "Cuadernos": [
        ("Cuaderno cuadriculado 100 hojas", ["cuaderno cuadriculado de 100 hojas", "cuadernos cuadriculados para matemáticas"]),
        ("Cuaderno de rayas 100 hojas", ["cuaderno de rayas para español", "cuaderno rayado de 100 hojas"]),
        ("Cuaderno de dibujo A4", ["cuaderno de dibujo tamaño carta", "cuaderno para artística"]),
        ("Cuaderno universitario cuadriculado", ["cuaderno universitario con cuadrícula", "cuaderno universitario 5 materias"]),
        ("Cuaderno cosido de 50 hojas", ["cuaderno cosido sencillo", "cuaderno de 50 hojas cosido"]),
    ],
    "Escritura": [
        ("Lápiz grafito HB x2", ["lápiz grafito número 2", "lapices de escribir grafito"]),
        ("Lapicero azul", ["esfero azul", "bolígrafo azul para escribir"]),
        ("Lapicero negro", ["esfero negro", "bolígrafo negro"]),
        ("Resaltador amarillo", ["marcador resaltador amarillo", "resaltador para subrayar"]),
        ("Corrector líquido", ["líquido corrector blanco", "corrector tipo lapiz"]),
    ],
    "Colores": [
        ("Colores x12", ["caja de colores de 12 unidades", "colores para pintar 12 piezas"]),
        ("Colores x24", ["caja de colores 24", "colores largos de 24"]),
        ("Temperas x6", ["pinturas temperas set de 6", "temperas escolares 6 colores"]),
        ("Pinturas acrílicas x12", ["pintura acrílica set 12", "acrílicos para cartulina"]),
        ("Plumones x10", ["marcadores delgados 10 colores", "plumones para dibujo 10"]),
    ],
    "Cartuchera y útiles": [
        ("Cartuchera escolar", ["cartuchera para lápices", "estuche escolar sencillo"]),
        ("Borrador de nata", ["borrador de caucho", "goma de borrar blanca"]),
        ("Tajalápiz metálico", ["sacapuntas metálico", "tajalápiz de metal"]),
        ("Regla 30 cm", ["regla de 30 centímetros", "regla escolar plástica"]),
        ("Tijeras punta roma", ["tijeras escolares sin punta", "tijeras para niños"]),
        ("Pegamento en barra", ["barra de pegamento", "pegante en barra 21 gramos"]),
        ("Compás escolar", ["compás para geometría", "compás con caja"]),
        ("Cinta adhesiva", ["cinta de enmascarar", "cinta transparente escolar"]),
    ],
    "Maletería": [
        ("Maleta escolar mediana", ["maleta para colegio mediana", "bolso escolar con ruedas"]),
        ("Lonchera térmica", ["lonchera para refrigerio", "lonchera termica escolar"]),
        ("Cartuchera con ruedas", ["maleta con carrito para libros", "cartuchera rodante"]),
    ],
    "Textos": [
        ("Diccionario escolar", ["diccionario de español para niños", "diccionario escolar básico"]),
        ("Atlas geográfico", ["atlas de geografía escolar", "mapas atlas para colegio"]),
        ("Libro de lectura grado 3", ["libro de cuentos grado tercero", "texto de lenguaje grado 3"]),
    ],
}

MARCAS = ["Norma", "BIC", "Faber-Castell", "Crayola", "Staedtler", "Maped",
          "Pelikan", "PaperMate", "Colkraft", "Rayuela"]

STOPWORDS_QUERIES = ["2 ", "3 ", "1 ", "un ", "una ", "unos ", "unas ", "el ",
                     "la ", "los ", "las ", "de ", "del ", "para "]


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return texto


def generar_catalogo(n_por_categoria: int | None = None, semilla: int = 7) -> list[dict]:
    """Genera el catálogo sintético. Cada producto: id, nombre (con marca y
    atributos), categoria, marca, precio. Devuelve lista de dicts."""
    rng = random.Random(semilla)
    productos = []
    for categoria, items in CATEGORIAS.items():
        for nombre_base, _ in items:
            marca = rng.choice(MARCAS)
            precio = rng.randint(3000, 45000)
            productos.append({
                "id": str(uuid.UUID(int=rng.getrandbits(128))),
                "nombre": f"{nombre_base} {marca}",
                "categoria": categoria,
                "marca": marca,
                "precio": precio,
            })
    if n_por_categoria is not None:
        productos = [p for p in productos]
    return productos


def generar_consultas(productos: list[dict], semilla: int = 7) -> list[dict]:
    """Para cada producto genera 3 consultas-paráfrasis. Ground truth: el id
    del producto que la originó."""
    rng = random.Random(semilla)
    consultas = []
    for p in productos:
        nombre_base = p["nombre"].rsplit(" ", 1)[0]
        variantes = set()
        variantes.add(_normalizar(p["nombre"]))
        # variante con cantidad + sin marca
        cantidades = ["", "2 ", "3 ", "1 "]
        variantes.add(f"{rng.choice(cantidades)}{nombre_base.lower()}")
        # variante reordenada/parafraseada
        variantes.add(f"{nombre_base.lower()} {p['marca'].lower()}")
        variantes.update(_normalizar(v) for v in _parafrasis(nombre_base, p))
        for v in sorted(variantes)[:3]:
            consultas.append({"id_producto": p["id"], "consulta": v})
    return consultas


def _parafrasis(nombre_base: str, producto: dict) -> list[str]:
    """Paráfrasis manuales según la categoría (simulan lo que escribiría un
    padre o el OCR de un PDF de lista)."""
    low = nombre_base.lower()
    categoria = producto["categoria"]
    if categoria == "Cuadernos":
        return [
            f"necesito {low}",
            f"cuaderno para el colegio tipo {producto['marca'].lower()}",
        ]
    if categoria == "Colores":
        return [
            f"{low} para pintar",
            f"set de {low}",
        ]
    if categoria == "Escritura":
        return [
            f"útil de escritura {low}",
            f"{low} para el estuche",
        ]
    return [
        f"{low} de buena calidad",
        f"lista escolar incluye {low}",
    ]


def dividir(productos: list[dict], n_consulta_por_modelo: int = 1) -> tuple[list[dict], list[dict]]:
    """Split catálogo/consultas simples para el benchmark."""
    consultas = generar_consultas(productos)
    return productos, consultas
