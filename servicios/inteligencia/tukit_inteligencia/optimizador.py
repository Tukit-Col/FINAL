"""Los tres kits, con una heuristica explicita en vez de NSGA-II.

**Esto no es el optimizador de la tesis y conviene decirlo aqui arriba.** La
version que sostiene los resultados de hipervolumen es un NSGA-II sobre pymoo
que produce un frente de Pareto de verdad; lo que hay en este modulo es una
regla de seleccion por perfil, determinista y leible en una tarde. Se escribe
asi a proposito y por dos razones:

1. El ciclo completo tiene que correr y verse antes que cada etapa sea
   optima. Sin kits que salgan, no hay pantalla que probar ni contrato que
   verificar, y el optimizador bueno se estaria afinando a ciegas.
2. Los tres puntos que devuelve son comparables con los que devolveria el
   frente: mismo vocabulario de objetivos (`costo`, `fidelidad`,
   `disponibilidad`), misma forma de salida. Cambiar la heuristica por el
   algoritmo es reemplazar `elegir_por_perfil` y nada mas.

Lo que **si** es definitivo aqui, porque no depende del algoritmo:

- La aritmetica de unidades. `unidades_a_comprar = techo(cantidad_pedida /
  unidades_por_empaque)` es la correccion del defecto que sumaba doce cajas
  cuando la lista pedia doce lapices, y vale igual con cualquier optimizador.
- Que el total incluya solo lo que Tukit puede entregar. Una linea
  informativa se muestra y no se cobra (FU-06).
- La regla de recomendacion de la seccion 6 del contrato, que sale de la
  encuesta y no del algoritmo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any

from .modelos import PESOS_POR_OMISION, EstadoResolucion, PerfilKit

# Orden de calidad de marca. Se usa para desempatar y para saber que es "subir
# de nivel"; no se puede derivar del nombre, asi que vive aqui.
ORDEN_NIVEL = ("economico", "confiable", "premium")

# Los modos en los que Tukit puede poner el item en el carrito. Es la misma
# lista que `catalogo.modelos.MODOS_SURTIBLES`, repetida aqui porque este
# servicio no puede importar el otro (invariante 1) y porque el vocabulario
# viaja por HTTP en el contrato, no por un paquete compartido.
MODOS_SURTIBLES = frozenset({"mercado_abierto", "libro_libre"})

# Tipos de renglon que nunca van al carrito, dijera lo que dijera el modo.
TIPOS_NO_COMPRABLES = frozenset({"licencia_digital", "no_comprar", "diferido", "uniforme"})

# Dos ediciones del mismo titulo NO son sustituibles, asi que los textos no se
# consolidan entre hermanos aunque el titulo coincida. Es la regla inversa de
# la consolidacion y se enuncia como dato para poder explicarla en la linea.
TIPOS_NO_CONSOLIDABLES = frozenset({"texto"})
MOTIVO_NO_CONSOLIDABLE = "Dos ediciones del mismo titulo no son sustituibles."


@dataclass(frozen=True)
class Candidato:
    """Un producto que el catalogo ofrecio para un renglon."""

    sku: str
    nombre: str
    nivel: str
    precio_cop: int | None
    producto_id: str | None = None
    marca: str | None = None
    personaje: str | None = None
    imagen_url: str | None = None
    unidad_base: str = "unidad"
    unidades_por_empaque: int = 1
    atributos: dict[str, Any] = field(default_factory=dict)
    cumple: bool = True

    @property
    def rango_nivel(self) -> int:
        return ORDEN_NIVEL.index(self.nivel) if self.nivel in ORDEN_NIVEL else len(ORDEN_NIVEL)


@dataclass(frozen=True)
class Renglon:
    """Un renglon ya parseado y ya emparejado, listo para entrar a un kit."""

    hijo: str
    orden: int
    texto: str
    tipo_item: str
    modo_adquisicion: str
    cantidad: int
    estado_resolucion: str
    unidad_base: str = "unidad"
    concepto_codigo: str | None = None
    concepto_nombre: str | None = None
    parecido: float = 0.0
    candidatos: tuple[Candidato, ...] = ()
    mensaje: str | None = None
    instruccion_colegio: str | None = None
    url_externa: str | None = None
    nota: str | None = None

    @property
    def informativa(self) -> bool:
        """Se muestra y no se cobra.

        Dos caminos distintos llevan aqui y los dos importan: el TIPO de
        renglon (una licencia digital nunca va al carrito) y el MODO de
        adquisicion (un texto de edicion exclusiva es papel comprable, pero el
        colegio cerro quien lo vende). Colapsarlos perderia el segundo, que es
        justo el que hace la diferencia entre un catalogo que promete y uno
        que cumple.
        """
        return self.tipo_item in TIPOS_NO_COMPRABLES or self.modo_adquisicion not in MODOS_SURTIBLES

    @property
    def no_consolidable(self) -> bool:
        return self.tipo_item in TIPOS_NO_CONSOLIDABLES


@dataclass(frozen=True)
class LineaKit:
    """Una linea ya resuelta para un perfil concreto."""

    hijo: str
    orden: int
    descripcion: str
    tipo: str
    estado_resolucion: str
    cantidad_pedida: int
    unidad_base: str
    unidades_por_empaque: int
    unidades_a_comprar: int
    informativa: bool
    elegido: Candidato | None = None
    alternativas: tuple[Candidato, ...] = ()
    precio_unitario_cop: int | None = None
    subtotal_cop: int | None = None
    mensaje: str | None = None
    instruccion_colegio: str | None = None
    url_externa: str | None = None
    no_consolidable: bool = False
    motivo_no_consolidable: str | None = None


@dataclass(frozen=True)
class KitArmado:
    perfil: str
    total_cop: int
    objetivos: dict[str, float | int]
    lineas: tuple[LineaKit, ...]
    consolidaciones: tuple[dict[str, Any], ...] = ()
    recomendado: bool = False
    razon: str | None = None
    dentro_de_presupuesto: bool | None = None


def unidades_a_comprar(cantidad_pedida: int, unidades_por_empaque: int) -> int:
    """Techo de la division. La correccion del error de carrito, en una linea.

    El empaque nunca es cero: la base lo impide con un CHECK, y aqui se vuelve
    a defender porque una division por cero en el armado del kit seria un 500
    en la unica pantalla que el acudiente esperaba durante tres minutos.
    """
    if cantidad_pedida <= 0:
        return 0
    return math.ceil(cantidad_pedida / max(1, unidades_por_empaque))


def _precio_para_ordenar(candidato: Candidato) -> tuple[int, int]:
    """Los que tienen precio primero y de menor a mayor.

    Un candidato sin precio no se descarta: puede ser el unico que cumple el
    atributo que el colegio exigio, y ofrecerlo diciendo "no conocemos el
    precio" es mejor respuesta que no ofrecer nada. Lo que no puede es ganar
    una comparacion de precio, y por eso va al final del orden.
    """
    return (1, 0) if candidato.precio_cop is None else (0, candidato.precio_cop)


def elegir_por_perfil(
    candidatos: tuple[Candidato, ...],
    perfil: str,
    *,
    personajes: tuple[str, ...] = (),
) -> Candidato | None:
    """La unica pieza que un NSGA-II reemplazaria.

    `Ahorrador` es el mas barato; `Premium` el de mejor nivel de marca y, a
    igualdad de nivel, el mas barato; `Fan` el que trae el personaje que el
    acudiente pidio para ESE hijo, y si no hay ninguno se comporta como
    `Ahorrador` en vez de inventarse un personaje.

    Nota sobre `Ahorrador`: puede terminar eligiendo un producto de nivel
    `premium` si resulto mas barato por empaque, y eso NO es un defecto. El
    nivel describe un producto y el perfil describe una ponderacion sobre el
    kit completo; el contrato lo dice explicitamente para que nadie
    "arregle" la coincidencia de nombre.
    """
    admisibles = [c for c in candidatos if c.cumple] or list(candidatos)
    if not admisibles:
        return None

    if perfil == PerfilKit.PREMIUM.value:
        mejor_nivel = max(c.rango_nivel for c in admisibles)
        del_nivel = [c for c in admisibles if c.rango_nivel == mejor_nivel]
        return min(del_nivel, key=lambda c: (_precio_para_ordenar(c), c.sku))

    if perfil == PerfilKit.FAN.value:
        pedidos = {p.lower() for p in personajes}
        con_personaje = [
            c for c in admisibles if c.personaje and (not pedidos or c.personaje.lower() in pedidos)
        ]
        if con_personaje:
            return min(con_personaje, key=lambda c: (_precio_para_ordenar(c), c.sku))

    return min(admisibles, key=lambda c: (_precio_para_ordenar(c), c.sku))


def _linea(renglon: Renglon, perfil: str, personajes: tuple[str, ...]) -> LineaKit:
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
        )

    elegido = elegir_por_perfil(renglon.candidatos, perfil, personajes=personajes)
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
    )


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
        if linea.elegido is None or linea.informativa or linea.no_consolidable:
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
        for i in indices[1:]:
            otra = lineas[i]
            resultado[i] = replace(
                otra,
                unidades_a_comprar=0,
                subtotal_cop=0 if otra.precio_unitario_cop is not None else None,
                mensaje=(
                    f"Se compra junto con el de {primera.hijo}: un empaque de {empaque} alcanza para los dos."
                ),
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
    """Los tres ejes del frente, calculados solo sobre lo comprable.

    Medir fidelidad o disponibilidad sobre las lineas informativas inflaria
    los dos numeros con items que Tukit nunca iba a surtir, y el kit se veria
    mejor cuanto mas cosas no pudiera vender.
    """
    comprables = [linea for linea in lineas if not linea.informativa]
    if not comprables:
        return {"costo": total, "fidelidad": 0.0, "disponibilidad": 0.0}

    resueltas = sum(
        1 for linea in comprables if linea.estado_resolucion == EstadoResolucion.RESUELTO_AUTO.value
    )
    con_precio = sum(1 for linea in comprables if linea.precio_unitario_cop is not None)
    return {
        "costo": total,
        "fidelidad": round(resueltas / len(comprables), 3),
        "disponibilidad": round(con_precio / len(comprables), 3),
    }


def _personajes_de(preferencias: dict[str, Any], hijo: str) -> tuple[str, ...]:
    por_hijo = preferencias.get("personaje_por_hijo") or {}
    valores = por_hijo.get(hijo) or []
    return tuple(str(v) for v in valores)


def armar_kit(renglones: list[Renglon], perfil: str, preferencias: dict[str, Any]) -> KitArmado:
    lineas = tuple(
        _linea(renglon, perfil, _personajes_de(preferencias, renglon.hijo)) for renglon in renglones
    )
    lineas, consolidaciones = consolidar(lineas)
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


def recomendar(kits: list[KitArmado], preferencias: dict[str, Any]) -> list[KitArmado]:
    """Marca UNO y no oculta los otros dos. La regla sale de la encuesta.

    - Por omision `Ahorrador`: 42 de 60 encuestados pagan como maximo 5 % mas
      y 15 exigen precio igual o menor.
    - `Premium` solo si el acudiente pone calidad primero Y declara al menos
      un 10 % de disposicion a pagar de mas.
    - `Fan` solo con `personaje_por_hijo` explicito. El personaje quedo ultimo
      en la P21, y tiene sentido: el que paga es el papa y el que quiere el
      personaje es el hijo.
    - Si el recomendado excede el presupuesto, se cae al siguiente kit que si
      quepa y la razon lo dice.
    """
    if not kits:
        return kits

    pesos = {**PESOS_POR_OMISION, **(preferencias.get("pesos") or {})}
    presupuesto = preferencias.get("presupuesto_por_hijo")
    sobreprecio = float(preferencias.get("disposicion_sobreprecio") or 0.0)
    personajes = preferencias.get("personaje_por_hijo") or {}

    por_perfil = {kit.perfil: kit for kit in kits}
    calidad_primero = pesos.get("calidad", 0) >= max(
        pesos.get("precio", 0), pesos.get("marca_exigida", 0), pesos.get("personaje", 0)
    )

    if personajes and pesos.get("personaje", 0) > 0 and PerfilKit.FAN.value in por_perfil:
        elegido, razon = (
            PerfilKit.FAN.value,
            "Pediste personajes para tus hijos, asi que este es el kit que los incluye.",
        )
    elif calidad_primero and sobreprecio >= 0.10 and PerfilKit.PREMIUM.value in por_perfil:
        elegido, razon = (
            PerfilKit.PREMIUM.value,
            "Pusiste la calidad primero y aceptas pagar hasta un 10 % mas.",
        )
    else:
        elegido, razon = (
            PerfilKit.AHORRADOR.value,
            "Elegiste precio como lo mas importante y este es el kit mas barato.",
        )

    # El presupuesto es una cota DURA, no un gusto. Es el uso mas valioso de la
    # encuesta: convierte una opinion en una restriccion que se puede imponer.
    cabe = None
    if isinstance(presupuesto, int) and presupuesto > 0:
        tope = int(presupuesto * max(1.0, 1.0 + sobreprecio))
        cabe = por_perfil[elegido].total_cop <= tope
        if not cabe:
            mas_barato = min(kits, key=lambda k: k.total_cop)
            if mas_barato.total_cop <= tope:
                elegido = mas_barato.perfil
                razon = (
                    f"El kit que pediste se pasa de tu presupuesto de ${presupuesto:,}, "
                    f"asi que te recomiendo este, que si cabe."
                )
                cabe = True
            else:
                razon = (
                    f"Ningun kit cabe en tu presupuesto de ${presupuesto:,}. "
                    f"Este es el mas barato que puedo armar."
                )
                elegido = mas_barato.perfil

    return [
        replace(
            kit,
            recomendado=kit.perfil == elegido,
            razon=razon if kit.perfil == elegido else None,
            dentro_de_presupuesto=cabe if kit.perfil == elegido else None,
        )
        for kit in kits
    ]


def armar_los_tres(renglones: list[Renglon], preferencias: dict[str, Any] | None = None) -> list[KitArmado]:
    """Los tres perfiles, con uno marcado. El punto de entrada de la etapa."""
    preferencias = preferencias or {}
    kits = [armar_kit(renglones, perfil.value, preferencias) for perfil in PerfilKit]
    return recomendar(kits, preferencias)
