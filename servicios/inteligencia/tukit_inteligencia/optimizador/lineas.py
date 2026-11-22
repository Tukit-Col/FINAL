"""De renglones a lineas de kit: consolidacion, herramientas compartidas, personaje y `armar_kit`."""

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
    """Construye la linea del kit a partir del candidato ya elegido.

    Separa la CONSTRUCCION de la linea de la SELECCION del candidato: la
    seleccion la hace el frente (o la heuristica en la linea de un solo
    candidato) y este helper solo arma la fila con la aritmetica de unidades y
    el subtotal. Es la pieza que no cambia con el algoritmo.
    """
    if renglon.informativa:
        # Ni precio ni subtotal, y la base lo impone con un CHECK. Lo que si
        # lleva es la instruccion textual del colegio: decir "esto lo vende la
        # editorial el 24 de enero en el colegio" es util; callarlo deja al
        # acudiente con un hueco que descubre tarde.
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
    """Una herramienta que varias materias piden se compra una vez por hijo.

    Las listas se escriben por materia, y cada profesor pide lo que usa: las
    tijeras salen en artes, en tecnologia y en la cartuchera. Son las mismas
    tijeras, y el kit cobraba tres. En las 18 listas curadas, 43 renglones de
    herramientas repetian a otro identico (Decimo pedia tres calculadoras
    cientificas).

    Solo para conceptos `uno_por_estudiante` (lo dice el catalogo): lo que se
    gasta (pegante, cinta, cuadernos) puede ser uno por materia a proposito, y
    juntarlo dejaria al nino sin material. Dentro de un MISMO hijo: dos
    hermanos necesitan cada uno sus tijeras (eso lo decide `consolidar`, por
    empaque). Y sobre el PRODUCTO elegido: `regla` y `regla de acero` no son la
    misma compra.

    Se compra la cantidad mayor, no la suma: si artes pide dos reglas y la
    cartuchera una, dos alcanzan. La linea repetida sigue en el kit con cero
    unidades y dice donde quedo, igual que la de un hermano consolidado: el
    colegio la pidio y el acudiente tiene que poder encontrarla.
    """
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
    """Junta la demanda de varios hermanos sobre el mismo producto.

    Es la razon de que el trabajo sea por HOGAR y no por hijo: si cada hijo se
    pidiera aparte, nadie podria ver que dos ninos necesitan un borrador cada
    uno y que una caja de diez sale mejor que dos sueltos.

    La consolidacion se hace sobre el PRODUCTO elegido, no sobre el concepto.
    Dos hermanos a los que se les eligio el mismo sku comparten empaque; dos a
    los que se les eligio productos distintos, no, y forzarlo cambiaria lo que
    cada uno recibe sin decirlo.

    El ahorro se le imputa a la primera linea del grupo y las demas quedan en
    cero unidades con su explicacion. Se prefiere eso a borrarlas porque el
    acudiente pidio ese item para ese hijo y tiene que seguir viendolo.
    """
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
            # Sin ahorro no se toca nada. Consolidar por consolidar movería
            # unidades entre hermanos sin beneficio y volveria la explicacion
            # mas dificil de leer que la lista original.
            continue

        precio = primera.precio_unitario_cop
        ahorro = 0 if precio is None else precio * (sueltas - juntas)

        resultado[indices[0]] = replace(
            primera,
            unidades_a_comprar=juntas,
            subtotal_cop=None if precio is None else precio * juntas,
        )
        # El texto lo lee el acudiente: nunca el id interno del hijo ("hijo-1").
        # Se nombra la linea que si se compra, y de quien es si no es de este
        # mismo hijo (el grupo puede traer dos renglones del mismo hijo).
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
    """El resumen de display del kit, calculado solo sobre lo comprable.

    Medir sobre las lineas informativas inflaria los numeros con items que Tukit
    nunca iba a surtir, y el kit se veria mejor cuanto mas cosas no pudiera vender.

    `fidelidad` es EL MISMO eje que el frente optimiza: nivel de marca promedio
    normalizado a [0, 1], recomputado aqui desde el `rango_nivel` del candidato
    elegido en cada linea. Antes este `fidelidad` era otra cosa —la fraccion de
    lineas resueltas en automatico—, con lo que el numero que se mostraba no era
    el eje que se habia optimizado; los dos solo coincidian por correlacion. Esa
    fraccion sigue siendo util y se reporta aparte como `resolucion_auto`.
    """
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
    """El renglon pide EXPLICITAMENTE un surtido (`colores surtidos`, `color=surtido`).

    Es la unica excepcion a la regla de variedad del Fan: si el colegio pide un
    surtido, repetir el mismo producto de personaje no contradice nada. Se mira
    tanto el atributo ya extraido por el catalogo como el texto crudo, porque el
    catalogo solo extrae `surtido` para los conceptos que lo declaran.
    """
    return "surtid" in texto.lower() or any(str(v).lower() == "surtido" for v in impuestos.values())


