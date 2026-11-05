"""
Test set para el benchmark "agente vs enfoque actual" en NL2C (lista de
útiles en lenguaje natural → ítems estructurados + restricciones).

Dos formatos, como en producción (SRS Módulo 2 y VFP):
  - "prosa": un mensaje natural de un padre ("Necesito 2 cuadernos
    cuadriculados y 1 esfero azul..."), donde el parser de reglas línea-por-
    línea de perception falla porque hay varios ítems en una sola línea.
  - "lista": texto línea-por-línea (formato OCR/PDF tipográfico), donde el
    parser de reglas está optimizado.

Cada caso tiene ground truth: ítems (id_producto, cantidad) y restricciones
(exclusion_marcas, precio_min/max, categoria).
"""
import random

from benchmarks.data import CATEGORIAS, MARCAS, _normalizar

# Sinónimos de la jerga escolar colombiana (espejo de perception/extractor.py
# PE-05) apuntando a la forma canónica usada en los nombres del catálogo.
SINONIMOS_CATALOGO = {
    "esfero": "lapicero", "esferos": "lapicero",
    "boligrafo": "lapicero", "boligrafos": "lapicero",
    "subrayador": "resaltador", "subrayadores": "resaltador",
    "sacapuntas": "tajalapiz",
}

# Descripciones canónicas (sin marca) por nombre base de producto. Reutiliza
# las paráfrasis de data.CATEGORIAS y añade variantes con sinónimos.
ALIASES = {}
for categoria, items in CATEGORIAS.items():
    for nombre_base, parafrasis in items:
        base = _normalizar(nombre_base)
        ALIASES[base] = set()
        ALIASES[base].add(base)
        ALIASES[base].update(_normalizar(p) for p in parafrasis)
        ALIASES[base].update(_normalizar(p).replace("cuaderno", "cuaderno") for p in parafrasis)

# Variantes extra por categoría para que las frases suenen naturales.
INTROS_PROSA = [
    "Necesito {item1}, {item2} y {item3} para el colegio de mi hija.",
    "La lista de útiles de segundo grado incluye {item1}, {item2} y {item3}.",
    "Para este año escolar necesito {item1}; también {item2} y {item3}.",
    "Me pidieron {item1}, {item2} y {item3} en la reunión de padres.",
    "Por favor incluye {item1}, {item2} y {item3} en la compra.",
    "Para el regreso a clases necesito {item1}, {item2} y {item3}.",
]
INTROS_LISTA = [
    "Lista de útiles:\n{lineas}",
    "Grado 3 — útiles escolares\n{lineas}",
]
SUFIJO_CONSTRAINT = [
    " sin marca {marca}",
    " y nada de la marca {marca}",
    " con un presupuesto máximo de ${monto}",
    " no más de ${monto}",
    " de preferencia en {categoria}",
    " preferiblemente en la categoría de {categoria}",
]

_ARTICULOS = ("un ", "una ", "unos ", "unas ", "el ", "la ", "los ", "las ", "2 ", "1 ", "3 ")


def _con_articulo(desc: str) -> str:
    return desc


def _item_prosa(producto: dict, cantidad: int, alias: str) -> str:
    cant_palabra = {1: "un", 2: "dos", 3: "tres"}[cantidad]
    if cantidad == 1:
        return f"{cant_palabra} {alias}"
    return f"{cant_palabra} {alias}"


def _item_lista(producto: dict, cantidad: int, alias: str) -> str:
    return f"{cantidad} {alias}"


def generar_casos(productos: list[dict], semilla: int = 11,
                  n_prosa: int = 20, n_lista: int = 10) -> list[dict]:
    """Genera casos de prueba. Cada caso: {"texto", "tipo", "items":[{id,
    cantidad}], "restricciones":{...}, "fuente":[{id, alias}]}."""
    rng = random.Random(semilla)
    base_por_id = {p["id"]: p["nombre"].rsplit(" ", 1)[0] for p in productos}
    nombre_por_id = {p["id"]: p["nombre"] for p in productos}

    casos = []
    for _ in range(n_prosa):
        elegidos = rng.sample(productos, 3)
        cantidades = [rng.randint(1, 3) for _ in range(3)]
        alias = []
        for p in elegidos:
            base = _normalizar(base_por_id[p["id"]])
            # sorted() para eliminar la dependencia del hash de strings de
            # Python (hash randomization por proceso → test set NO
            # reproducible). sorted() hace el conjunto reproducible.
            opciones = sorted(ALIASES.get(base, {base}))
            alias.append(rng.choice(opciones))
        textos_items = [
            _item_prosa(p, c, a) for p, c, a in zip(elegidos, cantidades, alias)
        ]
        frase = rng.choice(INTROS_PROSA).format(
            item1=textos_items[0], item2=textos_items[1], item3=textos_items[2])
        restricciones = {}
        azar = rng.random()
        if azar < 0.4:
            marca = rng.choice([m for m in MARCAS if m not in {p["marca"] for p in elegidos}])
            frase += rng.choice(SUFIJO_CONSTRAINT[:2]).format(marca=marca.lower())
            restricciones["exclusion_marcas"] = [marca.lower()]
        elif azar < 0.7:
            monto = rng.choice(["150000", "200000", "250000"])
            frase += rng.choice(SUFIJO_CONSTRAINT[2:4]).format(monto=monto)
            restricciones["precio_max"] = int(monto)
        elif azar < 0.9:
            cat = elegidos[0]["categoria"]
            frase += rng.choice(SUFIJO_CONSTRAINT[4:]).format(categoria=cat.lower())
            restricciones["categoria"] = cat
        casos.append({
            "texto": frase, "tipo": "prosa",
            "items": [{"id": p["id"], "cantidad": c} for p, c in zip(elegidos, cantidades)],
            "restricciones": restricciones,
            "fuente": [{"id": p["id"], "alias": a} for p, a in zip(elegidos, alias)],
        })

    for _ in range(n_lista):
        elegidos = rng.sample(productos, 3)
        cantidades = [rng.randint(1, 3) for _ in range(3)]
        lineas = []
        for p, c in zip(elegidos, cantidades):
            base = _normalizar(base_por_id[p["id"]])
            opciones = sorted(ALIASES.get(base, {base}))
            alias = rng.choice(opciones)
            lineas.append(_item_lista(p, c, alias))
        texto = rng.choice(INTROS_LISTA).format(lineas="\n".join(lineas))
        casos.append({
            "texto": texto, "tipo": "lista",
            "items": [{"id": p["id"], "cantidad": c} for p, c in zip(elegidos, cantidades)],
            "restricciones": {},
            "fuente": [{"id": p["id"], "alias": None} for p in elegidos],
        })

    return casos
