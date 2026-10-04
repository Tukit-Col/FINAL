"""Empareja un renglon contra NUESTRO catalogo. Nada mas.

Es la pregunta que va primero: ya lo tenemos? El clasificador y los
atributos son los que ya se afinaron sobre el corpus; aqui no hay un
segundo algoritmo. Lo que se agrega es la consecuencia de haberlos
afinado: si el renglon impone un atributo y ningun producto lo declara,
no se ofrece otro. "Block oficio" no se responde con origami.

Quien atiende a un acudiente no tiene por donde salir a la red, y hay
una prueba que lee este archivo para que eso siga siendo cierto.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import asdict, dataclass
from typing import Any

from .descubrir import clasificar
from .embeddings import Embeder, promedio
from .enriquecer import extraer_atributos
from .transcripcion import corregir, lexico_de

_ORDEN_NIVEL = ("economico", "confiable", "premium")

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Opcion:
    sku: str
    nombre: str
    nivel: str
    personaje: str | None
    atributos: dict[str, Any]
    precio_cop: int | None
    cumple: bool
    # Las cuatro de abajo no las usa la decision de emparejar: las usa quien
    # PINTA la opcion o quien la mete en un carrito. Viajan aqui porque el
    # consumidor de este resultado esta en otro proceso —`inteligencia` no
    # puede leer esta base— y pedirle que vuelva a consultar producto por
    # producto por el sku seria una llamada por renglon de la lista.
    #
    # Sin `unidades_por_empaque` no se puede calcular cuantos comprar, y ese
    # numero es justo el que el sistema anterior no tenia y por el que sumaba
    # doce cajas cuando la lista pedia doce lapices.
    marca: str | None = None
    imagen_url: str | None = None
    unidad_base: str = "unidad"
    unidades_por_empaque: int = 1
    # El identificador del producto canonico, no su sku. Lo pide el
    # manifiesto: `inteligencia.candidato_item.producto_canonico_id` y
    # `comercio.linea_pedido.producto_canonico_id` son referencias logicas
    # declaradas a ESTA tabla, y sin el valor la referencia no resolveria.
    # Va como cadena porque cruza por HTTP.
    producto_id: str | None = None


@dataclass(frozen=True)
class Emparejamiento:
    texto: str
    texto_corregido: str
    estado: str
    concepto_codigo: str | None
    concepto_nombre: str | None
    parecido: float
    atributos_impuestos: dict[str, Any]
    motivo: str
    opciones: tuple[Opcion, ...]
    # El tipo del concepto reconocido (util, uniforme, no_comprar...). Viaja para
    # que quien arma el kit sepa si el renglon se busca en el catalogo o es una
    # linea informativa, sin adivinarlo del texto. Nulo si no se reconocio.
    concepto_tipo_item: str | None = None

    def a_dict(self) -> dict[str, Any]:
        datos = asdict(self)
        datos["opciones"] = [asdict(o) for o in self.opciones]
        return datos


def _elegir_por_nivel(productos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Una opcion por nivel, y la de marca antes que la de personaje.

    El personaje es una via aparte: el cuaderno de Bluey no compite contra
    el cuaderno pelado por el puesto de "lo que el colegio pidio". Si en un
    nivel hay los dos, se muestra el de marca. El de personaje se ofrece
    cuando el acudiente lo pida, no de oficio.
    """
    por_nivel: dict[str, dict[str, Any]] = {}
    for producto in productos:
        nivel = producto.get("nivel") or ""
        actual = por_nivel.get(nivel)
        if actual is None:
            por_nivel[nivel] = producto
            continue
        # Sin personaje gana. A igualdad, el sku menor, para que la
        # respuesta no dependa del orden en que la base devolvio las filas.
        clave = (producto.get("personaje") is not None, producto.get("sku") or "")
        clave_actual = (actual.get("personaje") is not None, actual.get("sku") or "")
        if clave < clave_actual:
            por_nivel[nivel] = producto
    return [por_nivel[nivel] for nivel in _ORDEN_NIVEL if nivel in por_nivel]


def _cumple(producto: dict[str, Any], impuestos: dict[str, Any]) -> bool:
    declarados = {k: str(v).lower() for k, v in (producto.get("atributos") or {}).items()}
    return all(declarados.get(k) == str(v).lower() for k, v in impuestos.items())