def puntaje_de_encaje(impuestos: dict[str, Any], atributos: dict[str, Any]) -> int | None:
    """Cuanto encaja un producto en lo que un renglon exige. `None` si lo contradice.

    Entrada: lo que el renglon exige (`encuadernacion=cosido`) y lo que el
    producto declara. Salida: `None` si algun atributo declarado por el producto
    difiere del exigido (un argollado en un renglon que pide cosido), o el
    numero de atributos exigidos que el producto declara y cumple.

    Un atributo que el producto NO declara no contradice: los productos de
    personaje traen pocos atributos (el cuaderno de Spiderman declara
    encuadernacion, rayado y materias, pero no las hojas), y exigirles todo
    dejaria al Fan sin personaje en renglones donde si cabe. El empate entre
    renglones lo rompe el numero de aciertos (mas aciertos = mejor encaje).
    """
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
    """Que renglones llevan producto de personaje, y cual variante lleva cada uno.

    Algoritmo.
    Entrada: los renglones de UN concepto (cuaderno, cartuchera...) como tuplas
    `(clave, hijo, atributos_impuestos, texto)` en el orden del kit, y las
    variantes de personaje que el catalogo surte para ese concepto (cada una
    con sus `atributos` y `precio_desde`).
    Salida: `{clave_renglon: indice_de_variante}`.
    Estrategia: el kit Fan pone el personaje, pero un mismo producto no se
    repite en todos los renglones del concepto (cuatro cuadernos de Spiderman
    iguales no son variedad). Por cada hijo se evalua cada par (renglon,
    variante) con `puntaje_de_encaje`; un par que el renglon contradice (None)
    se descarta. De los restantes se elige UNO: el de mayor encaje; en empate,
    el renglon que va primero en el kit y luego la variante mas barata (el sku
    desempata). Con varias variantes, el cuaderno multimaterias no tapa al
    cosido de una materia que si cabe. Los renglones que piden `surtido`
    explicitamente tambien lo llevan (su mejor variante), porque ahi repetir es
    lo pedido. Si ningun par encaja, ese hijo queda sin personaje en el
    concepto (mejor un cuaderno neutro que el que el colegio no acepto) y el
    llamador lo reporta como `personaje_sin_encaje`.
    Complejidad: O(n * v * a), con n renglones, v variantes y a atributos
    exigidos por renglon; una sola pasada.
    """
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
            # `>` estricto: con igual encaje se queda la variante mas barata.
            if puntaje is not None and (mejor_del_renglon is None or puntaje > mejor_del_renglon[0]):
                mejor_del_renglon = (puntaje, indice)
        if mejor_del_renglon is None:
            continue
        puntaje, indice = mejor_del_renglon
        if _pide_surtido(texto, impuestos):
            llevan[clave] = indice
        # `>` estricto: el primer renglon que alcanza el maximo se queda el empate.
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
    """Que el kit Fan no repita el MISMO producto de personaje entre renglones.

    Algoritmo.
    Entrada: los renglones del kit, la eleccion ya hecha por (hijo, orden) y las
    preferencias (personajes pedidos por hijo).
    Salida: la misma eleccion, donde cada producto de personaje aparece una sola
    vez por hijo (salvo en renglones que piden surtido).
    Estrategia: recorrido en el orden del kit con un conjunto de
    (hijo, sku) ya usados. La primera vez que un producto de personaje aparece
    se conserva, asi el personaje queda al menos una vez. Si reaparece, el
    renglon cambia a (1) otro producto del personaje pedido que aun no se uso y
    cumpla lo que el renglon exige, el mas barato; o (2) el candidato sin
    personaje mas barato, que es el estilo normal que el Ahorrador elegiria.
    Si el renglon no tiene alternativa (todos sus candidatos son ese producto)
    se deja como esta: un renglon repetido es mejor que uno vacio.
    No toca Ahorrador, Premium ni A tu Medida: solo se invoca para el Fan, y
    cambiar un candidato por otro del MISMO renglon no altera la aritmetica de
    unidades (cada linea recalcula su empaque).
    Complejidad: O(n * c), con n renglones y c candidatos por renglon.
    """
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
    """Arma un kit para un perfil.

    Si `elecciones` viene (proyeccion del frente de Pareto), se usa el candidato
    que el frente asigno a cada linea; si no, se cae a la heuristica por perfil.
    La diferencia es solo la SELECCION del candidato: unidades, consolidacion,
    total honesto y objetivos son identicos en las dos rutas.
    """
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
    # El total suma SOLO lo no informativo. Es la promesa de la seccion 5.1.1
    # del contrato y la que impide cobrar lo que no se puede entregar.
    total = sum(linea.subtotal_cop or 0 for linea in lineas if not linea.informativa)
    return KitArmado(
        perfil=perfil,
        total_cop=total,
        objetivos=_objetivos(lineas, total),
        lineas=lineas,
        consolidaciones=consolidaciones,
    )


def anclar_personaje(kit: KitArmado, personaje: str | None) -> KitArmado:
    """Sube al tope las 4 lineas ancla cuyo producto trae el personaje pedido.

    Es post-proceso puro sobre un kit ya armado: NSGA-II no se toca. Cuando el
    acudiente pidio un personaje para el hijo, las lineas de los cuatro
    conceptos ancla (`CONCEPTOS_ANCLA`) cuyo producto elegido es de ese
    personaje se mueven al frente en el orden canonico cuaderno -> cartuchera
    -> carpeta -> maleta; el resto de las lineas conserva su orden. Como solo
    reordena, `total_cop`, `consolidaciones` y objetivos no cambian (el total
    es una suma, no depende del orden), y se defiende con una prueba.

    Si `personaje` es None o ninguna linea ancla trae ese personaje, devuelve
    el kit sin tocar (mismo objeto cuando es None).
    """
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
