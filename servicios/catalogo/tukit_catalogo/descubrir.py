"""Da de alta lo que una lista NUEVA pide y el catalogo todavia no tiene.

El catalogo es propio y curado, y solo tiene cosas que nos vemos en capacidad
de conseguir. Por eso funciona como un cache progresivo: el match de un
acudiente corre SIEMPRE contra nuestra base, con trigramas y vectores sobre
`concepto` y `producto_canonico`, y ninguna tienda participa de eso. Una
tienda aparece en un solo momento: cuando entra la lista de un colegio que
nadie ha revisado, un renglon no encuentra nada en casa, y hay que darlo de
alta.

La consecuencia de que sea un cache es que el gasto baja solo. La primera
lista de un colegio nuevo consulta tiendas por sus renglones raros; al
aprobarlos quedan en catalogo, y la siguiente lista -de ese colegio o de
otro- los encuentra en casa. Las listas ya revisadas no consultan nada,
nunca: `version_lista_oficial.revisada_en` lo cierra y no se vuelve a abrir.

Esa regla no se sostiene con disciplina sino con la forma del modulo. El
codigo que sale a una tienda solo es alcanzable a traves de una version de
lista sin revisar; `--probar`, que es el match del acudiente, no tiene por
donde llegar a la red aunque uno quiera.

Lo que este modulo NO hace es decidir. Escribe propuestas, nunca productos.
La razon esta en lo que devuelve una busqueda por texto: pedirle `punzon
punta metalica` a la tienda trae lapices correctores de PUNTA FINA, que son
productos reales, con foto, con existencias y al precio esperado. Lo que
falla es el significado, y contra eso no hay umbral que valga. Una persona lo
ve en dos segundos; un puntaje de similitud, nunca.

Para los libros el alta casi nunca es una busqueda. Lo que identifica un
libro es el ISBN de una edicion concreta, y eso no sale de buscar por titulo,
asi que `--crear` deja escribirlo a mano. Tambien pasa por la misma cola.

Uso:

    # el match del acudiente: solo nuestra base, sin red
    python -m tukit_catalogo.descubrir --probar "aserrin de colores x 3 bolsas"

    # revisar un colegio nuevo: aqui, y solo aqui, se consulta una tienda
    python -m tukit_catalogo.descubrir --listas
    python -m tukit_catalogo.descubrir --revisar <version>
    python -m tukit_catalogo.descubrir --revisar <version> --crear-libro \\
        --isbn 9789587050585 --titulo "..." --precio 52000 --tienda panamericana

    python -m tukit_catalogo.descubrir --pendientes
    python -m tukit_catalogo.descubrir --aprobar <id> --nivel economico
    python -m tukit_catalogo.descubrir --rechazar <id> --motivo "es un corrector"
    python -m tukit_catalogo.descubrir --cerrar <version>
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import tiendas
from .cargador import AGENTE_FIRECRAWL, _uuid_estable, isbn13_valido, normalizar_isbn
from .enriquecer import atributos_de_ficha, extraer_atributos, extraer_empaque, extraer_personaje

# Cuanto puede costar algo de una lista escolar. Es un filtro grueso y basta:
# lo que descarta son las garrafas industriales de veinte litros y los lotes
# institucionales que la tienda mezcla con el articulo suelto.
PRECIO_MINIMO = 1000
PRECIO_MAXIMO = 400_000


def _plano(texto: str) -> str:
    sin_tildes = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_tildes).strip()


def _ean_valido(ean: str | None) -> str | None:
    """El EAN de una tienda solo se guarda si tiene la forma de un codigo real.

    Una tienda pone cualquier cosa en ese campo (un SKU interno, un vacio). Un
    EAN de verdad es 8, 12 o 13 digitos; lo demas se descarta a None para no
    ensuciar el catalogo con una referencia que no sirve para casar productos.
    """
    ean = (ean or "").strip()
    return ean if ean.isdigit() and len(ean) in (8, 12, 13) else None


VACIAS = frozenset({"de", "del", "la", "el", "los", "las", "un", "una", "y", "o", "para", "con", "en"})

# Ruido de las listas escolares que no ayuda a buscar en una tienda. La
# cantidad y el empaque describen CUANTO, no QUE, y meterlos en la consulta
# la empeora: buscar `3 bolsas de aserrin de colores` devuelve peor que
# `aserrin de colores`.
RUIDO = re.compile(
    r"\b(\d+\s*)?(unidades?|unds?|uds?|paquetes?|bolsas?|cajas?|docenas?|pares?|"
    r"rollos?|tarros?|frascos?|pliegos?|hojas?|juegos?|sets?|x\d+)\b"
)


def consulta_desde_renglon(renglon: str) -> str:
    """Convierte el renglon del colegio en algo que una tienda entienda.

    El colegio escribe `3 bolsas de aserrin de colores surtidos` y la tienda
    responde mejor a `aserrin de colores`. Se quitan las cantidades y los
    empaques porque dicen CUANTO y no QUE, y se dejan los adjetivos, que si
    discriminan: `de colores` separa el aserrin escolar del aserrin de
    carpinteria.
    """
    texto = _plano(renglon)
    texto = re.sub(r"[(),;:.]", " ", texto)
    texto = RUIDO.sub(" ", texto)
    texto = re.sub(r"\b\d+\s*(gr?|grs|gramos?|ml|cc|cm|mm|mts?|metros?)\b", " ", texto)
    texto = re.sub(r"^\s*\d+\s+", "", texto)
    palabras = [
        p for p in texto.split() if len(p) > 1 and p not in ("de", "del", "la", "el", "y", "o", "para", "con")
    ]
    return " ".join(palabras[:6])


@dataclass(frozen=True)
class Propuesta:
    concepto_id: uuid.UUID | None
    concepto_sugerido: str | None
    texto_origen: str
    oferta: tiendas.Oferta


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
    palabras = consulta_desde_renglon(renglon).split()
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


def _misma_cosa(a: str, b: str) -> bool:
    """Si dos palabras nombran la misma cosa, comparando singulares."""
    sa, sb = singular(a), singular(b)
    return sa[:5] == sb[:5] if min(len(sa), len(sb)) >= 5 else sa == sb


def clasificar(renglon: str, conceptos: list[dict[str, Any]]) -> tuple[uuid.UUID | None, str, float]:
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
    """
    mejor_id, mejor_nombre, mejor = None, "", 0.0
    nucleo = cabeza(renglon)
    for concepto in conceptos:
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
                # sobra de la frase.
                puntaje = 0.6 + 0.4 * _parecido(renglon, candidato)
            elif nombra_la_cabeza:
                puntaje = _parecido(renglon, candidato)
            else:
                puntaje = 0.0
            if puntaje > mejor:
                mejor_id, mejor_nombre, mejor = concepto["id"], concepto["nombre"], puntaje
    return mejor_id, mejor_nombre, mejor


