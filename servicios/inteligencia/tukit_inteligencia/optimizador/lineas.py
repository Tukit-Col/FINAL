from __future__ import annotations

from dataclasses import replace
from typing import Any

from tukit_comun.texto import normalizar_personaje

from ..modelos import EstadoResolucion, PerfilKit
from .candidatos import elegir_por_perfil
from .preferencias import _personajes_de
from .tipos import (
    CONCEPTOS_ANCLA,
    MOTIVO_NO_CONSOLIDABLE,
    NOTA_CONSOLIDADA,
    ORDEN_NIVEL,
    Candidato,
    KitArmado,
    LineaKit,
    Renglon,
    _admisibles,
    _costo_para_ordenar,
    unidades_a_comprar,
)


def _linea_desde(renglon: Renglon, elegido: Candidato | None) -> LineaKit:
    if renglon.informativa:
        return LineaKit(
            hijo=renglon.hijo,
            orden=renglon.orden,
            descripcion=renglon.texto,
            tipo=renglon.tipo_item,
            estado_resolucion=renglon.estado_resolucion,
            cantidad_pedida=renglon.cantidad,
            unidad_base=renglon.unidad_base,
            unidades_por_empaque=1,
            unidades_a_comprar=0,
            informativa=True,
            mensaje=renglon.mensaje or renglon.nota,
            instruccion_colegio=renglon.instruccion_colegio,
            url_externa=renglon.url_externa,
            no_consolidable=renglon.no_consolidable,
            motivo_no_consolidable=MOTIVO_NO_CONSOLIDABLE if renglon.no_consolidable else None,
            concepto_codigo=renglon.concepto_codigo,
        )

    if elegido is None:
        return LineaKit(
            hijo=renglon.hijo,
            orden=renglon.orden,
            descripcion=renglon.texto,
            tipo=renglon.tipo_item,
            estado_resolucion=renglon.estado_resolucion,
            cantidad_pedida=renglon.cantidad,
            unidad_base=renglon.unidad_base,
            unidades_por_empaque=1,
            unidades_a_comprar=0,
            informativa=False,
            mensaje=renglon.mensaje,
            concepto_codigo=renglon.concepto_codigo,
        )

    unidades = unidades_a_comprar(renglon.cantidad, elegido.unidades_por_empaque)
    subtotal = None if elegido.precio_cop is None else elegido.precio_cop * unidades
    alternativas = tuple(c for c in renglon.candidatos if c.sku != elegido.sku)[:2]

    return LineaKit(
        hijo=renglon.hijo,
        orden=renglon.orden,
        descripcion=renglon.texto,
        tipo=renglon.tipo_item,
        estado_resolucion=renglon.estado_resolucion,
        cantidad_pedida=renglon.cantidad,
        unidad_base=elegido.unidad_base or renglon.unidad_base,
        unidades_por_empaque=elegido.unidades_por_empaque,
        unidades_a_comprar=unidades,
        informativa=False,
        elegido=elegido,
        alternativas=alternativas,
        precio_unitario_cop=elegido.precio_cop,
        subtotal_cop=subtotal,
        mensaje=renglon.mensaje,
        no_consolidable=renglon.no_consolidable,
        motivo_no_consolidable=MOTIVO_NO_CONSOLIDABLE if renglon.no_consolidable else None,
        concepto_codigo=renglon.concepto_codigo,
        uno_por_estudiante=renglon.uno_por_estudiante,
        atributos_impuestos=dict(renglon.atributos_impuestos),
    )


def juntar_herramientas(lineas: tuple[LineaKit, ...]) -> tuple[LineaKit, ...]:
    grupos: dict[tuple[str, str], list[int]] = {}
    for indice, linea in enumerate(lineas):
        if linea.elegido is None or linea.informativa or not linea.uno_por_estudiante:
            continue
        grupos.setdefault((linea.hijo, linea.elegido.sku), []).append(indice)

    resultado = list(lineas)
    for indices in grupos.values():
        if len(indices) < 2:
            continue
        primera = lineas[indices[0]]
        cantidad = max(lineas[i].cantidad_pedida for i in indices)
        unidades = unidades_a_comprar(cantidad, primera.unidades_por_empaque)
        precio = primera.precio_unitario_cop
        resultado[indices[0]] = replace(
            primera,
            unidades_a_comprar=unidades,
            subtotal_cop=None if precio is None else precio * unidades,
        )
        for i in indices[1:]:
            otra = lineas[i]
            resultado[i] = replace(
                otra,
                unidades_a_comprar=0,
                subtotal_cop=0 if otra.precio_unitario_cop is not None else None,
                junto_a=primera.orden,
                mensaje=f"Ya va en la linea {primera.orden}: sirve para todas las materias.",
            )
    return tuple(resultado)


