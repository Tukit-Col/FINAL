"""El avance de un pedido por la cadena de entrega, como dominio puro.

El back-office de logistica empuja el pedido `pagado -> en_preparacion ->
despachado -> en_reparto -> entregado`, con `incidencia` como desvio no terminal
y `cancelado` como salida. Tres preguntas gobiernan cada paso, y este modulo las
separa del router y del SQL:

1. *Es legal la transicion?* Lo responde la tabla `TRANSICIONES_PEDIDO` que ya
   vive en `modelos/base.py`; no se repite aqui, se consulta con
   `transicion_valida`. Reusarla es lo que mantiene una sola fuente de verdad de
   la maquina de estados.
2. *Le toca al back-office?* `AVANCES_DE_LOGISTICA` recorta esa tabla a lo que
   el operador puede mover. La tabla tambien la usan el webhook (que pone
   `pagado`), el retracto y el barredor (que cancelan); esos caminos no pasan
   por aqui.
3. *Estan los datos que el destino exige?* Lo que la tabla no puede expresar:
   con reparto propio, un despacho sin el nombre y el celular del repartidor no
   tiene a quien llamar; una incidencia sin su tipo no se puede atender.

`validar_avance` es pura: recibe cadenas y datos planos, no toca base ni HTTP, y
devuelve `None` cuando el avance es valido o un `AvanceRechazado` (razon tipada +
codigo HTTP + campo culpable) cuando no. El router traduce ese rechazo a un
`ErrorDominio`.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..modelos import EstadoPedido, transicion_valida

# Los tipos de incidencia, en el codigo y no en la base (sin CHECK): ampliarlos
# es cambiar esta tupla, sin migracion. El admin pinta su etiqueta.
TIPOS_INCIDENCIA = ("no_habia_nadie", "direccion_errada", "rechazado", "otro")

_E = EstadoPedido

# Lo que el back-office puede mover desde `/avanzar`: un SUBCONJUNTO de
# `TRANSICIONES_PEDIDO` (una prueba lo fija), uno a uno con los botones del
# admin. Quedan fuera, a proposito, `pendiente_pago -> pagado` (solo el webhook
# lo pone, con el pago como prueba), `pendiente_pago -> cancelado` (lo hace el
# barredor al vencer la reserva) y `pagado -> cancelado`: el staff solo cancela
# despues de una incidencia, que deja tipo y nota en el historial.
AVANCES_DE_LOGISTICA: dict[EstadoPedido, frozenset[EstadoPedido]] = {
    _E.PAGADO: frozenset({_E.EN_PREPARACION, _E.INCIDENCIA}),
    _E.EN_PREPARACION: frozenset({_E.DESPACHADO, _E.INCIDENCIA}),
    _E.DESPACHADO: frozenset({_E.EN_REPARTO, _E.INCIDENCIA}),
    _E.EN_REPARTO: frozenset({_E.ENTREGADO, _E.INCIDENCIA}),
    _E.INCIDENCIA: frozenset({_E.EN_PREPARACION, _E.CANCELADO}),
}

# Que aviso al acudiente sale de cada destino. Cancelar y reprogramar no avisan
# en esta fase: el contacto lo hace el operador, que ya sabe que paso.
_AVISOS = {
    _E.DESPACHADO: "pedido_despachado",
    _E.EN_REPARTO: "pedido_en_reparto",
    _E.ENTREGADO: "pedido_entregado",
    _E.INCIDENCIA: "incidencia",
}


@dataclass(frozen=True)
class AvanceRechazado:
    """Por que un avance no procede, con el codigo HTTP que le corresponde.

    `razon` es un identificador estable (no un mensaje) para que el router arme
    el sobre de error; `estado` es el HTTP: `422` cuando el destino ni siquiera
    es un estado o le faltan datos de entrada, `409` cuando el destino es valido
    pero la transicion desde el estado actual no lo es (conflicto de estado).
    `campo` dice que entrada corregir, para que el formulario la marque.
    """

    razon: str
    estado: int
    campo: str = "destino"


@dataclass(frozen=True)
class AvancePreparado:
    """Las entradas de un avance ya limpias y recortadas a lo que su destino usa.

    El repartidor solo se guarda en un despacho y el tipo solo en una
    incidencia: un `repartidor_nombre` que llegue con un `en_reparto` no debe
    sobrescribir el del envio. `aviso` es el tipo de evento a encolar, o None.
    """

    repartidor_nombre: str | None
    repartidor_celular: str | None
    tipo_incidencia: str | None
    nota: str | None
    aviso: str | None


def _limpio(valor: str | None) -> str | None:
    """Recorta espacios; una cadena vacia cuenta como ausente."""
    if valor is None:
        return None
    valor = valor.strip()
    return valor or None


def _estado(valor: str) -> EstadoPedido | None:
    try:
        return EstadoPedido(valor)
    except ValueError:
        return None


def es_avance_de_logistica(actual: str, destino: str) -> bool:
    """Si el back-office puede mover el pedido de `actual` a `destino`. No lanza
    ante un estado desconocido: devuelve False."""
    desde, hacia = _estado(actual), _estado(destino)
    if desde is None or hacia is None:
        return False
    return hacia in AVANCES_DE_LOGISTICA.get(desde, frozenset())


def validar_avance(
    actual: str,
    destino: str,
    *,
    repartidor_nombre: str | None = None,
    repartidor_celular: str | None = None,
    tipo_incidencia: str | None = None,
    nota: str | None = None,
) -> AvanceRechazado | None:
    """Valida mover un pedido de `actual` a `destino`. `None` = adelante.

    Rechaza, en orden: un `destino` que no es un estado conocido (`422`); una
    transicion que la tabla no permite o que no le toca al back-office (`409`);
    un despacho sin nombre o sin celular del repartidor (`422`); y una
    incidencia sin tipo, con un tipo que no existe, o de tipo `otro` sin nota
    (`422`). Cualquier otro avance pasa.
    """
    destino_estado = _estado(destino)
    if destino_estado is None:
        return AvanceRechazado("destino_invalido", 422)

    # La tabla manda; la matriz de logistica recorta. Se consultan las dos para
    # que un cambio en la tabla nunca abra por aqui una transicion ilegal.
    if not (transicion_valida(actual, destino) and es_avance_de_logistica(actual, destino)):
        return AvanceRechazado("transicion_invalida", 409)

    if destino_estado is EstadoPedido.DESPACHADO:
        if _limpio(repartidor_nombre) is None:
            return AvanceRechazado("despacho_incompleto", 422, "repartidor_nombre")
        if _limpio(repartidor_celular) is None:
            return AvanceRechazado("despacho_incompleto", 422, "repartidor_celular")

    if destino_estado is EstadoPedido.INCIDENCIA:
        tipo = _limpio(tipo_incidencia)
        if tipo is None:
            return AvanceRechazado("incidencia_sin_tipo", 422, "tipo_incidencia")
        if tipo not in TIPOS_INCIDENCIA:
            return AvanceRechazado("tipo_incidencia_invalido", 422, "tipo_incidencia")
        # "otro" no dice nada por si solo: sin la nota, quien atiende no sabe que paso.
        if tipo == "otro" and _limpio(nota) is None:
            return AvanceRechazado("incidencia_sin_nota", 422, "nota")

    return None


def tipo_aviso(destino: str) -> str | None:
    """El tipo de evento que avisa al acudiente de este destino, o None."""
    estado = _estado(destino)
    return _AVISOS.get(estado) if estado is not None else None


def preparar_avance(
    destino: str,
    *,
    repartidor_nombre: str | None = None,
    repartidor_celular: str | None = None,
    tipo_incidencia: str | None = None,
    nota: str | None = None,
) -> AvancePreparado:
    """Las entradas de un avance YA VALIDADO, limpias y recortadas a su destino."""
    estado = _estado(destino)
    despacho = estado is EstadoPedido.DESPACHADO
    incidencia = estado is EstadoPedido.INCIDENCIA
    return AvancePreparado(
        repartidor_nombre=_limpio(repartidor_nombre) if despacho else None,
        repartidor_celular=_limpio(repartidor_celular) if despacho else None,
        tipo_incidencia=_limpio(tipo_incidencia) if incidencia else None,
        nota=_limpio(nota),
        aviso=tipo_aviso(destino),
    )
