"""Reglas deterministas del asistente del kit para pedidos por categoria.

El modelo solo CLASIFICA la intencion ("mas barato", "mejor calidad", "variar") y, como
mucho, nombra una categoria. Que renglones entran en el pedido y que producto se propone
en cada uno lo decide este modulo con reglas sobre el catalogo del kit, de modo que:

- el modelo no elige skus ni precios (no hay nada que una inyeccion pueda dirigir);
- el resultado es reproducible: mismo kit y mismo pedido, mismas propuestas;
- el tope de propuestas y la pertenencia al kit los sigue imponiendo el servidor.

Aqui solo hay logica pura sobre diccionarios; armar los componentes de UI es de
`nl2c_kit.py` (que importa este modulo, no al reves).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

# Orden de calidad de marca. Se repite aqui (igual que en optimizador.py) porque este modulo
# no debe importar el optimizador, que arrastra pymoo: el vocabulario es el mismo.
ORDEN_NIVEL = ("economico", "confiable", "premium")

# Palabras que nunca nombran un tipo de util: del pedido o de relleno de las listas escolares.
_PALABRAS_VACIAS = frozenset(
    """
    los las del una uno unos unas por para con sin que mas muy todo todos toda todas cada
    kit kits util utiles renglon renglones cosa cosas quiero quisiera necesito veo ver
    barato barata baratos baratas economico economica mejor mejores calidad marca marcas
    surtido surtidos surtida variedad variar repetido repetidos tambien igual demasiado
    cambia cambiar cambio cambios dame poner pon hay tiene tienen quita quitar
    """.split()  # noqa: SIM905  (lista larga: mas legible como texto corrido)
)
# Una etiqueta que se le muestra al padre: solo letras, sin nada que pueda ser marcado.
_RE_ETIQUETA = re.compile(r"[a-zñáéíóúü]{3,24}")

# "que puedes hacer", "cuales son los cambios que puedes hacer", "ayuda", "como funcionas".
# Corta a proposito: un texto largo (con posible inyeccion) siempre pasa por el modelo.
_MAX_LARGO_AYUDA = 80
# La pregunta debe TERMINAR ahi (`$`) y no ir tras "lo": asi "mas barato en cuadernos, lo que
# puedes" o "que haces con los cuadernos" siguen siendo pedidos reales y llegan al modelo en
# vez de responderse con la lista de capacidades.
_RE_AYUDA = re.compile(
    r"(?:^|\s)(?:"
    r"(?:ayuda|ayudame|help)"
    r"|como\s+(?:funcionas?|te\s+uso)"
    r"|para\s+que\s+sirves"
    r"|(?<!lo\s)que\s+(?:haces|puedes|sabes|podes)(?:\s+(?:hacer|cambiar|pedir|ofrecer|ayudar))?(?:\s+(?:por\s+mi|aqui))?"
    r"|que\s+(?:puedo|se\s+puede)\s+(?:pedir|hacer|cambiar)"
    r"|(?:cambios|cosas|opciones)\s+(?:que\s+)?(?:puedes|puedo)(?:\s+(?:hacer|pedir))?"
    r")\s*$"
)


def plano(texto: str) -> str:
    """Minusculas y sin tildes: para comparar palabras, no para mostrar."""
    base = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return base.lower()


def raiz(palabra: str) -> str:
    """Quita el plural para que 'cuadernos' y 'Cuaderno' sean la misma palabra.

    Se aplica igual al pedido y a las descripciones del kit, asi que no necesita ser
    perfecta: solo consistente ('lapices' -> 'lapiz', 'colores' -> 'color').
    """
    if len(palabra) > 4 and palabra.endswith("ces"):
        return palabra[:-3] + "z"
    if len(palabra) > 4 and palabra.endswith("es") and palabra[-3] in "rnldz":
        return palabra[:-2]
    if len(palabra) > 3 and palabra.endswith("s"):
        return palabra[:-1]
    return palabra


def palabras(texto: str) -> list[tuple[str, str]]:
    """(palabra original en minuscula, raiz) de cada palabra con sentido para nombrar un util."""
    salida: list[tuple[str, str]] = []
    for original in re.findall(r"[\wñáéíóúü]+", (texto or "").lower()):
        p = plano(original)
        if len(p) < 3 or any(ch.isdigit() for ch in p) or p in _PALABRAS_VACIAS:
            continue
        salida.append((original, raiz(p)))
    return salida


def _raices(texto: str) -> set[str]:
    return {r for _, r in palabras(texto)}


def pide_ayuda(texto_limpio: str) -> bool:
    """El padre pregunta que puede pedir. Se responde sin llamar al modelo."""
    # Sin signos (¿?!.,) para que la pregunta se lea igual con o sin ellos.
    p = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", plano(texto_limpio))).strip()
    return 0 < len(p) <= _MAX_LARGO_AYUDA and bool(_RE_AYUDA.search(p))


def pluralizar(palabra: str) -> str:
    """Para los ejemplos tocables: 'cuaderno' -> 'cuadernos', 'color' -> 'colores'."""
    if palabra.endswith("s"):
        return palabra
    if palabra.endswith("z"):
        return palabra[:-1] + "ces"
    return palabra + ("es" if palabra[-1] in "rnld" else "s")


def etiqueta_valida(palabra: str) -> bool:
    return bool(_RE_ETIQUETA.fullmatch(palabra))


@dataclass
class Categoria:
    """Los renglones del kit que entran en un pedido por categoria."""

    etiqueta: str  # la palabra del padre (o del kit) para hablarle: solo letras
    refs: list[str]  # referencias L# en el orden del kit


def _palabra_del_kit(r: str, lineas: dict[str, dict[str, Any]], refs: list[str]) -> str:
    for ref in refs:
        for original, rr in palabras(str(lineas[ref].get("descripcion") or "")):
            if rr == r and etiqueta_valida(original):
                return original
    return "esos"


def resolver_categoria(fuente: str | None, lineas: dict[str, dict[str, Any]]) -> Categoria | None:
    """Que renglones nombra una frase ('cuadernos', 'mas barato en todos los colores').

    Una categoria solo existe si alguna de sus palabras aparece en las descripciones del kit:
    lo que el modelo invente o el atacante meta no resuelve a nada.
    """
    pares = palabras(fuente or "")
    if not pares:
        return None
    por_ref = {ref: _raices(str(ln.get("descripcion") or "")) for ref, ln in lineas.items()}
    en_texto = {r: o for o, r in pares}
    # Una descripcion que trae todas las palabras ("cuaderno cuadriculado") es lo mas preciso;
    # si no hay, se toma la union de renglones que traen alguna ("cuadernos y colores").
    todas = {r for _, r in pares}
    refs = [ref for ref, rs in por_ref.items() if todas <= rs]
    usadas = sorted(todas)
    if not refs:
        usadas = [r for r in dict.fromkeys(r for _, r in pares) if any(r in rs for rs in por_ref.values())]
        refs = [ref for ref, rs in por_ref.items() if rs & set(usadas)]
    if not refs:
        return None
    original = next((en_texto[r] for r in usadas if r in en_texto), "")
    if not etiqueta_valida(original):
        original = _palabra_del_kit(usadas[0], lineas, refs)
    return Categoria(original, sorted(refs, key=lambda ref: int(ref[1:])))


def todo_el_kit(lineas: dict[str, dict[str, Any]]) -> Categoria:
    """Solo para 'variar': repetir un personaje se ve en el kit entero, no en una categoria."""
    return Categoria("kit", sorted(lineas, key=lambda ref: int(ref[1:])))


def categorias_del_kit(lineas: dict[str, dict[str, Any]], *, maximo: int = 3) -> list[str]:
    """Las palabras con que el kit nombra sus renglones, las mas repetidas primero.

    Se toma la primera palabra con sentido de cada descripcion (el sustantivo: 'Cuaderno
    cuadriculado', 'Colores x12'). Sirven para los ejemplos tocables de la ayuda.
    """
    cuenta: dict[str, int] = {}
    nombre: dict[str, str] = {}
    for ln in lineas.values():
        for original, r in palabras(str(ln.get("descripcion") or "")):
            if not etiqueta_valida(original) or len(original) < 4:
                continue
            cuenta[r] = cuenta.get(r, 0) + 1
            nombre.setdefault(r, original)
            break
    orden = sorted(cuenta, key=lambda r: -cuenta[r])  # estable: empata por orden del kit
    return [pluralizar(nombre[r]) for r in orden[:maximo]]


def validar_anterior(anterior: Any, lineas: dict[str, dict[str, Any]]) -> dict[str, str] | None:
    """El pedido anterior que manda el navegador, aceptado solo si encaja en ESTE kit.

    Llega del cliente, asi que es dato no confiable: la accion debe ser de la lista y la
    categoria debe ser una palabra que el kit realmente usa. Lo demas se ignora.
    """
    if not isinstance(anterior, dict):
        return None
    accion, categoria = anterior.get("accion"), anterior.get("categoria")
    if accion not in ("mas_barato", "mejor_calidad", "variar") or not isinstance(categoria, str):
        return None
    if categoria == "kit":
        return {"accion": accion, "categoria": "kit"}
    if not etiqueta_valida(categoria) or resolver_categoria(categoria, lineas) is None:
        return None
    return {"accion": accion, "categoria": categoria}


# --- Reglas por accion ---------------------------------------------------------------------
def _entero(x: dict[str, Any], clave: str) -> int | None:
    v = x.get(clave)
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _nivel(x: dict[str, Any]) -> int:
    n = x.get("nivel")
    return ORDEN_NIVEL.index(n) if n in ORDEN_NIVEL else -1


def alternativa_mas_barata(actual: dict[str, Any], alts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """La alternativa de menor precio, solo si de verdad cuesta menos que el producto actual."""
    hoy = _entero(actual, "precio")
    validas = [a for a in alts if _entero(a, "precio_cop") is not None]
    if hoy is None:
        return None
    menores = [a for a in validas if _entero(a, "precio_cop") < hoy]  # type: ignore[operator]
    return min(menores, key=lambda a: (_entero(a, "precio_cop"), str(a.get("sku")))) if menores else None


def alternativa_de_mejor_calidad(actual: dict[str, Any], alts: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Sube un escalon de nivel (el mas cercano) y, dentro del escalon, la mas barata."""
    nivel = _nivel(actual)
    validas = [a for a in alts if _entero(a, "precio_cop") is not None]
    mejores = [a for a in validas if _nivel(a) > nivel >= 0]
    if _entero(actual, "precio") is None or not mejores:
        return None
    return min(mejores, key=lambda a: (_nivel(a), _entero(a, "precio_cop"), str(a.get("sku"))))


def clave_de_repeticion(linea: dict[str, Any]) -> tuple[str, str]:
    """Dos renglones 'se repiten' si traen el mismo personaje o, sin personaje, el mismo sku."""
    producto = linea["producto_elegido"]
    personaje = str(producto.get("personaje") or "").strip().lower()
    return ("p", personaje) if personaje else ("s", str(producto.get("sku")))


def renglones_a_variar(
    refs: list[str], lineas: dict[str, dict[str, Any]], consolidados: set[str]
) -> list[tuple[str, tuple[str, str]]]:
    """Los renglones que repiten producto, menos el primero de cada grupo.

    Dejar el primero de cada grupo cumple "mantener al menos uno del personaje": se
    varia lo que sobra, no se borra el personaje del kit.
    """
    grupos: dict[tuple[str, str], list[str]] = {}
    for ref in refs:
        grupos.setdefault(clave_de_repeticion(lineas[ref]), []).append(ref)
    salida: list[tuple[str, tuple[str, str]]] = []
    for clave, miembros in grupos.items():
        for ref in miembros[1:]:
            if str(lineas[ref]["producto_elegido"].get("sku")) not in consolidados:
                salida.append((ref, clave))
    return sorted(salida, key=lambda par: int(par[0][1:]))


def opciones_desde_alternativas(linea: dict[str, Any], alts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Plan B de `elegir_variante` si el carrusel no responde: las alternativas guardadas en el kit."""
    unidades = int(linea.get("unidades_a_comprar") or 1)
    salida = []
    for a in alts:
        precio = _entero(a, "precio_cop")
        if not a.get("sku") or precio is None:
            continue
        salida.append(
            {
                "sku": a["sku"],
                "nombre": a.get("nombre"),
                "marca": None,
                "nivel": a.get("nivel"),
                "personaje": None,
                "imagen_url": a.get("imagen_url"),
                "precio": precio,
                "unidades_a_comprar": unidades,
                "subtotal": precio * unidades,
                "en_kit": False,
            }
        )
    return salida


def elegir_variante(
    linea: dict[str, Any],
    clave: tuple[str, str],
    opciones: list[dict[str, Any]],
    usados_skus: set[str],
    usados_personajes: set[str],
) -> dict[str, Any] | None:
    """Una opcion distinta de lo que ya hay en la categoria, la mas parecida en precio.

    Descarta lo que ya esta en el kit, lo que repite un sku de la categoria y, si el grupo
    es de un personaje, cualquier otra opcion de ese mismo personaje. Prefiere un personaje
    que todavia no se use (mas variedad) y, a igualdad, el menor cambio de precio.
    """
    hoy = _entero(linea, "subtotal_linea") or 0
    candidatas = []
    for o in opciones:
        sku, subtotal = str(o.get("sku") or ""), _entero(o, "subtotal")
        personaje = str(o.get("personaje") or "").strip().lower()
        if (
            not sku
            or subtotal is None
            or _entero(o, "precio") is None
            or o.get("en_kit")
            or sku in usados_skus
        ):
            continue
        if clave[0] == "p" and personaje == clave[1]:
            continue
        candidatas.append((personaje in usados_personajes, abs(subtotal - hoy), subtotal, sku, o))
    if not candidatas:
        return None
    return min(candidatas, key=lambda c: c[:4])[4]