def consolidar(lineas: tuple[LineaKit, ...]) -> tuple[tuple[LineaKit, ...], tuple[dict[str, Any], ...]]:
    grupos: dict[str, list[int]] = {}
    for indice, linea in enumerate(lineas):
        if linea.elegido is None or linea.informativa or linea.no_consolidable or linea.junto_a is not None:
            continue
        grupos.setdefault(linea.elegido.sku, []).append(indice)

    resultado = list(lineas)
    notas: list[dict[str, Any]] = []

    for sku, indices in grupos.items():
        if len(indices) < 2:
            continue
        hijos = sorted({lineas[i].hijo for i in indices})
        if len(hijos) < 2:
            continue

        primera = lineas[indices[0]]
        empaque = primera.unidades_por_empaque
        demanda = sum(lineas[i].cantidad_pedida for i in indices)
        juntas = unidades_a_comprar(demanda, empaque)
        sueltas = sum(lineas[i].unidades_a_comprar for i in indices)
        if juntas >= sueltas:
            continue

        precio = primera.precio_unitario_cop
        ahorro = 0 if precio is None else precio * (sueltas - juntas)

        resultado[indices[0]] = replace(
            primera,
            unidades_a_comprar=juntas,
            subtotal_cop=None if precio is None else precio * juntas,
        )
        para_quienes = "los dos" if len(indices) == 2 else "todos"
        de_otro = "tu otro hijo" if len(hijos) == 2 else "otro de tus hijos"
        for i in indices[1:]:
            otra = lineas[i]
            donde = f"la línea {primera.orden}" + ("" if otra.hijo == primera.hijo else f" de {de_otro}")
            resultado[i] = replace(
                otra,
                unidades_a_comprar=0,
                subtotal_cop=0 if otra.precio_unitario_cop is not None else None,
                mensaje=f"{NOTA_CONSOLIDADA}{donde}: un empaque de {empaque} alcanza para {para_quienes}.",
            )

        notas.append(
            {
                "sku": sku,
                "producto": primera.elegido.nombre if primera.elegido else sku,
                "hijos": hijos,
                "demanda_base": demanda,
                "unidades_a_comprar": juntas,
                "ahorro": ahorro,
                "explicacion": (f"Un empaque de {empaque} sale mas barato que {sueltas} por separado."),
            }
        )

    return tuple(resultado), tuple(notas)


def _objetivos(lineas: tuple[LineaKit, ...], total: int) -> dict[str, float | int]:
    comprables = [linea for linea in lineas if not linea.informativa]
    if not comprables:
        return {
            "costo": total,
            "fidelidad": 0.0,
            "disponibilidad": 0.0,
            "resolucion_auto": 0.0,
        }

    tope_nivel = max(1, len(ORDEN_NIVEL) - 1)
    suma_fidelidad = sum((linea.elegido.rango_nivel / tope_nivel) for linea in comprables if linea.elegido)
    resueltas = sum(
        1 for linea in comprables if linea.estado_resolucion == EstadoResolucion.RESUELTO_AUTO.value
    )
    con_precio = sum(1 for linea in comprables if linea.precio_unitario_cop is not None)
    return {
        "costo": total,
        "fidelidad": round(suma_fidelidad / len(comprables), 3),
        "disponibilidad": round(con_precio / len(comprables), 3),
        "resolucion_auto": round(resueltas / len(comprables), 3),
    }


def _pide_surtido(texto: str, impuestos: dict[str, Any]) -> bool:
    return "surtid" in texto.lower() or any(str(v).lower() == "surtido" for v in impuestos.values())


def puntaje_de_encaje(impuestos: dict[str, Any], atributos: dict[str, Any]) -> int | None:
    declarados = {k: str(v).lower() for k, v in (atributos or {}).items()}
    aciertos = 0
    for clave, exigido in (impuestos or {}).items():
        if clave not in declarados:
            continue
        if declarados[clave] != str(exigido).lower():
            return None
        aciertos += 1
    return aciertos