def buscar_candidatos(consulta: str, ancla: str = "", cuantos: int = 3) -> list[tiendas.Oferta]:
    """Los mejores candidatos de las dos tiendas, repartidos por precio.

    El `ancla` es la palabra que nombra la cosa, y el candidato tiene que
    traerla en su nombre o no entra. Suena burdo y resuelve el fallo mas
    comun de estas busquedas: pedirle `aserrin colores surtidos` a Exito
    devuelve velas y un trapero, porque su buscador se queda con `colores
    surtidos` y suelta el sustantivo. Ninguna de esas velas se llama aserrin,
    asi que el filtro las tumba todas sin necesidad de entender nada.

    Se piden tres y no diez porque quien revisa no compara diez: mira los dos
    primeros y aprueba. Una cola de revision larga se abandona, y una cola
    abandonada es peor que no tenerla, porque aparenta un control que nadie
    ejerce.
    """
    encontrados: list[tiendas.Oferta] = []
    for tienda in tiendas.DOMINIOS:
        encontrados += [
            o
            for o in tiendas.buscar(tienda, consulta)
            if o.disponible and o.imagen_url and PRECIO_MINIMO <= o.precio_cop <= PRECIO_MAXIMO
        ]

    raiz = _plano(ancla or consulta).split()
    if raiz:
        # Se compara contra la raiz de la palabra y no contra la palabra
        # entera, para que `lapices` encuentre `lapiz` y `pompones` encuentre
        # `pompon`. Cinco letras alcanzan para no emparejar cosas distintas.
        prefijo = raiz[0][:5]
        encontrados = [o for o in encontrados if prefijo in _plano(o.nombre)]

    if not encontrados:
        return []

    ordenados = sorted(encontrados, key=lambda o: o.precio_cop)
    if len(ordenados) <= cuantos:
        return ordenados
    # Uno barato, uno de en medio y uno caro. Los extremos se evitan: el mas
    # barato de una busqueda suele ser un accesorio suelto y el mas caro un
    # empaque institucional.
    posiciones = [len(ordenados) // 6, len(ordenados) // 2, (5 * len(ordenados)) // 6]
    vistos, salida = set(), []
    for posicion in posiciones:
        elegido = ordenados[min(posicion, len(ordenados) - 1)]
        if elegido.sku not in vistos:
            vistos.add(elegido.sku)
            salida.append(elegido)
    return salida


NIVEL_POR_POSICION = ("economico", "confiable", "premium")


# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------


async def _contexto():
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    concepto = Base.metadata.tables["concepto"]
    tienda = Base.metadata.tables["tienda"]
    propuesta = Base.metadata.tables["propuesta_producto"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            conceptos = [
                {
                    "id": f.id,
                    "codigo": f.codigo,
                    "nombre": f.nombre_canonico,
                    "sinonimos": list(f.sinonimos or ()),
                    "attrs": tuple(f.atributos_discriminantes or ()) + tuple(f.atributos_descriptivos or ()),
                }
                for f in await conexion.execute(
                    select(
                        concepto.c.id,
                        concepto.c.codigo,
                        concepto.c.nombre_canonico,
                        concepto.c.sinonimos,
                        concepto.c.atributos_discriminantes,
                        concepto.c.atributos_descriptivos,
                    ).where(concepto.c.activo)
                )
            ]
            slugs = {f.slug: f.id for f in await conexion.execute(select(tienda.c.slug, tienda.c.id))}
            # Que niveles cubre ya NUESTRO catalogo para cada concepto. Es lo
            # que decide si hace falta salir a una tienda o no.
            producto = Base.metadata.tables["producto_canonico"]
            cobertura: dict[str, set[str]] = {}
            for f in await conexion.execute(
                select(producto.c.concepto_id, producto.c.nivel).where(producto.c.activo)
            ):
                cobertura.setdefault(str(f.concepto_id), set()).add(f.nivel)
            # Lo ya decidido, para no volver a preguntarlo. Es lo que hace que
            # rechazar sirva de algo.
            decididos = {
                (str(f.tienda_id), f.referencia_externa)
                for f in await conexion.execute(select(propuesta.c.tienda_id, propuesta.c.referencia_externa))
            }
            ofertados = {
                (str(f.tienda_id), f.referencia_externa)
                for f in await conexion.execute(
                    select(
                        Base.metadata.tables["oferta_tienda"].c.tienda_id,
                        Base.metadata.tables["oferta_tienda"].c.referencia_externa,
                    )
                )
            }
    finally:
        await motor.cerrar()
    return conceptos, slugs, decididos | ofertados, cobertura


async def _encolar(propuestas: list[dict[str, Any]]) -> int:
    from sqlalchemy.dialects.postgresql import insert
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    if not propuestas:
        return 0
    tabla = Base.metadata.tables["propuesta_producto"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            resultado = await conexion.execute(
                insert(tabla).values(propuestas).on_conflict_do_nothing(constraint="uq_propuesta_referencia")
            )
            return resultado.rowcount or 0
    finally:
        await motor.cerrar()


class PuertaCerrada(Exception):
    """Se intento salir a una tienda por una lista que ya esta revisada.

    Es un error y no un aviso. Si esto fuera tolerable, cada corrida volveria
    a consultar tiendas por listas resueltas hace meses: el catalogo dejaria
    de ser un cache que se llena y volveria a ser un buscador que paga lo
    mismo cada vez.
    """


def exigir_sin_revisar(id_corto: str, existe: bool, revisada_en: datetime | None) -> None:
    """La decision de la puerta, aparte de la consulta que trae los datos.

    Vive suelta para poder probarla. Enterrada dentro de la consulta, la
    unica forma de comprobar que una lista revisada no consulta tiendas
    seria montar una base y contar llamadas de red, que es justo la clase de
    prueba que nadie escribe.
    """
    if not existe:
        raise PuertaCerrada(f"No existe ninguna version de lista que empiece por {id_corto}")
    if revisada_en is not None:
        raise PuertaCerrada(
            f"Esa lista ya fue revisada el {revisada_en:%Y-%m-%d}. "
            "Una lista revisada se responde con el catalogo y no consulta tiendas."
        )


@dataclass(frozen=True)
class Revision:
    """Una version de lista abierta a revision, con sus renglones.

    Es la llave: `proponer` y `crear_libro` piden esto y no un texto, y lo
    unico que construye uno es `abrir_revision`, que comprueba la puerta. Por
    eso la regla no depende de que nadie se equivoque al llamar.
    """

    version_id: uuid.UUID
    colegio: str
    grado: str
    anio: int
    items: tuple[tuple[uuid.UUID, str], ...]


async def abrir_revision(id_corto: str) -> Revision:
    """Carga la version y comprueba la puerta ANTES de devolver los renglones.

    El orden importa: la comprobacion va aqui, en el unico sitio por el que
    se consiguen los renglones que disparan una busqueda. Ponerla en quien
    llama seria confiar en que todos los que llamen se acuerden.
    """
    from sqlalchemy import Text, cast, select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    version = Base.metadata.tables["version_lista_oficial"]
    lista = Base.metadata.tables["lista_oficial"]
    item = Base.metadata.tables["item_lista_oficial"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(
                        version.c.id,
                        version.c.numero,
                        version.c.revisada_en,
                        lista.c.colegio_id,
                        lista.c.grado,
                        lista.c.anio_lectivo,
                    )
                    .select_from(version.join(lista, lista.c.id == version.c.lista_id))
                    .where(cast(version.c.id, Text).like(f"{id_corto}%"))
                )
            ).first()
            exigir_sin_revisar(id_corto, fila is not None, fila.revisada_en if fila else None)
            assert fila is not None
            renglones = tuple(
                (f.id, f.texto_original)
                for f in await conexion.execute(
                    select(item.c.id, item.c.texto_original)
                    .where(item.c.version_id == fila.id)
                    .order_by(item.c.orden)
                )
            )
    finally:
        await motor.cerrar()

    return Revision(
        version_id=fila.id,
        colegio=str(fila.colegio_id)[:8],
        grado=fila.grado,
        anio=fila.anio_lectivo,
        items=renglones,
    )


async def proponer(revision: Revision) -> None:
    conceptos, slugs, ya_decididos, cobertura = await _contexto()
    renglones = [texto for _, texto in revision.items]
    ids_item = {texto: iid for iid, texto in revision.items}
    print(f"Revision de {revision.colegio} {revision.grado} {revision.anio}")
    print(f"Renglones a resolver: {len(renglones)}\n")

    propuestas: list[dict[str, Any]] = []
    en_casa = fuera = 0
    for renglon in renglones:
        concepto_id, nombre_concepto, parecido = clasificar(renglon, conceptos)
        consulta = consulta_desde_renglon(renglon)

        # Por debajo de este parecido no se fuerza el renglon dentro de un
        # concepto existente. Es preferible proponer un concepto nuevo, que
        # una persona puede fusionar en un minuto, a colgar pompones del
        # concepto de plastilina porque se parecian un poco.
        if parecido < 0.5:
            print(f"  {renglon[:44]:46} -> CONCEPTO NUEVO: {consulta}")
            concepto_id, sugerido = None, consulta[:128]
        else:
            concepto_id, sugerido = concepto_id, None
            nuestros = cobertura.get(str(concepto_id), set())
            # LA PREGUNTA QUE VA PRIMERO: ya lo tenemos?
            #
            # Salir a una tienda por algo que el catalogo ya surte es no
            # tener catalogo. La tienda es una fuente de ALTA, no de
            # consulta: solo se acude a ella cuando nuestra base no puede
            # responder, y aun asi lo que trae pasa por revision humana antes
            # de existir para un papa.
            if len(nuestros) >= 3:
                en_casa += 1
                print(f"  {renglon[:44]:46} -> {nombre_concepto}: YA LO TENEMOS")
                print(f"     {len(nuestros)} niveles en catalogo, no se consulta ninguna tienda")
                continue
            faltan = {"economico", "confiable", "premium"} - nuestros
            print(f"  {renglon[:44]:46} -> {nombre_concepto} ({parecido:.0%})")
            print(f"     lo tenemos a medias: falta {', '.join(sorted(faltan))}")

        fuera += 1
        # El ancla es el nombre del concepto cuando se reconocio: es mas
        # fiable que la primera palabra del renglon, que a veces es un
        # adjetivo o un resto de cantidad.
        candidatos = buscar_candidatos(consulta, ancla=nombre_concepto if concepto_id else consulta)
        nuevos = [c for c in candidatos if (str(slugs.get(c.tienda)), c.sku) not in ya_decididos]
        print(f"     se consulta la tienda: {len(candidatos)} candidatos, {len(nuevos)} sin decidir")

        for posicion, oferta in enumerate(nuevos):
            print(f"       ${oferta.precio_cop:>7}  {oferta.tienda:13} {oferta.nombre[:46]}")
            propuestas.append(
                {
                    "id": _uuid_estable("propuesta", oferta.tienda, oferta.sku),
                    "concepto_id": concepto_id,
                    "concepto_sugerido": sugerido,
                    "texto_origen": renglon,
                    "tienda_id": slugs[oferta.tienda],
                    "referencia_externa": oferta.sku,
                    "url": oferta.url or None,
                    "nombre": oferta.nombre[:512],
                    "marca": oferta.marca,
                    "ean": oferta.ean,
                    "imagen_url": oferta.imagen_url,
                    "precio_centavos": oferta.precio_cop * 100,
                    "disponible": oferta.disponible,
                    "especificaciones": oferta.especificaciones,
                    "nivel_sugerido": NIVEL_POR_POSICION[min(posicion, 2)],
                    "puntaje": round(min(parecido, 0.9), 3) if concepto_id else 0.3,
                    "estado": "pendiente",
                    "origen": "scraper",
                    "version_lista_id": revision.version_id,
                    "item_lista_id": ids_item.get(renglon),
                }
            )

    encoladas = await _encolar(propuestas)
    print(f"\n  resueltos con nuestro catalogo, sin salir  {en_casa}/{len(renglones)}")
    print(f"  hubo que consultar una tienda              {fuera}/{len(renglones)}")
    print(f"\nEncoladas para revision: {encoladas}")
    print("Revisalas con  --pendientes  y resuelvelas con  --aprobar / --rechazar")
    print(f"Cuando no quede nada pendiente:  --cerrar {str(revision.version_id)[:8]}")


async def listar_pendientes() -> None:
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    propuesta = Base.metadata.tables["propuesta_producto"]
    concepto = Base.metadata.tables["concepto"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            filas = (
                await conexion.execute(
                    select(
                        propuesta.c.id,
                        propuesta.c.texto_origen,
                        propuesta.c.nombre,
                        propuesta.c.precio_centavos,
                        propuesta.c.nivel_sugerido,
                        propuesta.c.concepto_sugerido,
                        concepto.c.nombre_canonico,
                    )
                    .select_from(propuesta.outerjoin(concepto, concepto.c.id == propuesta.c.concepto_id))
                    .where(propuesta.c.estado == "pendiente")
                    .order_by(propuesta.c.propuesta_en)
                )
            ).all()
    finally:
        await motor.cerrar()

    if not filas:
        print("No hay nada pendiente de revisar.")
        return
    print(f"{len(filas)} propuestas pendientes\n")
    for f in filas:
        destino = f.nombre_canonico or f"nuevo: {f.concepto_sugerido}"
        print(f"  {str(f.id)[:8]}  {destino[:22]:24} <- pedido: {f.texto_origen[:30]}")
        print(f"            ${f.precio_centavos // 100:>7} {f.nivel_sugerido or '-':10} {f.nombre[:52]}")


async def resolver(
    id_corto: str,
    aprobar: bool,
    nivel: str | None,
    motivo: str | None,
    no_surtir: bool = False,
) -> int:
    """Aprueba o rechaza, y si aprueba crea el producto con su oferta y precio.

    Aprobar no es marcar una casilla: es el momento en que nace el producto
    canonico, su oferta en esa tienda y su primer precio observado. Se hace en
    una sola transaccion porque un producto sin oferta no se puede comprar y
    una oferta sin precio no se puede sumar al kit; las tres cosas valen
    juntas o no valen.

    Rechazar tiene dos sabores. El corriente descarta ESTA propuesta y deja el
    concepto abierto para otra: quiza el candidato no servia pero el util si se
    ofrece. Con `no_surtir`, el rechazo es sobre el concepto entero: se marca
    `tipo_item = 'no_comprar'`, que es como el catalogo dice "esto existe en la
    lista del colegio pero nosotros no lo vendemos". Eso saca al concepto del
    conteo de huecos (`_medir_carencias` ya excluye `no_comprar`) y es la senal
    que el flujo del papa lee para mandarselo aparte en vez de sumarlo al kit.
    """
    from sqlalchemy import Text, cast, select, update
    from sqlalchemy.dialects.postgresql import insert
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    propuesta = Base.metadata.tables["propuesta_producto"]
    concepto = Base.metadata.tables["concepto"]
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(propuesta).where(cast(propuesta.c.id, Text).like(f"{id_corto}%"))
                )
            ).first()
            if fila is None:
                print(f"No encuentro ninguna propuesta que empiece por {id_corto}")
                return 1
            if fila.estado != "pendiente":
                print(f"Esa propuesta ya esta {fila.estado}.")
                return 1

            if not aprobar:
                await conexion.execute(
                    update(propuesta)
                    .where(propuesta.c.id == fila.id)
                    .values(estado="rechazada", motivo=motivo, resuelta_en=datetime.now(UTC))
                )
                print(f"Rechazada: {fila.nombre[:50]}")
                if motivo:
                    print(f"  motivo: {motivo}")
                if no_surtir:
                    if fila.concepto_id is None:
                        print("  (no se marco no_comprar: la propuesta no tiene concepto asociado)")
                    else:
                        await conexion.execute(
                            update(concepto)
                            .where(concepto.c.id == fila.concepto_id)
                            .values(tipo_item="no_comprar")
                        )
                        print("  concepto marcado 'no_comprar': no se lo ofrecemos al papa.")
                return 0

            if fila.concepto_id is None:
                print("Esta propuesta no tiene concepto. Primero hay que crear el concepto")
                print(f"  sugerido: {fila.concepto_sugerido}")
                return 1

            attrs_concepto = (
                await conexion.execute(
                    select(
                        Base.metadata.tables["concepto"].c.atributos_discriminantes,
                        Base.metadata.tables["concepto"].c.atributos_descriptivos,
                    ).where(Base.metadata.tables["concepto"].c.id == fila.concepto_id)
                )
            ).one()
            attrs_concepto = tuple(attrs_concepto[0] or ()) + tuple(attrs_concepto[1] or ())

            empaque = extraer_empaque(fila.nombre, attrs_concepto)
            atributos = {
                **atributos_de_ficha(fila.especificaciones or {}, attrs_concepto),
                **extraer_atributos(fila.nombre, attrs_concepto),
            }

            pid = _uuid_estable("aprobado", str(fila.tienda_id), fila.referencia_externa)
            await conexion.execute(
                insert(Base.metadata.tables["producto_canonico"])
                .values(
                    id=pid,
                    concepto_id=fila.concepto_id,
                    ean=fila.ean,
                    sku_interno=f"TK-REV-{fila.referencia_externa}"[:64],
                    nombre=fila.nombre[:255],
                    marca=fila.marca,
                    nivel=nivel or fila.nivel_sugerido or "confiable",
                    personaje=extraer_personaje(fila.nombre),
                    imagen_url=fila.imagen_url,
                    unidad_base=empaque.unidad_base,
                    unidades_por_empaque=empaque.unidades,
                    atributos=atributos,
                    es_propio=False,
                    es_representante_canonico=False,
                    activo=True,
                    # Lo miro una persona: vale mas que cualquier sugerencia
                    # automatica y menos que la curaduria original hecha sobre
                    # la lista del colegio en la mano.
                    quality_score=0.85,
                    curado_por=AGENTE_FIRECRAWL,
                )
                .on_conflict_do_nothing()
            )

            oferta_id = _uuid_estable("aprobado-oferta", str(fila.tienda_id), fila.referencia_externa)
            await conexion.execute(
                insert(Base.metadata.tables["oferta_tienda"])
                .values(
                    id=oferta_id,
                    producto_canonico_id=pid,
                    tienda_id=fila.tienda_id,
                    referencia_externa=fila.referencia_externa,
                    url=fila.url,
                    metodo_vinculacion="ean" if fila.ean else "manual",
                    confianza_vinculacion=0.85,
                    disponible=fila.disponible,
                    activo=True,
                )
                .on_conflict_do_nothing()
            )
            await conexion.execute(
                insert(Base.metadata.tables["precio_oferta"])
                .values(
                    id=_uuid_estable("aprobado-precio", str(fila.tienda_id), fila.referencia_externa),
                    oferta_id=oferta_id,
                    valor_centavos=fila.precio_centavos,
                    moneda="COP",
                    fuente="scraper",
                    vigente_desde=datetime.now(UTC),
                )
                .on_conflict_do_nothing()
            )
            await conexion.execute(
                update(propuesta)
                .where(propuesta.c.id == fila.id)
                .values(
                    estado="aprobada",
                    producto_canonico_id=pid,
                    resuelta_en=datetime.now(UTC),
                )
            )
    finally:
        await motor.cerrar()

    print(f"Aprobada y en catalogo: {fila.nombre[:52]}")
    resumen = f"nivel {nivel or fila.nivel_sugerido}  ${fila.precio_centavos // 100:,}"
    print(f"  {resumen}  empaque x{empaque.unidades}")
    if atributos:
        print(f"  atributos: {atributos}")
    return 0


async def probar(renglones: list[str]) -> None:
    """Lo que veria un acudiente: el match contra NUESTRA base y nada mas.

    No existe aqui ninguna forma de llegar a una tienda, y es a proposito.
    Esta funcion es la que responde una lista en produccion, y en produccion
    una lista se responde con el catalogo: si no esta, no esta, y se muestra
    como no resuelto. Consultar Exito en ese momento seria mostrarle al
    acudiente un producto que nadie ha verificado que podamos conseguir.
    """
    conceptos, _slugs, _decididos, cobertura = await _contexto()
    print(f"Contra nuestro catalogo, sin salir a ninguna tienda: {len(renglones)} renglones\n")
    resueltos = 0
    for renglon in renglones:
        concepto_id, nombre, parecido = clasificar(renglon, conceptos)
        niveles = cobertura.get(str(concepto_id), set()) if concepto_id else set()
        if parecido >= 0.5 and niveles:
            resueltos += 1
            cubre = ", ".join(sorted(niveles))
            print(f"  OK       {renglon[:40]:42} -> {nombre[:20]:22} [{cubre}]")
        elif parecido >= 0.5:
            print(f"  SIN QUE  {renglon[:40]:42} -> {nombre[:20]:22} concepto sin producto")
        else:
            print(f"  NO       {renglon[:40]:42} -> no lo reconocemos")
    print(f"\n  resueltos con catalogo  {resueltos}/{len(renglones)}")
    if resueltos < len(renglones):
        print("  el resto necesita revision de un administrador para darse de alta")


async def listar_listas() -> None:
    """Las versiones sin revisar, que son las unicas que abren la puerta."""
    from sqlalchemy import func as f_sql
    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    version = Base.metadata.tables["version_lista_oficial"]
    lista = Base.metadata.tables["lista_oficial"]
    item = Base.metadata.tables["item_lista_oficial"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            filas = (
                await conexion.execute(
                    select(
                        version.c.id,
                        version.c.numero,
                        version.c.revisada_en,
                        lista.c.colegio_id,
                        lista.c.grado,
                        lista.c.anio_lectivo,
                        f_sql.count(item.c.id).label("renglones"),
                    )
                    .select_from(
                        version.join(lista, lista.c.id == version.c.lista_id).outerjoin(
                            item, item.c.version_id == version.c.id
                        )
                    )
                    .group_by(
                        version.c.id,
                        version.c.numero,
                        version.c.revisada_en,
                        lista.c.colegio_id,
                        lista.c.grado,
                        lista.c.anio_lectivo,
                    )
                    .order_by(version.c.revisada_en.is_(None).desc(), lista.c.grado)
                )
            ).all()
    finally:
        await motor.cerrar()

    if not filas:
        print("No hay listas cargadas todavia.")
        return
    sin_revisar = [f for f in filas if f.revisada_en is None]
    print(f"{len(filas)} versiones de lista, {len(sin_revisar)} sin revisar\n")
    for f in filas:
        estado = "SIN REVISAR" if f.revisada_en is None else f"revisada {f.revisada_en:%Y-%m-%d}"
        print(
            f"  {str(f.id)[:8]}  {str(f.colegio_id)[:8]} {f.grado[:14]:16} "
            f"{f.anio_lectivo}  v{f.numero}  {f.renglones:>3} renglones  {estado}"
        )


async def crear_libro(
    id_corto: str,
    isbn: str,
    titulo: str,
    precio_cop: int,
    tienda: str,
    url: str | None,
    imagen: str | None,
    concepto: str | None,
) -> int:
    """Alta a mano de un libro, dentro de una revision abierta.

    Los libros no se dan de alta buscando. Lo que identifica un libro es el
    ISBN de una edicion concreta -misma obra, distinto ISBN, distinto precio
    y distinto contenido-, y una busqueda por titulo no distingue ediciones.
    Asi que quien revisa escribe el ISBN que el colegio pidio.

    Pasa por la misma cola que lo que trae el scraper, aunque lo haya
    escrito una persona. Encolarlo no es desconfianza: es que el alta de un
    producto es siempre el mismo camino, con los mismos datos minimos, y dos
    caminos distintos para lo mismo se separan con el tiempo.
    """
    revision = await abrir_revision(id_corto)

    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    # El digito de control se comprueba antes de tocar la base. Un ISBN mal
    # copiado no falla ruidosamente: entra, y el dia de la compra resulta ser
    # otra edicion o ningun libro. Es el tipo de error que solo se descubre
    # cuando ya hay alguien esperando su pedido.
    isbn = normalizar_isbn(isbn) or ""
    if not isbn13_valido(isbn):
        print(f"El ISBN '{isbn}' no pasa el digito de control. Revisalo antes de darlo de alta.")
        return 1

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            tabla_tienda = Base.metadata.tables["tienda"]
            tienda_id = (
                await conexion.execute(select(tabla_tienda.c.id).where(tabla_tienda.c.slug == tienda))
            ).scalar_one_or_none()
            if tienda_id is None:
                print(f"No conozco la tienda '{tienda}'.")
                return 1
            concepto_id = None
            if concepto:
                tabla_concepto = Base.metadata.tables["concepto"]
                concepto_id = (
                    await conexion.execute(
                        select(tabla_concepto.c.id).where(tabla_concepto.c.codigo == concepto)
                    )
                ).scalar_one_or_none()
                if concepto_id is None:
                    print(f"No existe el concepto '{concepto}'.")
                    return 1
    finally:
        await motor.cerrar()

    encoladas = await _encolar(
        [
            {
                "id": _uuid_estable("propuesta", tienda, isbn),
                "concepto_id": concepto_id,
                "concepto_sugerido": None if concepto_id else titulo[:128],
                "texto_origen": titulo,
                "tienda_id": tienda_id,
                "referencia_externa": isbn,
                "url": url,
                "nombre": titulo[:512],
                "marca": None,
                "ean": isbn,
                "imagen_url": imagen,
                "precio_centavos": precio_cop * 100,
                "disponible": True,
                "especificaciones": {"isbn": isbn},
                "nivel_sugerido": "confiable",
                # Lo escribio una persona con la lista del colegio delante,
                # que es mejor evidencia que cualquier busqueda por texto.
                "puntaje": 0.9,
                "estado": "pendiente",
                "origen": "manual",
                "version_lista_id": revision.version_id,
                "item_lista_id": None,
            }
        ]
    )
    if not encoladas:
        print(f"Ese ISBN ya estaba propuesto para {tienda}.")
        return 0
    print(f"Encolado a mano: {titulo[:52]}")
    print(f"  ISBN {isbn}  ${precio_cop:,}  {tienda}")
    print("Apruebalo con  --aprobar  cuando lo verifiques.")
    return 0


async def crear_util(
    id_corto: str,
    concepto: str,
    consulta: str,
    elegir: int | None,
) -> int:
    """Alta de un util APOYADA en las tiendas, no un formulario a ciegas.

    Un util no se identifica por ISBN, asi que a diferencia de un libro hay que
    encontrarlo. En vez de que el administrador copie a mano nombre, precio,
    marca e imagen, este comando consulta las tres tiendas que ya usa el
    catalogo -Exito y Panamericana por VTEX, Grancentral por Shopify- reusando
    el mismo cliente con cache y el mismo quinto filtro (`_coincide`: todas las
    palabras de la consulta tienen que estar en el nombre) que impide que entre
    un cuchillo cuando se busca una tabla de picar.

    El flujo es en dos pasos, a proposito:

      1. Sin `--elegir`, LISTA los candidatos numerados y no escribe nada. Es la
         pantalla de "esto encontre" que el administrador mira.
      2. Con `--elegir N`, ENCOLA ese candidato como propuesta contra el
         concepto dado. No lo mete al catalogo: pasa por la misma cola que todo
         lo demas, y solo se vuelve producto cuando se aprueba (`--aprobar`),
         que es cuando `resolver` le saca empaque y atributos del nombre.

    Pasa por `abrir_revision` igual que `crear_libro`: salir a una tienda exige
    una lista sin revisar. El util nuevo, al aprobarse, queda en el catalogo y
    surte a la siguiente lista que lo pida: eso es el cache que se llena.
    """
    revision = await abrir_revision(id_corto)

    from sqlalchemy import select
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    # El concepto tiene que existir: un util cuelga de una necesidad que el
    # colegio ya pidio, no de un texto suelto. Se resuelve su id y su nombre
    # antes de gastar una sola consulta a las tiendas.
    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            tabla_concepto = Base.metadata.tables["concepto"]
            fila_concepto = (
                await conexion.execute(
                    select(tabla_concepto.c.id, tabla_concepto.c.nombre_canonico).where(
                        tabla_concepto.c.codigo == concepto
                    )
                )
            ).first()
            if fila_concepto is None:
                print(f"No existe el concepto '{concepto}'. Mira los codigos con --pendientes o el CSV.")
                return 1
            tabla_tienda = Base.metadata.tables["tienda"]
            slugs = {
                f.slug: f.id for f in await conexion.execute(select(tabla_tienda.c.slug, tabla_tienda.c.id))
            }
    finally:
        await motor.cerrar()

    # Las tres tiendas, con su quinto filtro puesto. Se marca de que tienda vino
    # cada oferta para poder encolarla despues contra la `tienda_id` correcta.
    candidatos: list[tuple[str, Any]] = []
    for slug in ("exito", "panamericana", "grancentral"):
        if slug not in slugs:
            continue
        for oferta in tiendas.buscar(slug, consulta):
            if not tiendas._coincide(oferta.nombre, consulta):
                continue
            if oferta.precio_cop <= 0 or not oferta.disponible:
                continue
            candidatos.append((slug, oferta))

    # De mas barato a mas caro: es el orden en que el administrador razona los
    # tres niveles, y el mismo que usa `completar`.
    candidatos.sort(key=lambda par: par[1].precio_cop)

    if not candidatos:
        print(f"Ninguna tienda devolvio algo que contenga '{consulta}'.")
        print("Prueba otra consulta, o da de alta el dato a mano si lo surte un distribuidor fisico.")
        return 0

    if elegir is None:
        print(f"Candidatos para {concepto} ({fila_concepto.nombre_canonico}) con '{consulta}':\n")
        for indice, (slug, oferta) in enumerate(candidatos):
            marca = f"  [{oferta.marca}]" if oferta.marca else ""
            print(f"  {indice:2}  ${oferta.precio_cop:>8,}  {slug:13} {oferta.nombre[:48]}{marca}")
        print(f"\n{len(candidatos)} candidatos. Encola el que sirva con  --elegir N.")
        return 0

    if not 0 <= elegir < len(candidatos):
        print(f"El indice {elegir} no existe: hay {len(candidatos)} candidatos (0 a {len(candidatos) - 1}).")
        return 1

    slug, oferta = candidatos[elegir]
    encoladas = await _encolar(
        [
            {
                "id": _uuid_estable("util", slug, oferta.sku),
                "concepto_id": fila_concepto.id,
                "concepto_sugerido": None,
                "texto_origen": fila_concepto.nombre_canonico,
                "tienda_id": slugs[slug],
                "referencia_externa": oferta.sku,
                "url": oferta.url or None,
                "nombre": oferta.nombre[:512],
                "marca": oferta.marca,
                "ean": _ean_valido(oferta.ean),
                "imagen_url": oferta.imagen_url,
                # La ficha cruda de la tienda, para que al aprobar `resolver`
                # pueda leer los atributos que el nombre no diga.
                "especificaciones": oferta.especificaciones or {},
                "precio_centavos": oferta.precio_cop * 100,
                "disponible": oferta.disponible,
                "nivel_sugerido": None,
                # Lo eligio una persona de una lista de candidatos, mas alto que
                # lo que `completar` encola solo pero por debajo de un libro con
                # ISBN verificado: sigue siendo una tienda, no una ficha exacta.
                "puntaje": 0.6,
                "estado": "pendiente",
                "origen": "manual",
                "version_lista_id": revision.version_id,
                "item_lista_id": None,
            }
        ]
    )
    if not encoladas:
        print(f"Ese producto de {slug} ya estaba propuesto.")
        return 0
    print(f"Encolado para {concepto}: {oferta.nombre[:50]}")
    print(f"  ${oferta.precio_cop:,}  {slug}")
    print("Elige su nivel y apruebalo con  --aprobar ID --nivel <economico|confiable|premium>.")
    return 0


async def cerrar(id_corto: str) -> int:
    """Marca la version como revisada y cierra la puerta para siempre.

    Se niega si queda algo pendiente. Cerrar con propuestas sin decidir seria
    dejar el renglon sin producto y sin forma de volver a intentarlo: la
    puerta cerrada impide reabrir la busqueda, asi que el renglon quedaria
    mudo en todos los kits futuros de ese grado.
    """
    from sqlalchemy import Text, cast, func, select, update
    from tukit_comun.bd import crear_motor

    from .modelos import Base

    version = Base.metadata.tables["version_lista_oficial"]
    propuesta = Base.metadata.tables["propuesta_producto"]

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            fila = (
                await conexion.execute(
                    select(version.c.id, version.c.revisada_en).where(
                        cast(version.c.id, Text).like(f"{id_corto}%")
                    )
                )
            ).first()
            if fila is None:
                print(f"No existe ninguna version que empiece por {id_corto}")
                return 1
            if fila.revisada_en is not None:
                print(f"Ya estaba revisada el {fila.revisada_en:%Y-%m-%d}.")
                return 0
            pendientes = (
                await conexion.execute(
                    select(func.count())
                    .select_from(propuesta)
                    .where(propuesta.c.version_lista_id == fila.id, propuesta.c.estado == "pendiente")
                )
            ).scalar_one()
            if pendientes:
                print(f"Quedan {pendientes} propuestas sin decidir de esta lista.")
                print("Resuelvelas antes de cerrar: despues no se puede volver a buscar.")
                return 1
            await conexion.execute(
                update(version).where(version.c.id == fila.id).values(revisada_en=datetime.now(UTC))
            )
    finally:
        await motor.cerrar()
    print("Lista revisada. De aqui en adelante se responde con el catalogo, sin consultar tiendas.")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--probar", help="un renglon a resolver SOLO contra nuestra base")
    analizador.add_argument(
        "--desde-lista", type=Path, help="archivo con un renglon por linea, para --probar"
    )
    analizador.add_argument(
        "--listas", action="store_true", help="versiones de lista y su estado de revision"
    )
    analizador.add_argument("--revisar", metavar="VERSION", help="revisar una version sin revisar")
    analizador.add_argument("--cerrar", metavar="VERSION", help="dar por revisada una version")
    analizador.add_argument("--crear-libro", action="store_true", help="alta a mano, requiere --revisar")
    analizador.add_argument(
        "--crear-util",
        action="store_true",
        help="alta de un util apoyada en las tiendas, requiere --revisar --concepto --consulta",
    )
    analizador.add_argument("--isbn")
    analizador.add_argument("--titulo")
    analizador.add_argument("--precio", type=int, help="en pesos, sin centavos")
    analizador.add_argument("--tienda")
    analizador.add_argument("--url")
    analizador.add_argument("--imagen")
    analizador.add_argument("--concepto", help="codigo del concepto, por ejemplo C048")
    analizador.add_argument("--consulta", help="texto a buscar en las tiendas, para --crear-util")
    analizador.add_argument(
        "--elegir", type=int, metavar="N", help="numero del candidato a encolar, para --crear-util"
    )
    analizador.add_argument("--pendientes", action="store_true")
    analizador.add_argument("--aprobar", metavar="ID")
    analizador.add_argument("--rechazar", metavar="ID")
    analizador.add_argument("--nivel", choices=NIVEL_POR_POSICION)
    analizador.add_argument("--motivo")
    analizador.add_argument(
        "--no-surtir",
        action="store_true",
        help="al rechazar, marca el concepto 'no_comprar': no se lo ofrecemos al papa",
    )
    args = analizador.parse_args()

    if args.listas:
        return asyncio.run(listar_listas()) or 0
    if args.pendientes:
        return asyncio.run(listar_pendientes()) or 0
    if args.aprobar:
        return asyncio.run(resolver(args.aprobar, True, args.nivel, None))
    if args.rechazar:
        return asyncio.run(resolver(args.rechazar, False, None, args.motivo, args.no_surtir))
    if args.cerrar:
        return asyncio.run(cerrar(args.cerrar))

    renglones = []
    if args.probar:
        renglones.append(args.probar)
    if args.desde_lista:
        renglones += [ln.strip() for ln in args.desde_lista.read_text().splitlines() if ln.strip()]
    if renglones:
        return asyncio.run(probar(renglones)) or 0

    if args.crear_libro:
        if not args.revisar:
            print("El alta a mano va dentro de una revision: agrega --revisar <version>.")
            return 2
        faltan = [n for n in ("isbn", "titulo", "precio", "tienda") if getattr(args, n) is None]
        if faltan:
            print(f"Para dar de alta un libro faltan: {', '.join('--' + n for n in faltan)}")
            return 2
        try:
            return asyncio.run(
                crear_libro(
                    args.revisar,
                    args.isbn,
                    args.titulo,
                    args.precio,
                    args.tienda,
                    args.url,
                    args.imagen,
                    args.concepto,
                )
            )
        except PuertaCerrada as error:
            print(error)
            return 1

    if args.crear_util:
        if not args.revisar:
            print("El alta de un util va dentro de una revision: agrega --revisar <version>.")
            return 2
        faltan = [n for n in ("concepto", "consulta") if getattr(args, n) is None]
        if faltan:
            print(f"Para dar de alta un util faltan: {', '.join('--' + n for n in faltan)}")
            return 2
        try:
            return asyncio.run(crear_util(args.revisar, args.concepto, args.consulta, args.elegir))
        except PuertaCerrada as error:
            print(error)
            return 1

    if args.revisar:
        try:
            revision = asyncio.run(abrir_revision(args.revisar))
        except PuertaCerrada as error:
            print(error)
            return 1
        return asyncio.run(proponer(revision)) or 0

    analizador.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
