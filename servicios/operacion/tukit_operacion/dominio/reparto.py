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
    # Los avances del back-office de logistica (reparto propio): una plantilla por fase
    # del dashboard del acudiente, mas la cancelacion con su reembolso.
    "pedido_en_preparacion": "pedido_en_preparacion",
    "pedido_cancelado": "pedido_cancelado",
    "pedido_despachado": "pedido_despachado",
    "pedido_en_reparto": "pedido_en_reparto",
    "pedido_entregado": "pedido_entregado",
    # La respuesta del equipo a un ticket (bandeja de la propia Operacion).
    "caso_respuesta": "caso_respuesta",
}

# Los tipos cuyo destinatario viaja en la carga del evento (lo puso quien lo
# escribio). `kits_publicados` NO esta: su usuario se lee de trabajo_pipeline.
_USUARIO_EN_CARGA = frozenset(
    {
        "pedido_pagado",
        "incidencia",
        "pedido_en_preparacion",
        "pedido_cancelado",
        "pedido_despachado",
        "pedido_en_reparto",
        "pedido_entregado",
        "caso_respuesta",
    }
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


def lugar_de(colegio_nombre: str | None, grado: str | None) -> str:
    """ "Colegio X, grado 3": lo unico de la lista que viaja en el aviso. Sin
    apodo ni nombre de menor (Ley 1581); si falta algo, lo que haya."""
    partes = []
    if colegio_nombre and colegio_nombre.strip():
        partes.append(colegio_nombre.strip())
    if grado and str(grado).strip():
        partes.append(f"grado {str(grado).strip()}")
    return ", ".join(partes) or "tu lista escolar"


def _y(partes: list[str]) -> str:
    """ "A", "A y B", "A, B y C"."""
    if len(partes) <= 1:
        return partes[0] if partes else ""
    return f"{', '.join(partes[:-1])} y {partes[-1]}"


def _listas_de(carga: dict[str, Any]) -> list[dict[str, str]]:
    """Las listas del aviso: `listas` si viene; si no (evento viejo), la del primer hijo."""
    crudas = carga.get("listas")
    if isinstance(crudas, list) and crudas:
        salida = []
        for lista in crudas:
            if isinstance(lista, dict):
                par = {
                    "colegio_id": str(lista.get("colegio_id") or ""),
                    "grado": str(lista.get("grado") or ""),
                }
                if par not in salida:
                    salida.append(par)
        if salida:
            return salida
    return [{"colegio_id": str(carga.get("colegio_id") or ""), "grado": str(carga.get("grado") or "")}]


def lugares_de(listas: list[dict[str, Any]], nombres: dict[str, str | None]) -> str:
    """ "Colegio X, grados Septimo y Jardin" o "Colegio A, grado 3 y Colegio B, grado 5".

    Agrupa por colegio en el orden de las listas; cada colegio con sus grados sin
    repetir. Sin apodo ni nombre de menor (Ley 1581). Sin listas, lo de `lugar_de`.
    """
    if not listas:
        return lugar_de(None, None)
    grupos: dict[str, list[str]] = {}
    for lista in listas:
        colegio = str(lista.get("colegio_id") or "")
        grado = str(lista.get("grado") or "").strip()
        grados = grupos.setdefault(colegio, [])
        if grado and grado not in grados:
            grados.append(grado)
    partes = []
    for colegio, grados in grupos.items():
        nombre = (nombres.get(colegio) or "").strip()
        trozo = []
        if nombre:
            trozo.append(nombre)
        if grados:
            trozo.append(f"{'grados' if len(grados) > 1 else 'grado'} {_y(grados)}")
        if trozo:
            partes.append(", ".join(trozo))
    return _y(partes) or lugar_de(None, None)


def _uuid_o_none(valor: object) -> uuid.UUID | None:
    """El id si es un UUID valido; si no, None (nunca se arma un enlace con basura)."""
    try:
        return uuid.UUID(str(valor)) if valor else None
    except ValueError:
        return None


def datos_plantilla(
    tipo: str,
    agregado_id: uuid.UUID,
    carga: dict[str, Any] | None,
    *,
    base_web: str,
    colegio_nombre: str | None = None,
    colegios: dict[str, str | None] | None = None,
) -> dict[str, object]:
    """Las variables de negocio del aviso: pedido, enlace, repartidor... Nunca contacto.

    El unico identificador que ve el acudiente es el codigo del pedido (los 8
    primeros de su id, en mayusculas), el mismo de "Mis pedidos" y de
    `/pedidos/<id>`. No hay "turno": en un evento de pedido seria ese mismo codigo
    repetido. Para `kits_publicados` el enlace lleva a la pre-compra y, en un aviso
    de pedido, a su linea de tiempo; ambos llevan SOLO el id opaco (nunca correo ni
    celular). `base_web` es la base de la app del acudiente, que el worker saca del
    entorno.

    Para `kits_publicados`, `colegios` es `{colegio_id: nombre}` de cada colegio
    distinto de `listas` y arma "Colegio X, grados Septimo y Jardin"; `colegio_nombre`
    (el nombre del colegio del primer hijo) sigue valiendo para la ruta vieja.
    """
    carga = carga or {}
    datos: dict[str, object] = {}
    pedido_id = _uuid_o_none(carga.get("pedido_id"))
    if pedido_id is not None:
        datos["pedido"] = str(pedido_id)[:8].upper()
        datos["enlace"] = f"{base_web}/pedidos/{pedido_id}"
    if tipo == "pedido_pagado" and carga.get("total") is not None:
        datos["total"] = carga["total"]
    if tipo == "incidencia" and carga.get("motivo"):
        datos["motivo"] = str(carga["motivo"])
    if tipo == "pedido_en_preparacion":
        datos["retoma"] = bool(carga.get("retoma"))
    if tipo == "pedido_cancelado":
        datos["reembolso"] = bool(carga.get("reembolso"))
    if tipo == "caso_respuesta":
        # El texto de la respuesta NO viaja: el aviso solo invita a leerla en Tukit.
        datos["caso"] = str(agregado_id)[:8].upper()
    if tipo == "kits_publicados":
        datos["enlace"] = f"{base_web}/kits/{agregado_id}"
        listas = _listas_de(carga)
        nombres = dict(colegios or {})
        if colegio_nombre and carga.get("colegio_id"):
            nombres.setdefault(str(carga["colegio_id"]), colegio_nombre)
        datos["lugar"] = lugares_de(listas, nombres)
        # Una linea por lista para la fila "Listas" del correo.
        datos["listas"] = [lugar_de(nombres.get(li["colegio_id"]), li["grado"]) for li in listas]
    if tipo == "pedido_despachado":
        # Solo el nombre: Comercio nunca pone el celular del repartidor en la carga.
        datos["repartidor"] = str(carga.get("repartidor") or "").strip() or _REPARTIDOR_POR_OMISION
    return datos
