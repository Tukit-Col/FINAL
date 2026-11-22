"""Empareja un renglon contra el catalogo propio.

Decisiones:
- Es la ruta de servicio: quien atiende a un acudiente no tiene por donde salir a la red, y una
  prueba lee este archivo para que siga siendo cierto.
- No hay un segundo algoritmo: usa el clasificador y la extraccion de atributos ya afinados. Si el
  renglon impone un atributo y ningun producto lo declara, no se ofrece otro ("block oficio" no
  se responde con origami).
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
from dataclasses import asdict, dataclass
from typing import Any

from .cache_vectores import vectores_guardados
from .clasificacion import clasificar
from .embeddings import Embeder, promedio
from .extraccion import extraer_atributos
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
    marca: str | None = None
    imagen_url: str | None = None
    unidad_base: str = "unidad"
    unidades_por_empaque: int = 1
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
    concepto_tipo_item: str | None = None

    def a_dict(self) -> dict[str, Any]:
        datos = asdict(self)
        datos["opciones"] = [asdict(o) for o in self.opciones]
        return datos


_VACIAS_TITULO = frozenset(
    "de del la las el los en y o a un una con para por al to the of and with an".split()
)
_CORTE_TITULO = re.compile(r"\(| \+ | - | / |,| with ", re.IGNORECASE)


def _palabras_titulo(texto: str) -> set[str]:
    import unicodedata

    plano = "".join(
        c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn"
    )
    return {p for p in re.findall(r"[a-z0-9+]+", plano) if len(p) > 1 and p not in _VACIAS_TITULO}


def pide_titulo(discriminantes: tuple[str, ...] | list[str]) -> bool:
    return "isbn13" in tuple(discriminantes or ())


def del_mismo_titulo(texto: str, productos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    del_renglon = _palabras_titulo(texto)
    elegidos = []
    for producto in productos:
        titulo = _palabras_titulo(_CORTE_TITULO.split(producto.get("nombre") or "", maxsplit=1)[0])
        if titulo and titulo <= del_renglon:
            elegidos.append(producto)
    return elegidos


def _elegir_por_nivel(productos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    por_nivel: dict[str, dict[str, Any]] = {}
    for producto in productos:
        nivel = producto.get("nivel") or ""
        actual = por_nivel.get(nivel)
        if actual is None:
            por_nivel[nivel] = producto
            continue
        clave = (producto.get("personaje") is not None, producto.get("sku") or "")
        clave_actual = (actual.get("personaje") is not None, actual.get("sku") or "")
        if clave < clave_actual:
            por_nivel[nivel] = producto
    return [por_nivel[nivel] for nivel in _ORDEN_NIVEL if nivel in por_nivel]


_NO_SE_EXIGEN = frozenset({("tipo", "escolar")})


_AL_MENOS: dict[str, float | None] = {
    "hojas": 2.0,
    "unidades": None,
    "colores": None,
    "piezas": None,
    "notas": None,
    "puntos": 2.2,
    "peso": None,
    "gramaje": None,
    "capacidad": None,
}
_TOLERANCIA: dict[str, tuple[float, float]] = {"longitud": (0.85, 1.35)}
_TOLERANCIA_MEDIDAS = 0.25
_EQUIVALENTES: dict[str, tuple[frozenset[str], ...]] = {
    "tamano": (frozenset({"carta", "a4"}),),
    "presentacion": (frozenset({"frasco", "tarro"}),),
    "material": (frozenset({"plastico", "antifluido"}), frozenset({"acero", "metal"})),
    "tipo": (frozenset({"gigante", "jumbo"}),),
}
_A_CM = {"mm": 0.1, "cm": 1.0, "m": 100.0, "in": 2.54}


def _numero(valor: Any) -> tuple[float, str] | None:
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int | float):
        return float(valor), ""
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*([a-z]*)", str(valor).lower())
    return (float(m.group(1)), m.group(2)) if m else None


def _medidas(valor: Any) -> list[float] | None:
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*cm\s*", str(valor).lower())
    return sorted((float(m.group(1)), float(m.group(2)))) if m else None


def _idioma_cumple(declarado: str, pedido: str) -> bool:
    if "-" in pedido or pedido == "espanol":
        return declarado == pedido or (pedido.split("-") == [declarado] * 2)
    return declarado in (pedido, f"{pedido}-{pedido}", "-".join(sorted({"espanol", pedido})))


def _valor_cumple(atributo: str, declarado: Any, pedido: Any) -> bool:
    texto_declarado, texto_pedido = str(declarado).lower(), str(pedido).lower()
    if texto_declarado == texto_pedido:
        return True
    if atributo == "idioma":
        return _idioma_cumple(texto_declarado, texto_pedido)
    if any({texto_declarado, texto_pedido} <= clase for clase in _EQUIVALENTES.get(atributo, ())):
        return True
    if atributo in _AL_MENOS:
        tiene, pide = _numero(declarado), _numero(pedido)
        if tiene is None or pide is None or tiene[1] != pide[1]:
            return False
        tope = _AL_MENOS[atributo]
        return tiene[0] >= pide[0] and (tope is None or tiene[0] <= pide[0] * tope)
    if atributo in _TOLERANCIA:
        tiene, pide = _numero(declarado), _numero(pedido)
        if tiene is None or pide is None or tiene[1] not in _A_CM or pide[1] not in _A_CM or not pide[0]:
            return False
        bajo, alto = _TOLERANCIA[atributo]
        razon = (tiene[0] * _A_CM[tiene[1]]) / (pide[0] * _A_CM[pide[1]])
        return bajo <= razon <= alto
    if atributo == "tamano":
        tiene_m, pide_m = _medidas(declarado), _medidas(pedido)
        if tiene_m and pide_m:
            return all(abs(t - p) < p * _TOLERANCIA_MEDIDAS for t, p in zip(tiene_m, pide_m, strict=True))
    return False


def _cumple(producto: dict[str, Any], impuestos: dict[str, Any]) -> bool:
    declarados = {str(k): v for k, v in (producto.get("atributos") or {}).items()}
    return all(k in declarados and _valor_cumple(k, declarados[k], v) for k, v in impuestos.items())


def emparejar(
    texto: str,
    conceptos: list[dict[str, Any]],
    productos: list[dict[str, Any]],
    *,
    embedding_renglon: list[float] | None = None,
    concepto_forzado: str | None = None,
) -> Emparejamiento:
    corregido = corregir(texto, lexico_de(conceptos))
    asignado = next((c for c in conceptos if concepto_forzado and c.get("codigo") == concepto_forzado), None)
    if asignado is not None:
        concepto_id, nombre, parecido = asignado["id"], asignado["nombre"], 1.0
    else:
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
    impuestos = {
        k: v
        for k, v in extraer_atributos(corregido, tuple(concepto.get("discriminantes") or ())).items()
        if (k, v) not in _NO_SE_EXIGEN
    }
    del_concepto = [p for p in productos if p.get("concepto_id") == concepto_id]
    if pide_titulo(concepto.get("discriminantes") or ()):
        del_concepto = del_mismo_titulo(texto, del_concepto)
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
    conceptos, productos = await _cargar_indice_cli()
    if embeder is None:
        embeder = _embeder_por_entorno()
    if embeder is None:
        log.debug("sin GEMINI_API_KEY: match lexico")
    vectores = await calcular_vectores(renglones, embeder)
    return [
        emparejar(renglon, conceptos, productos, embedding_renglon=vec)
        for renglon, vec in zip(renglones, vectores, strict=True)
    ]


async def calcular_vectores(renglones: list[str], embeder: Embeder | None) -> list[list[float] | None]:
    if embeder is None or not renglones:
        return [None] * len(renglones)
    try:
        return list(await vectores_guardados(renglones, embeder))
    except Exception as exc:  # noqa: BLE001 - degrada a lexico, no tumba la consulta
        log.warning("canal semantico degradado a lexico: %s", exc)
        return [None] * len(renglones)


def _embeder_por_entorno() -> Embeder | None:
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
