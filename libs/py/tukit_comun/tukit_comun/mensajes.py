from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any


class MensajeInvalido(ValueError):
    pass


@dataclass(frozen=True)
class Evento:
    id: int
    origen: str
    tipo: str
    agregado_tipo: str | None = None
    agregado_id: uuid.UUID | None = None
    carga: dict[str, Any] = field(default_factory=dict)
    correlacion_id: str | None = None
    intentos: int = 0

    @property
    def message_id(self) -> str:
        return f"{self.origen}:{self.id}"


def evento_de_fila(fila: Any, *, origen: str) -> Evento:
    carga = fila.carga if isinstance(fila.carga, dict) else {}
    agregado = fila.agregado_id
    return Evento(
        id=int(fila.id),
        origen=origen,
        tipo=str(fila.tipo),
        agregado_tipo=fila.agregado_tipo,
        agregado_id=uuid.UUID(str(agregado)) if agregado is not None else None,
        carga=carga,
        correlacion_id=carga.get("correlacion_id"),
    )


def cuerpo(evento: Evento) -> bytes:
    return json.dumps(
        {
            "evento_id": evento.id,
            "origen": evento.origen,
            "tipo": evento.tipo,
            "agregado_tipo": evento.agregado_tipo,
            "agregado_id": str(evento.agregado_id) if evento.agregado_id is not None else None,
            "carga": evento.carga,
            "correlacion_id": evento.correlacion_id,
        },
        default=str,
    ).encode()


def evento_de(datos: bytes, *, intentos: int = 0) -> Evento:
    try:
        sobre = json.loads(datos)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MensajeInvalido(f"el cuerpo no es JSON: {error}") from error
    if not isinstance(sobre, dict):
        raise MensajeInvalido("el cuerpo no es un objeto JSON")
    faltan = [clave for clave in ("evento_id", "origen", "tipo") if sobre.get(clave) in (None, "")]
    if faltan:
        raise MensajeInvalido(f"al sobre le falta {', '.join(faltan)}")
    carga = sobre.get("carga")
    if carga is not None and not isinstance(carga, dict):
        raise MensajeInvalido("la carga no es un objeto JSON")
    try:
        evento_id = int(sobre["evento_id"])
        agregado = sobre.get("agregado_id")
        agregado_id = uuid.UUID(str(agregado)) if agregado else None
    except (TypeError, ValueError) as error:
        raise MensajeInvalido(f"identificador invalido: {error}") from error
    return Evento(
        id=evento_id,
        origen=str(sobre["origen"]),
        tipo=str(sobre["tipo"]),
        agregado_tipo=sobre.get("agregado_tipo"),
        agregado_id=agregado_id,
        carga=carga or {},
        correlacion_id=sobre.get("correlacion_id"),
        intentos=intentos,
    )


__all__ = ["Evento", "MensajeInvalido", "cuerpo", "evento_de", "evento_de_fila"]