def emparejar(
    texto: str,
    conceptos: list[dict[str, Any]],
    productos: list[dict[str, Any]],
    *,
    embedding_renglon: list[float] | None = None,
) -> Emparejamiento:
    """Clasifica el renglon y, si el catalogo puede cumplirlo, da hasta tres opciones.

    Tres, no treinta: una por nivel. El acudiente compara tres cosas. Una
    cola de blocks carta no es una respuesta, es el fallo que este corte
    existe para no repetir.

    `embedding_renglon` es el canal semantico (OE3): el vector del renglon
    entrante, que `clasificar` funde con el lexico. Es opcional para que quien
    no lo calcula —o corre sin el modelo— siga obteniendo el match lexico de
    siempre.
    """
    corregido = corregir(texto, lexico_de(conceptos))
    concepto_id, nombre, parecido = clasificar(corregido, conceptos, embedding_renglon=embedding_renglon)
    if parecido < 0.5 or concepto_id is None:
        return Emparejamiento(
            texto=texto,
            texto_corregido=corregido,
            estado="sin_match",
            concepto_codigo=None,
            concepto_nombre=None,
            parecido=parecido,
            atributos_impuestos={},
            motivo="No reconocemos que pide este renglon.",
            opciones=(),
        )

    concepto = next(c for c in conceptos if c["id"] == concepto_id)
    impuestos = extraer_atributos(corregido, tuple(concepto.get("discriminantes") or ()))
    del_concepto = [p for p in productos if p.get("concepto_id") == concepto_id]
    if not del_concepto:
        return Emparejamiento(
            texto=texto,
            texto_corregido=corregido,
            estado="hueco_catalogo",
            concepto_codigo=concepto.get("codigo"),
            concepto_tipo_item=concepto.get("tipo_item"),
            concepto_nombre=nombre,
            parecido=parecido,
            atributos_impuestos=impuestos,
            motivo=f"Entendimos {nombre} y el catalogo no tiene producto.",
            opciones=(),
        )

    candidatos = del_concepto
    if impuestos:
        que_cumplen = [p for p in del_concepto if _cumple(p, impuestos)]
        if not que_cumplen:
            pedido = ", ".join(f"{k}={v}" for k, v in impuestos.items())
            return Emparejamiento(
                texto=texto,
                texto_corregido=corregido,
                estado="abstencion",
                concepto_codigo=concepto.get("codigo"),
                concepto_tipo_item=concepto.get("tipo_item"),
                concepto_nombre=nombre,
                parecido=parecido,
                atributos_impuestos=impuestos,
                motivo=(
                    f"El renglon pide {nombre} con {pedido} y ninguno de los "
                    f"{len(del_concepto)} productos lo declara. No ofrezco otro."
                ),
                opciones=(),
            )
        candidatos = que_cumplen

    opciones = tuple(
        Opcion(
            sku=p.get("sku") or "",
            nombre=p.get("nombre") or "",
            nivel=p.get("nivel") or "",
            personaje=p.get("personaje"),
            atributos=dict(p.get("atributos") or {}),
            precio_cop=p.get("precio_cop"),
            cumple=_cumple(p, impuestos) if impuestos else True,
            marca=p.get("marca"),
            imagen_url=p.get("imagen_url"),
            unidad_base=p.get("unidad_base") or "unidad",
            unidades_por_empaque=int(p.get("unidades_por_empaque") or 1),
            producto_id=None if p.get("id") is None else str(p["id"]),
        )
        for p in _elegir_por_nivel(candidatos)
    )
    return Emparejamiento(
        texto=texto,
        texto_corregido=corregido,
        estado="reconocido",
        concepto_codigo=concepto.get("codigo"),
        concepto_tipo_item=concepto.get("tipo_item"),
        concepto_nombre=nombre,
        parecido=parecido,
        atributos_impuestos=impuestos,
        motivo="",
        opciones=opciones,
    )


