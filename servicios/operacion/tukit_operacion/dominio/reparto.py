"""Como se interpreta un evento de bandeja de salida, sin base ni red.

El repartidor (`repartidor.py`) recoge eventos de las bandejas de Inteligencia y
Comercio y entrega su aviso. Que plantilla le toca a cada tipo, de donde sale el
destinatario cuando la carga ya lo trae, y como se arma el cuerpo del aviso son
decisiones puras: dependen solo de la fila del evento, no de conexiones. Viven
aqui para probarse solas y para que el worker quede como pura orquestacion.

Lo que NO esta aqui, a proposito: leer `trabajo_pipeline.usuario_id` para un
`kits_publicados` necesita la base de origen —eso es I/O, se queda en el worker.
Esta capa solo dice "de la carga no sale" (`destinatario_en_carga` devuelve None
para ese tipo); el worker sabe que entonces toca ir a la base.
"""

from __future__ import annotations

import uuid
from typing import Any

# Que plantilla y de donde sale el destinatario, por tipo de evento. La plantilla
# coincide con el nombre del tipo hoy, pero el mapa es el punto unico donde se
# decide "que tipos maneja este repartidor": un tipo fuera de aqui no nos toca.
_PLANTILLAS = {
    "kits_publicados": "kits_publicados",
    "pedido_pagado": "pedido_pagado",
    "incidencia": "incidencia",
    # Los avances del back-office de logistica (reparto propio).
    "pedido_despachado": "pedido_despachado",
    "pedido_en_reparto": "pedido_en_reparto",
    "pedido_entregado": "pedido_entregado",
}

# Los tipos cuyo destinatario viaja en la carga del evento (lo puso quien lo
# escribio). `kits_publicados` NO esta: su usuario se lee de trabajo_pipeline.
_USUARIO_EN_CARGA = frozenset(
    {"pedido_pagado", "incidencia", "pedido_despachado", "pedido_en_reparto", "pedido_entregado"}
)

# Si el despacho llego sin nombre (un evento viejo o malformado), el aviso sale
# igual: decir "va con nuestro repartidor" es mejor que no avisar.
_REPARTIDOR_POR_OMISION = "nuestro repartidor"


def plantilla_para(tipo: str) -> str | None:
    """La plantilla del aviso para un tipo de evento, o None si no nos toca."""
    return _PLANTILLAS.get(tipo)


def destinatario_en_carga(tipo: str, carga: dict[str, Any] | None) -> str | None:
    """El `usuario_id` que viaja en la carga, si este tipo lo trae ahi.

    Para `kits_publicados` devuelve None aunque la carga traiga un usuario: ese
    destinatario se resuelve contra `trabajo_pipeline` en el worker, no aqui.
    """
    if tipo not in _USUARIO_EN_CARGA:
        return None
    usuario = (carga or {}).get("usuario_id")
    return str(usuario) if usuario else None


def destinatario_de_la_cola(tipo: str, carga: dict[str, Any] | None) -> str | None:
    """El `usuario_id` de un evento que llega por RabbitMQ (ADR 0046).

    Con broker el repartidor no lee `trabajo_pipeline`: todo tipo con plantilla
    trae su destinatario en la carga, `kits_publicados` incluido (Inteligencia lo
    pone al emitirlo).
    """
    if tipo not in _PLANTILLAS:
        return None
    usuario = (carga or {}).get("usuario_id")
    return str(usuario) if usuario else None


def datos_plantilla(
    tipo: str, agregado_id: uuid.UUID, carga: dict[str, Any] | None, *, base_web: str
) -> dict[str, object]:
    """Las variables de negocio del aviso: turno, pedido, enlace, repartidor. Nunca contacto.

    El turno es un identificador corto y estable del evento (los 8 primeros del
    id del agregado). Para `kits_publicados` se agrega el enlace de pre-compra,
    que lleva SOLO el `agregado_id` opaco (nunca correo ni celular); `base_web`
    es la base de la app del acudiente, que el worker saca del entorno.
    """
    carga = carga or {}
    datos: dict[str, object] = {"turno": str(agregado_id)[:8].upper()}
    if carga.get("pedido_id"):
        datos["pedido"] = str(carga["pedido_id"])[:8].upper()
    if tipo == "kits_publicados":
        datos["enlace"] = f"{base_web}/kits/{agregado_id}"
    if tipo == "pedido_despachado":
        # Solo el nombre: Comercio nunca pone el celular del repartidor en la carga.
        datos["repartidor"] = str(carga.get("repartidor") or "").strip() or _REPARTIDOR_POR_OMISION
    return datos