def renglones_con_personaje(
    renglones: list[tuple[Any, str, dict[str, Any], str]], variantes: list[dict[str, Any]]
) -> dict[Any, int]:
    orden_variante = sorted(
        range(len(variantes)),
        key=lambda i: (
            variantes[i].get("precio_desde") is None,
            variantes[i].get("precio_desde") or 0,
            str(variantes[i].get("sku") or ""),
        ),
    )
    mejor: dict[str, tuple[int, Any, int]] = {}
    llevan: dict[Any, int] = {}
    for clave, hijo, impuestos, texto in renglones:
        mejor_del_renglon: tuple[int, int] | None = None
        for indice in orden_variante:
            puntaje = puntaje_de_encaje(impuestos, variantes[indice].get("atributos") or {})
            if puntaje is not None and (mejor_del_renglon is None or puntaje > mejor_del_renglon[0]):
                mejor_del_renglon = (puntaje, indice)
        if mejor_del_renglon is None:
            continue
        puntaje, indice = mejor_del_renglon
        if _pide_surtido(texto, impuestos):
            llevan[clave] = indice
        if hijo not in mejor or puntaje > mejor[hijo][0]:
            mejor[hijo] = (puntaje, clave, indice)
    for _, clave, indice in mejor.values():
        llevan[clave] = indice
    return llevan


def variar_personaje(
    renglones: list[Renglon],
    elegidos: dict[tuple[str, int], Candidato | None],
    preferencias: dict[str, Any],
) -> dict[tuple[str, int], Candidato | None]:
    usados: set[tuple[str, str]] = set()
    resultado = dict(elegidos)
    for renglon in renglones:
        clave = (renglon.hijo, renglon.orden)
        elegido = resultado.get(clave)
        if renglon.informativa or elegido is None or not elegido.personaje:
            continue
        if (
            _pide_surtido(renglon.texto, renglon.atributos_impuestos)
            or (renglon.hijo, elegido.sku) not in usados
        ):
            usados.add((renglon.hijo, elegido.sku))
            continue

        admisibles = _admisibles(renglon)
        pedidos = {normalizar_personaje(p) for p in _personajes_de(preferencias, renglon.hijo)}

        def orden(c: Candidato, cantidad: int = renglon.cantidad) -> tuple[tuple[int, int, int], str]:
            return (_costo_para_ordenar(c, cantidad), c.sku)

        otros_disenos = [
            c
            for c in admisibles
            if c.personaje
            and (not pedidos or normalizar_personaje(c.personaje) in pedidos)
            and (renglon.hijo, c.sku) not in usados
        ]
        normales = [c for c in admisibles if not c.personaje]
        cambio = min(otros_disenos or normales, key=orden, default=None)
        if cambio is None:
            continue
        resultado[clave] = cambio
        if cambio.personaje:
            usados.add((renglon.hijo, cambio.sku))
    return resultado


def armar_kit(
    renglones: list[Renglon],
    perfil: str,
    preferencias: dict[str, Any],
    *,
    elecciones: dict[tuple[str, int], Candidato] | None = None,
) -> KitArmado:
    elegidos: dict[tuple[str, int], Candidato | None] = {}
    for renglon in renglones:
        if renglon.informativa:
            continue
        if elecciones is not None:
            elegidos[(renglon.hijo, renglon.orden)] = elecciones.get((renglon.hijo, renglon.orden))
        else:
            elegidos[(renglon.hijo, renglon.orden)] = elegir_por_perfil(
                renglon.candidatos,
                perfil,
                personajes=_personajes_de(preferencias, renglon.hijo),
                cantidad=renglon.cantidad,
            )
    if perfil == PerfilKit.FAN.value:
        elegidos = variar_personaje(renglones, elegidos, preferencias)

    lineas_lista: list[LineaKit] = []
    for renglon in renglones:
        if renglon.informativa:
            lineas_lista.append(_linea_desde(renglon, None))
        else:
            lineas_lista.append(_linea_desde(renglon, elegidos[(renglon.hijo, renglon.orden)]))

    lineas, consolidaciones = consolidar(juntar_herramientas(tuple(lineas_lista)))
    total = sum(linea.subtotal_cop or 0 for linea in lineas if not linea.informativa)
    return KitArmado(
        perfil=perfil,
        total_cop=total,
        objetivos=_objetivos(lineas, total),
        lineas=lineas,
        consolidaciones=consolidaciones,
    )


def anclar_personaje(kit: KitArmado, personaje: str | None) -> KitArmado:
    if personaje is None:
        return kit

    pedido = normalizar_personaje(personaje)

    def es_ancla(linea: LineaKit, codigo: str) -> bool:
        return (
            not linea.informativa
            and linea.concepto_codigo == codigo
            and linea.elegido is not None
            and normalizar_personaje(linea.elegido.personaje or "") == pedido
        )

    anclas: list[LineaKit] = []
    usadas: set[int] = set()
    for codigo in CONCEPTOS_ANCLA:
        for indice, linea in enumerate(kit.lineas):
            if indice not in usadas and es_ancla(linea, codigo):
                anclas.append(linea)
                usadas.add(indice)

    if not anclas:
        return kit

    resto = [linea for indice, linea in enumerate(kit.lineas) if indice not in usadas]
    return replace(kit, lineas=tuple(anclas) + tuple(resto))