async def cargar_indice(
    conexion: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Conceptos activos y sus productos, con el precio vigente mas bajo.

    Recibe una conexion YA ABIERTA. Antes habia dos copias de esta consulta —una
    aqui que creaba un motor por llamada (solo alcanzable por CLI) y otra en la
    API que reusaba el motor del servicio pero NO leia embeddings—, y la de la
    API dejaba el canal semantico de OE3 muerto en produccion (coseno siempre 0).
    Ahora hay una: quien la llama trae la conexion (el servicio, su pool; la CLI,
    un motor efimero por `_cargar_indice_cli`), y el canal semantico vive en las
    dos vias porque el embedding del producto se carga una sola vez, aqui.

    El precio sale de la oferta, no del producto: un producto tiene varias
    tiendas y el numero que se le muestra al acudiente es el menor vigente.

    El vector del concepto se deriva del de sus productos (`promedio`): el centro
    de los cuadernos ES, en promedio, "cuaderno". El embedding crudo del producto
    no viaja en el dict de salida —se consume aqui para el promedio y se descarta—
    porque el consumidor (`emparejar`) solo necesita el del concepto.

    ponytail: index load = un par de SELECTs a escala tesis (~100 conceptos /
    ~261 productos); si el perfilado lo muestra en la ruta caliente, cachear en
    `app.state` con alcance de lifespan. No antes.
    """
    from sqlalchemy import func, select

    from .modelos import Base

    concepto = Base.metadata.tables["concepto"]
    producto = Base.metadata.tables["producto_canonico"]
    oferta = Base.metadata.tables["oferta_tienda"]
    precio = Base.metadata.tables["precio_oferta"]

    conceptos = [
        {
            "id": f.id,
            "codigo": f.codigo,
            "nombre": f.nombre_canonico,
            "sinonimos": list(f.sinonimos or ()),
            "discriminantes": tuple(f.atributos_discriminantes or ()),
            "tipo_item": f.tipo_item,
        }
        for f in await conexion.execute(
            select(
                concepto.c.id,
                concepto.c.codigo,
                concepto.c.nombre_canonico,
                concepto.c.sinonimos,
                concepto.c.atributos_discriminantes,
                concepto.c.tipo_item,
            ).where(concepto.c.activo.is_(True))
        )
    ]
    precio_min = (
        select(
            oferta.c.producto_canonico_id.label("pid"),
            func.min(precio.c.valor_centavos).label("centavos"),
        )
        .select_from(oferta.join(precio, precio.c.oferta_id == oferta.c.id))
        .where(oferta.c.activo.is_(True), precio.c.vigente_hasta.is_(None))
        .group_by(oferta.c.producto_canonico_id)
        .subquery()
    )
    productos = []
    emb_por_concepto: dict[Any, list[list[float]]] = {}
    for f in await conexion.execute(
        select(
            producto.c.id,
            producto.c.concepto_id,
            producto.c.sku_interno,
            producto.c.nombre,
            producto.c.nivel,
            producto.c.personaje,
            producto.c.marca,
            producto.c.imagen_url,
            producto.c.unidad_base,
            producto.c.unidades_por_empaque,
            producto.c.atributos,
            producto.c.embedding,
            precio_min.c.centavos,
        )
        .select_from(producto.outerjoin(precio_min, precio_min.c.pid == producto.c.id))
        .where(producto.c.activo.is_(True))
    ):
        productos.append(
            {
                "id": f.id,
                "concepto_id": f.concepto_id,
                "sku": f.sku_interno,
                "nombre": f.nombre,
                "nivel": f.nivel,
                "personaje": f.personaje,
                "marca": f.marca,
                "imagen_url": f.imagen_url,
                "unidad_base": f.unidad_base or "unidad",
                "unidades_por_empaque": int(f.unidades_por_empaque or 1),
                "atributos": dict(f.atributos or {}),
                "precio_cop": None if f.centavos is None else int(f.centavos) // 100,
            }
        )
        if f.embedding is not None:
            emb_por_concepto.setdefault(f.concepto_id, []).append(list(f.embedding))

    con_emb = 0
    for c in conceptos:
        c["embedding"] = promedio(emb_por_concepto.get(c["id"], []))
        if c["embedding"] is not None:
            con_emb += 1
    if conceptos and con_emb == 0:
        log.debug("indice sin embeddings poblados: el match sera solo lexico")
    return conceptos, productos


async def _cargar_indice_cli() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """`cargar_indice` para la CLI: abre y cierra su propio motor efimero.

    El servicio HTTP reusa su pool; un proceso `python -m ...consulta` no tiene
    pool que reusar, asi que crea un motor, lo usa y lo cierra.
    """
    from tukit_comun.bd import crear_motor

    motor = crear_motor("catalogo")
    try:
        async with motor.engine.begin() as conexion:
            return await cargar_indice(conexion)
    finally:
        await motor.cerrar()


async def emparejar_en_catalogo(
    renglones: list[str], *, embeder: Embeder | None = None
) -> list[Emparejamiento]:
    """Empareja una tanda de renglones contra el catalogo cargado.

    `embeder` es el canal semantico (OE3): si se pasa, se calcula el vector de
    cada renglon UNA vez (un lote, una peticion) y se funde en `clasificar`. Se
    resuelve por entorno cuando no se inyecta —con GEMINI_API_KEY, el real; sin
    ella, ninguno—, de modo que la consulta sigue dando el match lexico donde
    no hay modelo, sin fallar. El vector es del renglon entrante nada mas: no
    sale de la base ni entra a ella, asi que la invariante de que el acudiente
    no sale a nuestra red por producto se mantiene.
    """
    conceptos, productos = await _cargar_indice_cli()
    if embeder is None:
        embeder = _embeder_por_entorno()
    if embeder is None:
        log.debug("sin GEMINI_API_KEY: match lexico")
    vectores = calcular_vectores(renglones, embeder)
    return [
        emparejar(renglon, conceptos, productos, embedding_renglon=vec)
        for renglon, vec in zip(renglones, vectores, strict=True)
    ]


def calcular_vectores(renglones: list[str], embeder: Embeder | None) -> list[list[float] | None]:
    """El vector de cada renglon en un solo lote, o `None` por renglon si no hay
    embeder o si la llamada falla.

    El canal semantico DEGRADA, no tumba: si el proveedor no responde, la consulta
    sigue dando el match lexico. Se registra el fallo (antes era un `except`
    silencioso) para que "de repente todo es solo lexico" deje rastro.
    """
    if embeder is None or not renglones:
        return [None] * len(renglones)
    try:
        return list(embeder(list(renglones)))
    except Exception as exc:  # noqa: BLE001 - degrada a lexico, no tumba la consulta
        log.warning("canal semantico degradado a lexico: %s", exc)
        return [None] * len(renglones)


def _embeder_por_entorno() -> Embeder | None:
    """El embeder real si hay clave, ninguno si no. Igual criterio que enriquecer."""
    import os

    from .embeddings import embeder_gemini

    return embeder_gemini if os.environ.get("GEMINI_API_KEY", "").strip() else None


def _imprimir(resultado: Emparejamiento) -> None:
    if resultado.texto_corregido and resultado.texto_corregido != resultado.texto:
        print(f"  {resultado.texto[:70]}")
        print(f"  leido como {resultado.texto_corregido[:70]}")
    cabeza = f"{resultado.estado.upper():16} {resultado.texto_corregido[:42] or resultado.texto[:42]:44}"
    if resultado.concepto_nombre:
        cabeza += f" -> {resultado.concepto_nombre}"
        if resultado.atributos_impuestos:
            pedido = ", ".join(f"{k}={v}" for k, v in resultado.atributos_impuestos.items())
            cabeza += f"  [{pedido}]"
    print(cabeza)
    if resultado.motivo:
        print(f"  {resultado.motivo}")
    for opcion in resultado.opciones:
        precio = f"${opcion.precio_cop:,}" if opcion.precio_cop is not None else "sin precio"
        personaje = f"  {opcion.personaje}" if opcion.personaje else ""
        print(f"  {opcion.nivel:12} {precio:>12}  {opcion.nombre[:52]}{personaje}")


def main(argv: list[str] | None = None) -> int:
    """`python -m tukit_catalogo.consulta "block oficio" "2 lapices negros"`."""
    renglones = list(argv if argv is not None else sys.argv[1:])
    if not renglones:
        print("Pasa al menos un renglon.", file=sys.stderr)
        return 2
    for resultado in asyncio.run(emparejar_en_catalogo(renglones)):
        _imprimir(resultado)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
